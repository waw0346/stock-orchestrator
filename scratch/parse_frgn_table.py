#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re
from bs4 import BeautifulSoup # bs4 is usually available or we can use regex

url = "https://finance.naver.com/item/frgn.naver?code=207940&page=1"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": "https://finance.naver.com/"
    }
)

def clean_num(text):
    text = re.sub(r"[^\d.+\-]", "", text)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0

try:
    with urllib.request.urlopen(req, timeout=10) as res:
        html_content = res.read().decode("cp949", errors="replace")
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Find the table with class 'type2'
        table = soup.find("table", class_="type2")
        if not table:
            print("Could not find table class type2")
            # Let's print some table classes
            tables = soup.find_all("table")
            for t in tables:
                print(f"Table classes: {t.get('class')}")
            sys.exit(1)
            
        rows = table.find_all("tr")
        parsed_rows = []
        for row in rows:
            # Check if this row has onMouseOver attribute
            if not row.get("onmouseover"):
                continue
            cells = row.find_all("td")
            if len(cells) < 8:
                continue
            
            date = cells[0].text.strip()
            close = clean_num(cells[1].text.strip())
            volume = clean_num(cells[4].text.strip())
            institution = clean_num(cells[5].text.strip())
            foreigner = clean_num(cells[6].text.strip())
            
            parsed_rows.append({
                "date": date,
                "close": close,
                "volume": volume,
                "institution": institution,
                "foreigner": foreigner
            })
            
        print(f"Parsed {len(parsed_rows)} rows from page 1:")
        for idx, r in enumerate(parsed_rows[:10]):
            print(f"{idx+1}. Date: {r['date']} | Close: {r['close']:,} | Vol: {r['volume']:,} | Inst: {r['institution']:+,} | Foreign: {r['foreigner']:+,}")
except Exception as e:
    print(f"Error: {e}")
