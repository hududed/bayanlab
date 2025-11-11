#!/usr/bin/env python3
"""
Enrich business owner data by searching Google for company information.

For each business owner, searches "[Company Name]" on Google and extracts:
- Address (city, state, zip)
- Phone number
- Website
- Business hours
- Google Maps location

Usage:
    python scripts/enrich_via_google.py --input exports/business_filtering/high_priority_owners.csv --limit 25

Requirements:
    pip install beautifulsoup4 requests
"""

import argparse
import csv
import re
import time
import json
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

# Headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}


def search_google(company_name: str, industry: str = None) -> Optional[Dict]:
    """
    Search Google for a company and extract location data.

    Returns dict with: address, city, state, zip, phone, website, hours
    """

    # Build search query
    query = f'"{company_name}"'
    if industry:
        query += f' {industry}'

    search_url = f"https://www.google.com/search?q={quote_plus(query)}"

    print(f"  Searching: {query}")

    try:
        # Add random delay to avoid rate limiting
        time.sleep(2 + (time.time() % 3))  # 2-5 second random delay

        response = requests.get(search_url, headers=HEADERS, timeout=10)

        if response.status_code != 200:
            print(f"  ⚠️  Google returned status {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        result = {
            'address': None,
            'city': None,
            'state': None,
            'zip': None,
            'phone': None,
            'website': None,
            'hours': None,
            'google_maps_url': None
        }

        # Method 1: Extract from Google Knowledge Panel (right side)
        # Look for address in <span> tags
        for span in soup.find_all('span', class_=re.compile('LrzXr')):
            text = span.get_text(strip=True)
            if is_address(text):
                result['address'] = text
                parsed = parse_address(text)
                result.update(parsed)
                break

        # Method 2: Look for phone number
        for a in soup.find_all('a', href=re.compile(r'tel:')):
            phone = a.get('href').replace('tel:', '').strip()
            result['phone'] = format_phone(phone)
            break

        # Alternative: Find phone in text
        if not result['phone']:
            phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            for text in soup.stripped_strings:
                match = re.search(phone_pattern, text)
                if match:
                    result['phone'] = format_phone(match.group())
                    break

        # Method 3: Extract website
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if 'url?q=' in href:
                url = href.split('url?q=')[1].split('&')[0]
                if is_valid_website(url):
                    result['website'] = url
                    break

        # Method 4: Look for Google Maps link
        for a in soup.find_all('a', href=re.compile(r'google.com/maps')):
            result['google_maps_url'] = a.get('href')
            break

        # Method 5: Extract hours (if available)
        hours_keywords = ['Open', 'Closed', 'Hours']
        for text in soup.stripped_strings:
            if any(kw in text for kw in hours_keywords) and ('AM' in text or 'PM' in text):
                result['hours'] = text
                break

        return result

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Error parsing: {e}")
        return None


def is_address(text: str) -> bool:
    """Check if text looks like an address."""
    # Must contain a number and a street indicator
    has_number = bool(re.search(r'\d+', text))
    has_street = bool(re.search(r'\b(St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Pkwy|Parkway|Unit|Suite)\b', text, re.IGNORECASE))
    has_state = bool(re.search(r'\b[A-Z]{2}\b', text))

    return has_number and (has_street or has_state)


def parse_address(address: str) -> Dict:
    """Parse address into components: city, state, zip."""

    result = {'city': None, 'state': None, 'zip': None}

    # Pattern: "City, STATE ZIP"
    match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5})', address)
    if match:
        result['city'] = match.group(1).strip()
        result['state'] = match.group(2).strip()
        result['zip'] = match.group(3).strip()

    return result


def format_phone(phone: str) -> str:
    """Format phone number to (XXX) XXX-XXXX."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone


def is_valid_website(url: str) -> bool:
    """Check if URL is a valid website (not Google, LinkedIn, etc.)."""
    exclude = ['google.com', 'facebook.com', 'linkedin.com', 'twitter.com', 'youtube.com']
    return url.startswith('http') and not any(ex in url for ex in exclude)


def enrich_business_owners(input_csv: Path, output_csv: Path, limit: int = None):
    """
    Read business owners CSV, enrich via Google search, save results.
    """

    enriched = []
    total = 0
    success = 0

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if limit:
            rows = rows[:limit]

        print(f"\n🔍 Enriching {len(rows)} businesses via Google search...\n")

        for idx, row in enumerate(rows, start=1):
            total += 1
            company = row.get('Company Name', '').strip()
            industry = row.get('Industry ', '').strip()
            name = row.get('Name', '').strip()

            print(f"[{idx}/{len(rows)}] {name} - {company}")

            if not company or company.lower() in ['n/a', 'student', 'unemployed']:
                print("  ⏭️  Skipping (no company)")
                enriched.append({**row, 'enrichment_status': 'skipped'})
                continue

            # Search Google
            google_data = search_google(company, industry)

            if google_data and (google_data['address'] or google_data['phone'] or google_data['website']):
                success += 1
                print(f"  ✅ Found: {google_data.get('city', 'N/A')}, {google_data.get('state', 'N/A')} | {google_data.get('phone', 'N/A')}")

                enriched.append({
                    **row,
                    'enriched_address': google_data.get('address'),
                    'enriched_city': google_data.get('city'),
                    'enriched_state': google_data.get('state'),
                    'enriched_zip': google_data.get('zip'),
                    'enriched_phone': google_data.get('phone'),
                    'enriched_website': google_data.get('website'),
                    'enriched_hours': google_data.get('hours'),
                    'google_maps_url': google_data.get('google_maps_url'),
                    'enrichment_status': 'success'
                })
            else:
                print("  ⚠️  No data found")
                enriched.append({**row, 'enrichment_status': 'failed'})

            # Rate limiting
            if idx % 10 == 0:
                print(f"\n  ⏸️  Pausing 30 seconds (rate limiting)...\n")
                time.sleep(30)

    # Save results
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if enriched:
        fieldnames = list(enriched[0].keys())

        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched)

        print(f"\n{'='*60}")
        print(f"✅ Enrichment complete!")
        print(f"{'='*60}")
        print(f"Total processed: {total}")
        print(f"Successfully enriched: {success} ({success/total*100:.1f}%)")
        print(f"Output: {output_csv}")
        print(f"\n💡 Next step: Filter for Colorado businesses")
        print(f"   grep -i 'colorado\\|CO' {output_csv} | wc -l")
        print(f"{'='*60}\n")
    else:
        print("❌ No data to save")


def main():
    parser = argparse.ArgumentParser(description='Enrich business owners via Google search')
    parser.add_argument('--input', type=str, default='exports/business_filtering/high_priority_owners.csv',
                        help='Input CSV file')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of businesses to enrich (for testing)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output CSV file (default: input_enriched.csv)')

    args = parser.parse_args()

    input_csv = Path(args.input)

    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    if args.output:
        output_csv = Path(args.output)
    else:
        output_csv = input_csv.parent / f"{input_csv.stem}_enriched.csv"

    print(f"📂 Input: {input_csv}")
    print(f"📂 Output: {output_csv}")
    if args.limit:
        print(f"📊 Limit: {args.limit} businesses")

    enrich_business_owners(input_csv, output_csv, args.limit)

    return 0


if __name__ == "__main__":
    exit(main())
