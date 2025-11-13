#!/usr/bin/env python3
"""
Simple website scraper that extracts text content WITHOUT requiring LLM API.
Just fetches and cleans website text for manual review.

Usage:
    python scripts/simple_scrape_websites.py
    python scripts/simple_scrape_websites.py --limit 5
"""

import argparse
import asyncio
import csv
import time
from pathlib import Path
import re

try:
    from crawl4ai import AsyncWebCrawler
except ImportError as e:
    print(f"❌ Error: crawl4ai not installed - {e}")
    print("Install with: uv add crawl4ai")
    import sys
    sys.exit(1)


def clean_text(text: str) -> str:
    """Clean and truncate text content"""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Truncate to 1000 chars for CSV
    if len(text) > 1000:
        text = text[:1000] + "..."
    return text.strip()


def extract_keywords(text: str, keywords: list) -> list:
    """Find keywords in text (case insensitive)"""
    found = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found.append(keyword)
    return found


async def scrape_website_simple(url: str) -> dict:
    """
    Scrape website and return raw text + basic analysis

    Returns:
        {
            'raw_text': str,  # First 1000 chars of cleaned text
            'char_count': int,
            'has_services': bool,
            'has_about': bool,
            'found_keywords': list
        }
    """

    print(f"  Scraping: {url}")

    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url, bypass_cache=True)

            if result.success and result.markdown:
                raw_text = result.markdown

                # Clean text
                cleaned = clean_text(raw_text)

                # Basic keyword detection
                service_keywords = [
                    'services', 'products', 'solutions', 'consulting',
                    'we offer', 'we provide', 'specializ', 'expertise'
                ]
                about_keywords = ['about', 'mission', 'vision', 'team', 'founded', 'established']

                found_services = extract_keywords(raw_text, service_keywords)
                found_about = extract_keywords(raw_text, about_keywords)

                print(f"  ✅ Scraped {len(raw_text)} chars")

                return {
                    'raw_text': cleaned,
                    'char_count': len(raw_text),
                    'has_services': bool(found_services),
                    'has_about': bool(found_about),
                    'found_keywords': ', '.join(set(found_services + found_about)),
                    'status': 'success'
                }
            else:
                print(f"  ⚠️  No content extracted")
                return {
                    'raw_text': '',
                    'char_count': 0,
                    'has_services': False,
                    'has_about': False,
                    'found_keywords': '',
                    'status': 'no_content'
                }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {
            'raw_text': '',
            'char_count': 0,
            'has_services': False,
            'has_about': False,
            'found_keywords': '',
            'status': f'error: {str(e)[:100]}'
        }


async def scrape_businesses(input_csv: Path, output_csv: Path, limit: int = None):
    """Scrape all businesses and save results"""

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

        print(f"\n🌐 Simple scraping {len(rows)} business websites...\n")
        print("NOTE: This scrapes raw text only (no LLM extraction)")
        print("      Review the 'raw_text' column for manual analysis\n")

        for idx, row in enumerate(rows, start=1):
            total += 1
            website = (row.get('enriched_website') or '').strip()
            company = (row.get('Company Name') or '').strip()
            name = (row.get('Name') or '').strip()

            print(f"[{idx}/{len(rows)}] {name[:30]} - {company[:30]}")

            if not website or website.lower() in ['none', 'n/a', '']:
                print("  ⏭️  Skipping (no website)")
                enriched.append({
                    **row,
                    'scraped_raw_text': '',
                    'scraped_char_count': 0,
                    'scraped_has_services': False,
                    'scraped_has_about': False,
                    'scraped_keywords': '',
                    'scrape_status': 'skipped_no_website'
                })
                skipped += 1
                continue

            # Scrape website
            result = await scrape_website_simple(website)

            if result['status'] == 'success':
                success += 1
            else:
                failed += 1

            enriched.append({
                **row,
                'scraped_raw_text': result['raw_text'],
                'scraped_char_count': result['char_count'],
                'scraped_has_services': result['has_services'],
                'scraped_has_about': result['has_about'],
                'scraped_keywords': result['found_keywords'],
                'scrape_status': result['status']
            })

            # Rate limiting
            await asyncio.sleep(2)

            # Progress updates
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
        print(f"✅ Simple scraping complete!")
        print(f"{'='*60}")
        print(f"Total processed: {total}")
        print(f"Successfully scraped: {success} ({success/total*100:.1f}%)")
        print(f"Skipped (no website): {skipped}")
        print(f"Failed: {failed}")
        print(f"\nOutput: {output_csv}")
        print(f"\n💡 Next steps:")
        print(f"   1. Open CSV and review 'scraped_raw_text' column")
        print(f"   2. Look for businesses with 'scraped_has_services' = True")
        print(f"   3. Manually extract services/info from raw text")
        print(f"   4. Or get OpenAI/Anthropic API key for automatic extraction")
        print(f"{'='*60}\n")
    else:
        print("❌ No data to save")


def main():
    parser = argparse.ArgumentParser(description='Simple website scraper (no LLM required)')
    parser.add_argument('--input', type=str, default='exports/enrichment/colorado_businesses.csv',
                        help='Input CSV file')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of websites to scrape')
    parser.add_argument('--output', type=str, default='exports/enrichment/colorado_simple_scraped.csv',
                        help='Output CSV file')

    args = parser.parse_args()

    input_csv = Path(args.input)

    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    output_csv = Path(args.output)

    print(f"📂 Input: {input_csv}")
    print(f"📂 Output: {output_csv}")
    if args.limit:
        print(f"📊 Limit: {args.limit} websites")

    asyncio.run(scrape_businesses(input_csv, output_csv, args.limit))

    return 0


if __name__ == "__main__":
    exit(main())
