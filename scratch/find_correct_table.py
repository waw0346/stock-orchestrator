#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re

url = "https://finance.naver.com/item/frgn.naver?code=207940&page=1"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": "https://finance.naver.com/"
    }
)

with urllib.request.urlopen(req, timeout=10) as res:
    html_content = res.read().decode("cp949", errors="replace")
    
    # Find all tables
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html_content, flags=re.IGNORECASE | re.DOTALL)
    print(f"Total tables found: {len(tables)}")
    
    for idx, table_content in enumerate(tables):
        # Print index and the first 300 characters
        print(f"\nTable {idx}:")
        print(table_content[:300].strip())
        print("-" * 40)
