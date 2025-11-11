#!/usr/bin/env python3
"""
Deep scrape business websites using Crawl4AI + LLM extraction.

For each business website, extracts:
- Services offered (list)
- Business description
- Service area (cities/regions served)
- Years in business
- Team size
- Certifications/licenses

Usage:
    python scripts/deep_scrape_websites.py
    python scripts/deep_scrape_websites.py --input colorado_businesses.csv --limit 10

Requirements:
    uv add crawl4ai openai
    OPENAI_API_KEY in .env (or use Claude API)
"""

import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

try:
    from crawl4ai import WebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
except ImportError:
    print("❌ Error: crawl4ai not installed")
    print("Install with: uv add crawl4ai")
    exit(1)

# Check for API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
    print("❌ Error: No LLM API key found")
    print("Add to .env: OPENAI_API_KEY=your_key or ANTHROPIC_API_KEY=your_key")
    exit(1)

# Configure LLM provider
if OPENAI_API_KEY:
    LLM_PROVIDER = "openai/gpt-4o-mini"  # Cheap & fast
    API_TOKEN = OPENAI_API_KEY
elif ANTHROPIC_API_KEY:
    LLM_PROVIDER = "anthropic/claude-3-haiku-20240307"
    API_TOKEN = ANTHROPIC_API_KEY


def scrape_website(url: str) -> Optional[Dict]:
    """
    Scrape a business website and extract structured data using LLM.

    Returns:
        Dict with: services, description, service_area, years_in_business, team_size, certifications
    """

    print(f"  Scraping: {url}")

    try:
        # Configure LLM extraction
        extraction_strategy = LLMExtractionStrategy(
            provider=LLM_PROVIDER,
            api_token=API_TOKEN,
            instruction="""
            Extract the following information from this business website:

            1. **services**: List of services offered (array of strings). Be specific.
            2. **description**: Brief business description or "about" text (1-2 sentences)
            3. **service_area**: Geographic areas served (cities, regions, or "nationwide")
            4. **years_in_business**: How many years in business (number) or "since YEAR"
            5. **team_size**: Number of employees/team members (number or range like "10-50")
            6. **certifications**: Licenses, certifications, or credentials (array)
            7. **contact_email**: Email address if found
            8. **contact_phone**: Phone number if different from Google

            Return ONLY valid JSON with these exact keys. If information not found, use null.

            Example:
            {
              "services": ["Plumbing", "Drain cleaning", "Water heater installation"],
              "description": "Family-owned plumbing company serving Denver metro since 1995",
              "service_area": "Denver, Aurora, Lakewood",
              "years_in_business": "since 1995",
              "team_size": "15",
              "certifications": ["Licensed Plumber", "Insured", "BBB Accredited"],
              "contact_email": "info@example.com",
              "contact_phone": "(303) 555-1234"
            }
            """,
            extraction_type="schema",
            schema={
                "type": "object",
                "properties": {
                    "services": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                    "service_area": {"type": "string"},
                    "years_in_business": {"type": "string"},
                    "team_size": {"type": "string"},
                    "certifications": {"type": "array", "items": {"type": "string"}},
                    "contact_email": {"type": "string"},
                    "contact_phone": {"type": "string"}
                }
            }
        )

        # Initialize crawler
        crawler = WebCrawler()
        crawler.warmup()

        # Crawl the website
        result = crawler.run(
            url=url,
            extraction_strategy=extraction_strategy,
            bypass_cache=True
        )

        # Parse extracted content
        if result.extracted_content:
            extracted = json.loads(result.extracted_content)
            print(f"  ✅ Extracted: {len(extracted.get('services', []))} services")
            return extracted
        else:
            print(f"  ⚠️  No content extracted")
            return None

    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def deep_scrape_businesses(input_csv: Path, output_csv: Path, limit: Optional[int] = None):
    """
    Read enriched businesses CSV, scrape websites, save results.
    """

    enriched = []
    total = 0
    success = 0
    skipped = 0
    failed = 0

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if limit:
            rows = rows[:limit]

        print(f"\n🌐 Deep scraping {len(rows)} business websites with Crawl4AI + LLM...\n")
        print(f"Using LLM: {LLM_PROVIDER}\n")

        for idx, row in enumerate(rows, start=1):
            total += 1
            website = row.get('enriched_website', '').strip()
            company = row.get('Company Name', '').strip()
            name = row.get('Name', '').strip()

            print(f"[{idx}/{len(rows)}] {name} - {company}")

            if not website or website.lower() in ['none', 'n/a']:
                print("  ⏭️  Skipping (no website)")
                enriched.append({**row, 'scrape_status': 'skipped', 'skip_reason': 'no_website'})
                skipped += 1
                continue

            # Scrape website
            scraped_data = scrape_website(website)

            if scraped_data:
                success += 1

                # Format services and certifications as comma-separated
                services_str = ', '.join(scraped_data.get('services', [])) if scraped_data.get('services') else None
                certs_str = ', '.join(scraped_data.get('certifications', [])) if scraped_data.get('certifications') else None

                enriched.append({
                    **row,
                    'scraped_services': services_str,
                    'scraped_description': scraped_data.get('description'),
                    'scraped_service_area': scraped_data.get('service_area'),
                    'scraped_years_in_business': scraped_data.get('years_in_business'),
                    'scraped_team_size': scraped_data.get('team_size'),
                    'scraped_certifications': certs_str,
                    'scraped_contact_email': scraped_data.get('contact_email'),
                    'scraped_contact_phone': scraped_data.get('contact_phone'),
                    'scrape_status': 'success'
                })
            else:
                failed += 1
                enriched.append({**row, 'scrape_status': 'failed'})

            # Rate limiting (be nice to websites)
            time.sleep(2)  # 2 second delay between requests

            # Progress updates every 5 businesses
            if idx % 5 == 0:
                print(f"\n  📊 Progress: {success}/{total} successful ({success/total*100:.1f}%)\n")

    # Save results
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if enriched:
        fieldnames = list(enriched[0].keys())

        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched)

        print(f"\n{'='*60}")
        print(f"✅ Deep scraping complete!")
        print(f"{'='*60}")
        print(f"Total processed: {total}")
        print(f"Successfully scraped: {success} ({success/total*100:.1f}%)")
        print(f"Skipped (no website): {skipped}")
        print(f"Failed: {failed}")
        print(f"\nOutput: {output_csv}")
        print(f"\n💡 Next step: Manual QA")
        print(f"   - Review output CSV")
        print(f"   - Verify phone numbers work")
        print(f"   - Confirm services match ProWasl")
        print(f"   - Add to business_canonical table")
        print(f"{'='*60}\n")
    else:
        print("❌ No data to save")


def main():
    parser = argparse.ArgumentParser(description='Deep scrape business websites with Crawl4AI + LLM')
    parser.add_argument('--input', type=str, default='exports/enrichment/colorado_businesses.csv',
                        help='Input CSV file (must have enriched_website column)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of websites to scrape (for testing)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output CSV file')

    args = parser.parse_args()

    input_csv = Path(args.input)

    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    if args.output:
        output_csv = Path(args.output)
    else:
        output_csv = Path('exports/enrichment/fully_enriched_colorado.csv')

    print(f"📂 Input: {input_csv}")
    print(f"📂 Output: {output_csv}")
    if args.limit:
        print(f"📊 Limit: {args.limit} websites")

    deep_scrape_businesses(input_csv, output_csv, args.limit)

    return 0


if __name__ == "__main__":
    exit(main())
