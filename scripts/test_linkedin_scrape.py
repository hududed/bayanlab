#!/usr/bin/env python3
"""Test LinkedIn scraping"""

import requests
import re

url = "https://www.linkedin.com/company/boardroomeducation/about/"

response = requests.get(url, headers={
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}, timeout=10)

print(f"Status: {response.status_code}")
print(f"Content length: {len(response.text)}")
print(f"\nFirst 2000 chars:\n")
print(response.text[:2000])
print(f"\n\n{'='*80}")
print("SEARCHING FOR PATTERNS")
print('='*80)

# Search for key patterns
patterns = [
    ('Address (Primary)', r'Primary\s*\n\s*([^\n]+,\s*[A-Z]{2}\s+\d{5})'),
    ('Address (alt)', r'(\d+\s+[\w\s]+,\s*[\w\s]+,\s*[A-Z]{2}\s+\d{5})'),
    ('Phone (Phone\\n)', r'Phone\s*\n\s*(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})'),
    ('Phone (USA:)', r'USA:\s*\+?1?\s*(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})'),
    ('Email', r'Email:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'),
    ('Website', r'Website\s*\n\s*(https?://[^\s\n]+)'),
]

for name, pattern in patterns:
    match = re.search(pattern, response.text)
    if match:
        print(f"\n✅ {name}: {match.group(1)}")
    else:
        print(f"\n❌ {name}: Not found")

# Check if it's a login page
if 'Sign in' in response.text or 'authwall' in response.text.lower():
    print("\n⚠️  LinkedIn returned a login wall!")
