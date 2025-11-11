#!/usr/bin/env python3
"""
Filter Muslim Professionals networking sheet to identify high-potential business owners.

Usage:
    python scripts/filter_business_owners.py

Outputs:
    - exports/high_priority_owners.csv - Tier 1: Business owners in service industries
    - exports/service_businesses.csv - Tier 2: All service industry professionals
    - exports/colorado_businesses.csv - Tier 3: Colorado-based businesses
    - exports/all_filtered.csv - Combined deduplicated list
"""

import csv
import re
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict

# Filtering criteria
OWNER_KEYWORDS = [
    'owner', 'founder', 'ceo', 'president', 'principal', 'co-owner',
    'cofounder', 'co-founder', 'managing partner', 'proprietor'
]

FREELANCE_KEYWORDS = [
    'freelance', 'independent', 'contractor', 'self-employed',
    'consultant', 'freelancer'
]

SERVICE_INDUSTRIES = [
    # Home services
    'construction', 'contractor', 'contracting', 'plumbing', 'plumber',
    'electrical', 'electrician', 'hvac', 'heating', 'cooling',
    'landscaping', 'lawn care', 'cleaning', 'janitorial',
    'painting', 'painter', 'roofing', 'roofer', 'carpentry', 'carpenter',
    'handyman', 'repair', 'maintenance', 'remodeling', 'renovation',

    # Real estate & property
    'real estate', 'property', 'realtor', 'broker', 'property management',

    # Professional services
    'consulting', 'consultant', 'legal', 'law', 'accounting', 'tax',
    'financial', 'insurance', 'marketing', 'design', 'architecture',
    'engineering', 'it services', 'software consulting',

    # Personal services
    'catering', 'event planning', 'photography', 'videography',
    'tutoring', 'coaching', 'training', 'health', 'wellness',
    'fitness', 'beauty', 'salon', 'barber', 'spa'
]

COLORADO_KEYWORDS = [
    # Major cities (use word boundaries to avoid partial matches)
    r'\bdenver\b', r'\bboulder\b', r'\bcolorado springs\b', r'\bfort collins\b',
    r'\baurora\b', r'\blakewood\b', r'\bthornton\b', r'\barvada\b',
    r'\bwestminster\b', r'\bpueblo\b', r'\bcentennial\b',
    r'\bhighlands ranch\b', r'\bcastle rock\b', r'\blongmont\b', r'\bloveland\b',

    # More Colorado cities
    r'\bgreeley\b', r'\bbroomfield\b', r'\bcommerce city\b', r'\bparker\b',
    r'\blittleton\b', r'\bwheat ridge\b', r'\benglewoo\b', r'\bwheat ridge\b',
    r'\bgolden\b', r'\blafayette\b', r'\blouisville\b', r'\bsuperior\b',
    r'\bcolorado\b',  # Full word "Colorado"

    # Metro areas
    r'\bfront range\b', r'\bdenver metro\b', r'\bdenver area\b',

    # Never match: "co" alone (too many false positives with Company, Co-Founder)
]


def clean_text(text: str) -> str:
    """Normalize text for matching."""
    if not text:
        return ''
    return text.lower().strip()


def contains_keyword(text: str, keywords: List[str]) -> bool:
    """Check if text contains any keyword (case-insensitive)."""
    text_lower = clean_text(text)
    return any(keyword in text_lower for keyword in keywords)


def contains_keyword_regex(text: str, keywords: List[str]) -> bool:
    """Check if text contains any keyword using regex."""
    text_lower = clean_text(text)
    return any(re.search(keyword, text_lower) for keyword in keywords)


def score_row(row: Dict[str, str]) -> Dict[str, any]:
    """Score a row based on filtering criteria."""
    title = clean_text(row.get('Title/Position', ''))
    company = clean_text(row.get('Company Name', ''))
    industry = clean_text(row.get('Industry ', ''))  # Note trailing space in CSV header
    reason = clean_text(row.get('Reason for Joining', ''))
    bio = clean_text(row.get('Get to know me! ', ''))  # Note trailing space
    name = clean_text(row.get('Name', ''))

    # Check all text fields for Colorado mentions
    all_text = f"{bio} {reason} {title}".lower()

    scores = {
        'is_owner': contains_keyword(title, OWNER_KEYWORDS),
        'is_freelance': contains_keyword(title, FREELANCE_KEYWORDS),
        'is_service_industry': contains_keyword(industry, SERVICE_INDUSTRIES) or
                              contains_keyword(title, SERVICE_INDUSTRIES),
        'is_colorado': contains_keyword_regex(all_text, COLORADO_KEYWORDS),
        'has_company': bool(company and company not in ['n/a', 'student', 'unemployed']),
    }

    # Calculate tier
    if scores['is_owner'] and scores['is_service_industry']:
        tier = 1  # High priority
    elif scores['is_owner']:
        tier = 2  # Business owner, any industry
    elif scores['is_service_industry'] and (scores['is_freelance'] or scores['has_company']):
        tier = 3  # Service industry professional
    elif scores['is_colorado'] and scores['has_company']:
        tier = 4  # Colorado-based
    else:
        tier = 5  # Low priority

    scores['tier'] = tier
    return scores


def filter_professionals(input_csv: Path) -> Dict[str, List[Dict]]:
    """Filter professionals into different tiers."""

    results = {
        'tier1_high_priority': [],      # Owners + Service industry
        'tier2_all_owners': [],          # All business owners
        'tier3_service_industry': [],    # Service industry (non-owners)
        'tier4_colorado': [],            # Colorado-based
        'all_filtered': []               # Combined list (tiers 1-3)
    }

    stats = defaultdict(int)

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, start=1):
            stats['total'] += 1

            # Skip students
            if 'student' in clean_text(row.get('Industry ', '')):
                stats['skipped_students'] += 1
                continue

            scores = score_row(row)

            # Add tier to row for export
            row['tier'] = scores['tier']
            row['is_owner'] = scores['is_owner']
            row['is_service_industry'] = scores['is_service_industry']
            row['is_colorado'] = scores['is_colorado']

            # Categorize
            if scores['tier'] == 1:
                results['tier1_high_priority'].append(row)
                results['all_filtered'].append(row)
                stats['tier1'] += 1

            if scores['is_owner']:
                results['tier2_all_owners'].append(row)
                if scores['tier'] > 1:
                    results['all_filtered'].append(row)
                stats['owners'] += 1

            if scores['is_service_industry'] and not scores['is_owner']:
                results['tier3_service_industry'].append(row)
                results['all_filtered'].append(row)
                stats['service_industry'] += 1

            if scores['is_colorado']:
                results['tier4_colorado'].append(row)
                stats['colorado'] += 1

    # Deduplicate all_filtered (by name)
    seen_names = set()
    deduplicated = []
    for row in results['all_filtered']:
        name = row.get('Name', '').strip()
        if name and name not in seen_names:
            seen_names.add(name)
            deduplicated.append(row)
    results['all_filtered'] = deduplicated

    # Print statistics
    print("\n" + "="*60)
    print("FILTERING RESULTS")
    print("="*60)
    print(f"Total records processed: {stats['total']:,}")
    print(f"Students skipped: {stats['skipped_students']:,}")
    print(f"\nTier 1 (High Priority - Owners + Service): {stats['tier1']:,}")
    print(f"Tier 2 (All Business Owners): {stats['owners']:,}")
    print(f"Tier 3 (Service Industry Non-Owners): {stats['service_industry']:,}")
    print(f"Tier 4 (Colorado-based): {stats['colorado']:,}")
    print(f"\nCombined filtered list: {len(results['all_filtered']):,}")
    print("="*60 + "\n")

    return results, stats


def export_results(results: Dict[str, List[Dict]], output_dir: Path):
    """Export filtered results to CSV files."""

    output_dir.mkdir(exist_ok=True)

    exports = {
        'high_priority_owners.csv': results['tier1_high_priority'],
        'all_business_owners.csv': results['tier2_all_owners'],
        'service_industry_professionals.csv': results['tier3_service_industry'],
        'colorado_businesses.csv': results['tier4_colorado'],
        'all_filtered_combined.csv': results['all_filtered'],
    }

    for filename, data in exports.items():
        if not data:
            print(f"⚠️  Skipping {filename} (no data)")
            continue

        output_path = output_dir / filename

        # Get fieldnames from first row + our added fields
        fieldnames = list(data[0].keys())

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        print(f"✅ Exported {len(data):,} records to {output_path}")

    print()


def show_sample(results: Dict[str, List[Dict]]):
    """Show sample results from each tier."""

    print("\n" + "="*60)
    print("SAMPLE RESULTS")
    print("="*60)

    # Tier 1 samples
    if results['tier1_high_priority']:
        print("\n📊 TIER 1: High Priority (Owners + Service Industry)")
        print("-" * 60)
        for row in results['tier1_high_priority'][:5]:
            print(f"  {row.get('Name', 'N/A')}")
            print(f"    Title: {row.get('Title/Position', 'N/A')}")
            print(f"    Company: {row.get('Company Name', 'N/A')}")
            print(f"    Industry: {row.get('Industry ', 'N/A')}")
            print()

    # Owner samples
    if results['tier2_all_owners']:
        print("\n📊 TIER 2: All Business Owners (Any Industry)")
        print("-" * 60)
        for row in results['tier2_all_owners'][:5]:
            print(f"  {row.get('Name', 'N/A')}")
            print(f"    Title: {row.get('Title/Position', 'N/A')}")
            print(f"    Company: {row.get('Company Name', 'N/A')}")
            print(f"    Industry: {row.get('Industry ', 'N/A')}")
            print()

    print("="*60 + "\n")


def main():
    """Main execution."""

    # Paths
    project_root = Path(__file__).parent.parent
    input_csv = project_root / "backend" / "data" / "businesses" / "muslimprofessionals_co.csv"
    output_dir = project_root / "exports" / "business_filtering"

    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    print(f"📂 Reading from: {input_csv}")
    print(f"📂 Exporting to: {output_dir}")

    # Filter
    results, stats = filter_professionals(input_csv)

    # Export
    export_results(results, output_dir)

    # Show samples
    show_sample(results)

    print("✅ Filtering complete!")
    print(f"\n💡 Next steps:")
    print(f"   1. Review {output_dir}/high_priority_owners.csv")
    print(f"   2. Begin LinkedIn enrichment on top 25-50 profiles")
    print(f"   3. Draft outreach message for Muslim Professionals Slack")
    print(f"   4. See docs/business_enrichment_strategy.md for full plan\n")

    return 0


if __name__ == "__main__":
    exit(main())
