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
    
    # Print the table with class 'type2'
    table_match = re.search(r"<table[^>]*class=['\"]type2['\"][^>]*>(.*?)</table>", html_content, flags=re.IGNORECASE | re.DOTALL)
    if table_match:
        table_html = table_match.group(1)
        print("Found table type2. Printing first 1000 characters of table content:")
        print(table_html[:1000])
        print("---")
        # Print all tr tags
        tr_tags = re.findall(r"<tr[^>]*>", table_html, flags=re.IGNORECASE)
        print(f"Total tr tags found: {len(tr_tags)}")
        for i, tr in enumerate(tr_tags[:10]):
            print(f"  tr {i}: {tr}")
    else:
        print("Could not find table with class type2")
