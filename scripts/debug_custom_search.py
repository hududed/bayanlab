#!/usr/bin/env python3
"""Debug script to see raw Custom Search API response"""

import requests
import os
import json
import re
from pathlib import Path

# Load from .env manually
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

CUSTOM_SEARCH_API_KEY = os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY')
CUSTOM_SEARCH_ENGINE_ID = os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')

company_name = "GBAC Global Board Advisors Corp"
query = f'"{company_name}" contact'

url = "https://www.googleapis.com/customsearch/v1"
params = {
    'key': CUSTOM_SEARCH_API_KEY,
    'cx': CUSTOM_SEARCH_ENGINE_ID,
    'q': query,
    'num': 3
}

response = requests.get(url, params=params)
data = response.json()

print("=" * 80)
print("RAW CUSTOM SEARCH API RESPONSE")
print("=" * 80)
print(f"\nQuery: {query}\n")
print(f"Status: {response.status_code}\n")

if 'items' in data:
    for idx, item in enumerate(data['items'], 1):
        print(f"\n{'─' * 80}")
        print(f"Result #{idx}")
        print(f"{'─' * 80}")
        print(f"Title: {item.get('title', 'N/A')}")
        print(f"Link: {item.get('link', 'N/A')}")
        print(f"\nSnippet:")
        print(item.get('snippet', 'N/A'))
else:
    print("No items found in response")
    print(f"\nFull response:\n{json.dumps(data, indent=2)}")

# Test combined text extraction
if 'items' in data:
    combined_text = ""
    for item in data['items'][:3]:
        snippet = item.get('snippet', '')
        combined_text += f" {snippet}"

    print(f"\n{'=' * 80}")
    print("COMBINED TEXT FOR REGEX EXTRACTION")
    print(f"{'=' * 80}")
    print(combined_text)

    # Test regex patterns
    print(f"\n{'=' * 80}")
    print("REGEX EXTRACTION RESULTS")
    print(f"{'=' * 80}")

    # Address
    address_match = re.search(r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Court|Ct|Lane|Ln|Boulevard|Blvd)[,\s]+[\w\s]+,\s+[A-Z]{2}\s+\d{5}', combined_text)
    if address_match:
        print(f"✅ Address found: {address_match.group(0)}")
    else:
        print("❌ Address NOT found with current regex")

    # Phone (current pattern)
    phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', combined_text)
    if phone_match:
        print(f"✅ Phone found (current): {phone_match.group(0)}")
    else:
        print("❌ Phone NOT found with current regex")

    # Try different phone patterns
    print(f"\n📱 Testing different phone patterns:")
    phone_patterns = [
        (r'\+\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', 'International with +'),
        (r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', 'US format (current)'),
        (r'\d{3}[-.\s]\d{3}[-.\s]\d{4}', 'Simple format'),
    ]

    for pattern, desc in phone_patterns:
        matches = re.findall(pattern, combined_text)
        if matches:
            print(f"  ✅ {desc}: {matches}")

    # Email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, combined_text)
    if emails:
        print(f"\n📧 Emails found: {emails}")
    else:
        print("\n❌ No emails found")
