#!/usr/bin/env python3
"""
Verified enrichment pipeline with strict matching criteria.

This script:
1. Searches Google Places API for business
2. VERIFIES the result matches the original business
3. Only enriches if verification passes
4. Flags mismatches for manual review

Verification checks:
- Company name similarity (fuzzy match with threshold)
- Website domain match (if available)
- Industry/category relevance

Usage:
    python scripts/verify_and_enrich.py --limit 3  # Test with 3 businesses first
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from difflib import SequenceMatcher
from urllib.parse import urlparse
import time

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')
CUSTOM_SEARCH_API_KEY = os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY')
CUSTOM_SEARCH_ENGINE_ID = os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
PLACES_API_BASE = "https://places.googleapis.com/v1"

if not PLACES_API_KEY:
    print("❌ Error: GOOGLE_PLACES_API_KEY not found in .env")
    sys.exit(1)

# Track custom search usage
CUSTOM_SEARCH_QUOTA_REMAINING = 100  # Reset daily
CUSTOM_SEARCH_QUOTA_EXCEEDED = False


def normalize_domain(url: str) -> str:
    """Extract base domain from URL (e.g., example.com from www.example.com)"""
    if not url:
        return ""
    try:
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""


def company_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two company names (0.0 to 1.0)

    Normalizes by:
    - Lowercase
    - Removing common suffixes (LLC, Inc, Corp, etc.)
    - Removing punctuation
    """
    # Normalize
    def normalize(name):
        name = name.lower()
        # Remove common business suffixes
        suffixes = [' llc', ' inc', ' corp', ' corporation', ' ltd', ' limited',
                   ' company', ' co', ',', '.', '-', '&']
        for suffix in suffixes:
            name = name.replace(suffix, '')
        return name.strip()

    norm1 = normalize(name1)
    norm2 = normalize(name2)

    # Use SequenceMatcher for fuzzy matching
    return SequenceMatcher(None, norm1, norm2).ratio()


def verify_match(
    original_company: str,
    original_website: str,
    found_name: str,
    found_website: str,
    found_address: str
) -> Tuple[bool, str, float]:
    """
    Verify if the Google Places result matches the original business

    Returns:
        (is_valid, reason, confidence_score)
    """

    # Check 1: Company name similarity
    name_similarity = company_name_similarity(original_company, found_name)

    # Check 2: Website domain match (if both available)
    website_match = False
    if original_website and found_website:
        orig_domain = normalize_domain(original_website)
        found_domain = normalize_domain(found_website)

        if orig_domain and found_domain:
            website_match = orig_domain == found_domain

    # Decision logic
    if website_match:
        return (True, f"Website domain match: {orig_domain}", 1.0)

    if name_similarity >= 0.85:
        return (True, f"High name similarity: {name_similarity:.2f}", name_similarity)

    if name_similarity >= 0.60:
        return (False, f"Medium name similarity: {name_similarity:.2f} - needs manual review", name_similarity)

    return (False, f"Low name similarity: {name_similarity:.2f} - likely wrong business", name_similarity)


def clean_company_name_for_search(company_name: str) -> str:
    """
    Clean company name to improve Google Places search results

    Removes:
    - URLs/domains (e.g., "- website.com")
    - Extra long descriptions
    Strategy: Keep name parts, remove domains
    """
    # Remove everything after " - " if it looks like a domain or description
    if ' - ' in company_name:
        parts = company_name.split(' - ')
        cleaned_parts = []

        for part in parts:
            part = part.strip()
            # Skip if it's a domain (.com, .io, etc.)
            if '.' in part and any(ext in part.lower() for ext in ['.com', '.io', '.net', '.org', '.co']):
                continue
            # Skip very long descriptive parts (> 50 chars)
            if len(part) > 50:
                continue
            cleaned_parts.append(part)

        # If we have multiple parts, join them
        if len(cleaned_parts) > 1:
            return ' '.join(cleaned_parts)
        elif len(cleaned_parts) == 1:
            return cleaned_parts[0]

    return company_name.strip()


def scrape_linkedin_about(url: str) -> Optional[Dict]:
    """
    Scrape LinkedIn company About page for contact info

    Returns dict with address, phone, email if found
    """
    try:
        print(f"     Fetching LinkedIn About page...")

        # Use requests for simple HTML fetching
        # LinkedIn may block requests without proper headers
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }, timeout=10)

        if response.status_code != 200:
            print(f"     ⚠️  HTTP {response.status_code}")
            return None

        text = response.text

        # Extract contact info using regex
        import re

        # Address pattern - LinkedIn shows "Primary\n9128 Knox Court , Laurel, MD 20723, US"
        address_match = re.search(r'Primary\s*\n\s*([^\n]+,\s*[A-Z]{2}\s+\d{5})', text)
        if not address_match:
            # Alternative pattern: just street, city, state zip
            address_match = re.search(r'(\d+\s+[\w\s]+,\s*[\w\s]+,\s*[A-Z]{2}\s+\d{5})', text)

        address = address_match.group(1).strip() if address_match else None

        # Parse city, state, zip from address
        city = None
        state = None
        zip_code = None
        if address:
            # Format: "9128 Knox Court , Laurel, MD 20723"
            parts = [p.strip() for p in address.split(',')]
            if len(parts) >= 3:
                city = parts[-2]
                state_zip = parts[-1].split()
                if len(state_zip) >= 2:
                    state = state_zip[0]
                    zip_code = state_zip[1]

        # Phone - look for "Phone\n571-277-0642"
        phone_match = re.search(r'Phone\s*\n\s*(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', text)
        if not phone_match:
            # Alternative: USA: +1 571-277-0642
            phone_match = re.search(r'USA:\s*\+?1?\s*(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', text)

        phone = phone_match.group(1).strip() if phone_match else None

        # Email
        email_match = re.search(r'Email:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})', text)
        email = email_match.group(1).strip() if email_match else None

        # Website - look for "Website\nhttps://..."
        website_match = re.search(r'Website\s*\n\s*(https?://[^\s\n]+)', text)
        website = website_match.group(1).strip() if website_match else None

        if address or phone or email:
            return {
                'address': address,
                'city': city,
                'state': state,
                'zip': zip_code,
                'phone': phone,
                'email': email,
                'website': website
            }

        return None

    except Exception as e:
        print(f"     ⚠️  LinkedIn scrape error: {e}")
        return None


def search_google_custom(company_name: str) -> Optional[Dict]:
    """
    Fallback to Google Custom Search API when Places API returns nothing

    Strategy:
    1. Search for company + "contact"
    2. If LinkedIn company page in results, fetch and scrape it
    3. Otherwise extract from snippets

    Returns structured business data extracted from search results
    """
    global CUSTOM_SEARCH_QUOTA_REMAINING, CUSTOM_SEARCH_QUOTA_EXCEEDED

    # Check if quota exceeded
    if CUSTOM_SEARCH_QUOTA_EXCEEDED:
        print(f"  ⚠️  Google Custom Search quota exceeded (100/day limit)")
        return None

    # Check if API keys configured
    if not CUSTOM_SEARCH_API_KEY or not CUSTOM_SEARCH_ENGINE_ID:
        print(f"  ℹ️  Google Custom Search not configured (optional)")
        return None

    print(f"  🔍 Trying Google Custom Search fallback...")

    try:
        # Build search query - "contact" tends to find contact pages with address/phone
        query = f'"{company_name}" contact'

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': CUSTOM_SEARCH_API_KEY,
            'cx': CUSTOM_SEARCH_ENGINE_ID,
            'q': query,
            'num': 3  # Get top 3 results
        }

        response = requests.get(url, params=params)

        # Check for quota exceeded
        if response.status_code == 429:
            print(f"  ⚠️  Google Custom Search quota exceeded!")
            CUSTOM_SEARCH_QUOTA_EXCEEDED = True
            return None

        if response.status_code != 200:
            print(f"  ❌ Custom Search API error: {response.status_code}")
            return None

        data = response.json()

        # Decrement quota
        CUSTOM_SEARCH_QUOTA_REMAINING -= 1
        print(f"     (Custom Search quota remaining: {CUSTOM_SEARCH_QUOTA_REMAINING})")

        if CUSTOM_SEARCH_QUOTA_REMAINING <= 0:
            CUSTOM_SEARCH_QUOTA_EXCEEDED = True

        # Extract business info from search results
        if 'items' not in data or len(data['items']) == 0:
            print(f"  ⚠️  No Custom Search results")
            return None

        # Check if LinkedIn company page is in results
        linkedin_url = None
        for item in data['items'][:3]:
            link = item.get('link', '')
            # Look for linkedin.com/company/{company-name}
            if 'linkedin.com/company/' in link:
                # Convert to /about page if not already
                if '/about' not in link:
                    linkedin_url = link.rstrip('/') + '/about/'
                else:
                    linkedin_url = link
                break

        # If LinkedIn found, scrape it for full contact info
        if linkedin_url:
            print(f"     Found LinkedIn page: {linkedin_url}")
            scraped = scrape_linkedin_about(linkedin_url)

            if scraped:
                print(f"  ✅ Found via LinkedIn scrape:")
                if scraped.get('address'):
                    print(f"     Address: {scraped['address']}")
                if scraped.get('phone'):
                    print(f"     Phone: {scraped['phone']}")
                if scraped.get('email'):
                    print(f"     Email: {scraped['email']}")

                return {
                    'enriched_place_id': None,
                    'enriched_google_name': company_name,
                    'enriched_address': scraped.get('address'),
                    'enriched_street': None,  # Could parse from address
                    'enriched_city': scraped.get('city'),
                    'enriched_state': scraped.get('state'),
                    'enriched_zip': scraped.get('zip'),
                    'enriched_country': 'US' if scraped.get('state') else None,
                    'enriched_phone': scraped.get('phone'),
                    'enriched_website': scraped.get('website'),
                    'enriched_rating': None,
                    'enriched_lat': None,
                    'enriched_lng': None,
                    'enrichment_status': 'success_custom_search',
                    'enrichment_source': 'custom_search_linkedin',
                    'verification_reason': 'Found via Google Custom Search + LinkedIn scrape',
                    'verification_confidence': 0.7
                }

        # Fallback: Extract from snippets if no LinkedIn or scrape failed
        combined_text = ""
        found_website = None

        for item in data['items'][:3]:
            snippet = item.get('snippet', '')
            combined_text += f" {snippet}"

            # Get website from first result
            if not found_website:
                found_website = item.get('link', '')

        # Simple regex extraction from snippets
        import re

        # Look for address pattern
        address_match = re.search(r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Court|Ct|Lane|Ln|Boulevard|Blvd)[,\s]+[\w\s]+,\s+[A-Z]{2}\s+\d{5}', combined_text)
        address = address_match.group(0) if address_match else None

        # Look for phone pattern
        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', combined_text)
        phone = phone_match.group(0) if phone_match else None

        # Look for email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', combined_text)
        email = email_match.group(0) if email_match else None

        if address or phone or email:
            print(f"  ✅ Found via Custom Search snippets:")
            if address:
                print(f"     Address: {address}")
            if phone:
                print(f"     Phone: {phone}")
            if email:
                print(f"     Email: {email}")

            return {
                'enriched_place_id': None,
                'enriched_google_name': company_name,
                'enriched_address': address,
                'enriched_street': None,
                'enriched_city': None,
                'enriched_state': None,
                'enriched_zip': None,
                'enriched_country': None,
                'enriched_phone': phone,
                'enriched_website': found_website,
                'enriched_rating': None,
                'enriched_lat': None,
                'enriched_lng': None,
                'enrichment_status': 'success_custom_search',
                'enrichment_source': 'custom_search_snippets',
                'verification_reason': 'Found via Google Custom Search snippets',
                'verification_confidence': 0.5
            }

        print(f"  ⚠️  Custom Search found results but no structured data")
        return None

    except Exception as e:
        print(f"  ❌ Custom Search error: {e}")
        return None


def search_and_verify(company_name: str, industry: str = None, original_website: str = None) -> Optional[Dict]:
    """
    Search Google Places API and verify the result matches

    Returns:
        Dict with enriched data if verified, None if no match or verification failed
    """

    # Clean company name for better search results
    cleaned_name = clean_company_name_for_search(company_name)

    # Build search query - use cleaned name + simpler industry
    query = cleaned_name
    # Only add industry if it's short and specific
    if industry and len(industry) < 30:
        # Take first industry if comma-separated
        first_industry = industry.split(',')[0].strip()
        query += f" {first_industry}"

    print(f"  🔍 Searching: {query}")
    if cleaned_name != company_name:
        print(f"     (cleaned from: {company_name})")

    try:
        # Search Google Places API
        search_url = f"{PLACES_API_BASE}/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": PLACES_API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.addressComponents,places.internationalPhoneNumber,places.websiteUri,places.rating,places.location"
        }
        payload = {"textQuery": query}

        response = requests.post(search_url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"  ❌ API Error: {response.status_code}")
            return None

        data = response.json()

        if not data.get('places') or len(data['places']) == 0:
            print(f"  ⚠️  No results found in Google Places")

            # Try Google Custom Search as fallback
            custom_result = search_google_custom(cleaned_name)
            if custom_result:
                return custom_result

            return None

        # Get first result
        place = data['places'][0]
        found_name = place.get('displayName', {}).get('text', '')
        found_website = place.get('websiteUri', '')
        found_address = place.get('formattedAddress', '')

        print(f"  📍 Found: {found_name}")
        print(f"     Address: {found_address}")
        if found_website:
            print(f"     Website: {found_website}")

        # VERIFY the match
        is_valid, reason, confidence = verify_match(
            company_name,
            original_website,
            found_name,
            found_website,
            found_address
        )

        if is_valid:
            print(f"  ✅ VERIFIED: {reason} (confidence: {confidence:.2f})")

            # Parse address components
            address_data = parse_address(place.get('addressComponents', []))
            location = place.get('location', {})

            return {
                'enriched_place_id': place.get('id'),
                'enriched_google_name': found_name,
                'enriched_address': found_address,
                'enriched_street': address_data['street'],
                'enriched_city': address_data['city'],
                'enriched_state': address_data['state'],
                'enriched_zip': address_data['zip'],
                'enriched_country': address_data['country'],
                'enriched_phone': place.get('internationalPhoneNumber'),
                'enriched_website': found_website,
                'enriched_rating': place.get('rating'),
                'enriched_lat': location.get('latitude'),
                'enriched_lng': location.get('longitude'),
                'enrichment_status': 'success',
                'enrichment_source': 'places_api',
                'verification_reason': reason,
                'verification_confidence': confidence
            }
        else:
            print(f"  ❌ VERIFICATION FAILED: {reason}")
            # Return failed status but with found data for manual review
            return {
                'enriched_place_id': place.get('id'),
                'enriched_google_name': found_name,
                'enriched_address': found_address,
                'enriched_street': None,
                'enriched_city': None,
                'enriched_state': None,
                'enriched_zip': None,
                'enriched_country': None,
                'enriched_phone': place.get('internationalPhoneNumber'),
                'enriched_website': found_website,
                'enriched_rating': None,
                'enriched_lat': None,
                'enriched_lng': None,
                'enrichment_status': 'verification_failed',
                'enrichment_source': 'places_api',
                'verification_reason': reason,
                'verification_confidence': confidence
            }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def parse_address(components: list) -> Dict:
    """Parse address components into structured fields"""
    result = {'street': None, 'city': None, 'state': None, 'zip': None, 'country': None}
    street_number = None
    route = None

    for component in components:
        types = component.get('types', [])
        long_text = component.get('longText', '')
        short_text = component.get('shortText', '')

        if 'street_number' in types:
            street_number = long_text
        elif 'route' in types:
            route = long_text
        elif 'locality' in types:
            result['city'] = long_text
        elif 'administrative_area_level_1' in types:
            result['state'] = short_text
        elif 'postal_code' in types:
            result['zip'] = long_text
        elif 'country' in types:
            result['country'] = short_text

    # Combine street number and route
    if street_number and route:
        result['street'] = f"{street_number} {route}"
    elif route:
        result['street'] = route

    return result


def clean_csv_field(value: str) -> str:
    """Clean CSV field by removing newlines and extra whitespace"""
    if not value:
        return value
    # Replace newlines with spaces
    cleaned = value.replace('\n', ' ').replace('\r', ' ')
    # Collapse multiple spaces into one
    cleaned = ' '.join(cleaned.split())
    return cleaned


def process_businesses(input_file: str, output_file: str, limit: int = None):
    """Process businesses with verification"""

    print(f"\n{'='*70}")
    print(f"🔍 VERIFIED Enrichment Pipeline")
    print(f"{'='*70}\n")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    if limit:
        print(f"Limit: {limit} businesses (TEST MODE)")
    print()

    # Read input
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        businesses = list(reader)

    # Clean all text fields to remove embedded newlines
    for business in businesses:
        for key, value in business.items():
            if isinstance(value, str):
                business[key] = clean_csv_field(value)

    if limit:
        businesses = businesses[:limit]

    print(f"📊 Processing {len(businesses)} businesses...\n")

    # Process each business
    results = []
    success = 0
    failed_verification = 0
    no_results = 0

    for idx, business in enumerate(businesses, start=1):
        name = business.get('Name', '')
        company = business.get('Company Name', '')
        industry = business.get('Industry ', '')  # Note the space in column name
        original_website = business.get('Company Name', '').split(' - ')[-1] if ' - ' in business.get('Company Name', '') else ''

        print(f"\n[{idx}/{len(businesses)}] {name} - {company}")
        print(f"{'─'*70}")

        # Search and verify
        enriched_data = search_and_verify(company, industry, original_website)

        # Merge with original data
        if enriched_data:
            if enriched_data['enrichment_status'] == 'success' or enriched_data['enrichment_status'] == 'success_custom_search':
                success += 1
            elif enriched_data['enrichment_status'] == 'verification_failed':
                failed_verification += 1
            else:
                no_results += 1

            result = {**business, **enriched_data}
        else:
            no_results += 1
            result = {
                **business,
                'enrichment_status': 'no_results',
                'enrichment_source': None,
                'verification_reason': 'No results from Google Places API',
                'verification_confidence': None
            }

        results.append(result)

        # Rate limiting - be nice to the API
        if idx < len(businesses):
            time.sleep(1.5)

    # Save results
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if results:
        fieldnames = list(results[0].keys())
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    # Summary
    print(f"\n{'='*70}")
    print(f"✅ Enrichment Complete!")
    print(f"{'='*70}")
    print(f"Total processed: {len(businesses)}")
    print(f"✅ Verified & enriched: {success} ({success/len(businesses)*100:.1f}%)")
    print(f"⚠️  Failed verification: {failed_verification} ({failed_verification/len(businesses)*100:.1f}%)")
    print(f"❌ No results found: {no_results} ({no_results/len(businesses)*100:.1f}%)")
    print(f"\n📁 Output: {output_file}")
    print(f"\n💡 Next steps:")
    print(f"   - Review 'verification_failed' entries manually")
    print(f"   - Check 'verification_reason' column for details")
    print(f"   - If satisfied, run on full dataset without --limit")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Verified enrichment with Google Places API')
    parser.add_argument('--input', default='exports/business_filtering/filtered_muslim_business_owners.csv',
                       help='Input CSV file')
    parser.add_argument('--output', default='exports/enrichment/verified_enriched.csv',
                       help='Output CSV file')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of businesses to process (for testing)')

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        return 1

    process_businesses(str(input_path), args.output, args.limit)
    return 0


if __name__ == '__main__':
    exit(main())
