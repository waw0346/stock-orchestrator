import os
import re
import sys
import glob
import argparse
from datetime import datetime

# Set UTF-8 encoding on Windows to print emojis correctly
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(ROOT_DIR, "picks", "INDEX.md")
POSTMORTEM_DIR = os.path.join(ROOT_DIR, "picks", "postmortems")

# Template for Postmortem Analysis
POSTMORTEM_TEMPLATE = """---
ticker: "{ticker}"
name: "{name}"
entry_price: "{entry_price}"
close_price: "{close_price}"
realized_pnl: "{realized_pnl}"
close_date: "{close_date}"
type: postmortem
status: draft
---

# 🔍 {name} ({ticker}) 사후 복기 보고서 (Postmortem)

> [!CAUTION]
> **본 보고서는 감리반 에이전트(Audit Agent)에 의해 작성된 리스크 사후 분석 보고서입니다.**
> 본 픽은 총 **{realized_pnl}**의 대형 손실로 종결되었습니다. 실패 원인을 철저히 진단하여 동일 실수를 예방하고 투자 가이드를 보완합니다.

---

## 1. 📊 실패 현황 및 주요 지표
- **종목명 (코드):** {name} ({ticker})
- **최종 수익률:** {realized_pnl}
- **진입 가격 / 청산 가격:** {entry_price} / {close_price}
- **손절선 설정:** [투자 노트에서 설정한 손절 가격 기입]
- **청산 일자:** {close_date}

---

## 2. 📉 투자 가설의 설정 및 붕괴 과정 (Thesis Breakdown)
> [!NOTE]
> *원래 세웠던 투자 가설(Thesis)이 무엇이었으며, 어떤 시장/기업 악재로 인해 가설이 붕괴되었는지 시계열로 기술합니다.*

- **초기 진입 근거 (Thesis):**
  - 
- **가설 붕괴 시점 및 촉매 (Catalysts):**
  - 

---

## 3. 🚨 손절 지연 및 손실 확대 원인 분석 (Root Cause Analysis)
> [!WARNING]
> *정해진 손절 규칙이 제때 작동하지 않은 구체적인 이유를 분석합니다.*

- **시스템적 요인 (Data & Operations):**
  - [예: 모니터링 공백 발생, 가격 수집기 오작동, 주말/휴장일 수급 대응 지연 등]
- **인지적/심리적 오류 (Cognitive Biases):**
  - [예: 모멘텀(SpaceX 상장 등)에 대한 과도한 미련, 손실 회피 성향, 확증 편향 등]

---

## 4. 🧠 시스템적/의사결정 프로세스 오류 진단
- **포지션 크기 적합성:** [기본 비중 3~5% 제한 준수 여부 및 손절 시 총자산 허용 손실 0.5% 이내 성립 여부]
- **피드백 품질:** [리뷰 이력에서 경고가 반복되었음에도 매도하지 않은 구체적 판단 과정]

---

## 5. 🛠️ 향후 예방 및 투자 규칙 보완 조치 (Action Plan)
> [!IMPORTANT]
> *동일한 반복 실수를 방지하기 위해 투자 가이드라인(`INVESTMENT_POLICY.md`) 및 아키텍처에 보완할 구체적 액션 아이템입니다.*

- **1. 단기 모니터링 경보 강화:** [스톱로스 실시간 모니터링 스크립트 활용 등]
- **2. 포지션 청산 규율 강제화:** [종가 기준 손절선 하회 시 예외 없는 기계적 청산 룰 확립]
- **3. 투자 가이드라인(Investment Policy) 보완점:**
  - 

---
*감리반 작성일: {audit_date} | 대상 종목: {ticker}*
"""

def parse_percentage(text):
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    return None

def scan_for_large_losses():
    if not os.path.exists(INDEX_PATH):
        print(f"❌ Index file not found at {INDEX_PATH}")
        return []
    
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.splitlines()
    large_losses = []
    
    # Simple table parser
    for line in lines:
        line = line.strip()
        if not line.startswith("|") or "발행일" in line or "Tracked" in line or "---" in line:
            continue
            
        columns = [col.strip() for col in line.split("|")]
        if len(columns) < 7:
            continue
            
        # Parse return from columns
        # In Tracked Table: column 8 is Return (index 8)
        # In Closed Table: column 6 is Return (index 6)
        ret_val = None
        ticker = ""
        name = ""
        entry = ""
        close = ""
        close_date = ""
        
        # Check if the row belongs to Closed Table or Tracked Table
        if re.match(r"^\d{4}-\d{2}-\d{2}$", columns[1]): # date format
            ticker = columns[2].zfill(6)
            name = columns[3]
            
            # Let's inspect column 6 and 8
            r6 = parse_percentage(columns[6])
            r8 = parse_percentage(columns[8]) if len(columns) > 8 else None
            
            if r6 is not None:
                ret_val = r6
                entry = columns[4]
                close = columns[5]
                close_date = columns[1] # For closed picks, the row date is the published date, but let's check
                # Closed picks: columns[1]=date, columns[2]=ticker, columns[3]=name, columns[4]=entry, columns[5]=close, columns[6]=return
                # Let's extract close date from the reason text or use current year-month-day
                reason = columns[7] if len(columns) > 7 else ""
                date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)", reason)
                if date_match:
                    close_date = date_match.group(1)
            elif r8 is not None:
                ret_val = r8
                entry = columns[6]
                close = columns[7]
                close_date = columns[10] if len(columns) > 10 else columns[1] # last check date
                
        if ret_val is not None and ret_val <= -15.0:
            large_losses.append({
                "ticker": ticker,
                "name": name,
                "entry_price": entry,
                "close_price": close,
                "realized_pnl": f"{ret_val:.1f}%",
                "close_date": close_date
            })
            
    # Deduplicate by ticker
    seen = set()
    dedup = []
    for item in large_losses:
        if item["ticker"] not in seen:
            seen.add(item["ticker"])
            dedup.append(item)
            
    return dedup

def check_existing_postmortem(ticker):
    pattern = os.path.join(POSTMORTEM_DIR, f"*_{ticker}_postmortem.md")
    files = glob.glob(pattern)
    return len(files) > 0

def main():
    parser = argparse.ArgumentParser(description="Audit agent tool to scan for positions with losses >= 15%.")
    parser.add_argument("--DryRun", action="store_true", help="Scan only, do not write templates.")
    args = parser.parse_args()
    
    print("=== 감리반 에이전트: 대형 손실 종목 스캔 ===")
    
    losses = scan_for_large_losses()
    print(f"🔍 전체 이력에서 -15% 이하 대형 손실 종목 {len(losses)}건 감지됨.")
    
    os.makedirs(POSTMORTEM_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for item in losses:
        ticker = item["ticker"]
        name = item["name"]
        realized_pnl = item["realized_pnl"]
        
        print(f"\n[대상 발견] {name} ({ticker}) | 손실율: {realized_pnl} | 청산일: {item['close_date']}")
        
        if check_existing_postmortem(ticker):
            print(f"  ✅ 이미 {ticker}에 대한 사후 복기 보고서가 존재합니다. (패스)")
            continue
            
        file_name = f"{item['close_date']}_{ticker}_postmortem.md"
        file_path = os.path.join(POSTMORTEM_DIR, file_name)
        
        file_content = POSTMORTEM_TEMPLATE.format(
            ticker=ticker,
            name=name,
            entry_price=item["entry_price"],
            close_price=item["close_price"],
            realized_pnl=realized_pnl,
            close_date=item["close_date"],
            audit_date=today_str
        )
        
        if args.DryRun:
            print(f"  [DryRun] {file_name} 사후 복기 초안 파일을 생성할 예정입니다.")
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"  📝 감리 초안 파일 생성 완료: picks/postmortems/{file_name}")

if __name__ == "__main__":
    main()
