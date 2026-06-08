#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Unified Flow & Volume Momentum Scanner.
Analyzes consecutive institutional flow streaks and matches individual stock volume averages
to identify Breakout (상승 돌파) and Pullback (눌림 수축) patterns.

Outputs:
  picks/cache/flow_volume_candidates.json
  obsidian/stock_log/04_candidate_boards/Flow Volume Candidates.md
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_FLOW_STREAK = ROOT / "picks" / "cache" / "flow_streak_candidates.json"
DEFAULT_FOREIGN_STREAK = ROOT / "picks" / "cache" / "foreign_streak_candidates.json"
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "flow_volume_candidates.json"
_obsidian_vault = os.environ.get("OBSIDIAN_VAULT_PATH")
DEFAULT_OBSIDIAN_NOTE = (
    Path(_obsidian_vault) / "stock_log" / "04_candidate_boards" / "Flow Volume Candidates.md"
    if _obsidian_vault
    else ROOT / "obsidian" / "stock_log" / "04_candidate_boards" / "Flow Volume Candidates.md"
)
KST = timezone(timedelta(hours=9))


def configure_stdio() -> None:
    """Prefer UTF-8 console output when supported."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> datetime:
    """Return current KST datetime."""
    return datetime.now(KST)


def read_json(path: Path) -> Dict[str, Any]:
    """Read JSON if present, otherwise return empty dict."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_flow_buyers(flow_streak_path: Path, foreign_streak_path: Path) -> Dict[str, Dict[str, Any]]:
    """Aggregate buying flow streak candidates from consecutive scanner cache files."""
    buyers = {}
    
    # 1. Load flow_streak_candidates
    if flow_streak_path.exists():
        try:
            data = json.loads(flow_streak_path.read_text(encoding="utf-8"))
            for item in (data.get("foreign_buy_candidates") or []):
                ticker = str(item.get("ticker", "")).zfill(6)
                buyers[ticker] = {
                    "ticker": ticker,
                    "name": item.get("name"),
                    "flow_types": ["Foreigner Streak"],
                    "net_flow_sum": item.get("net_flow_sum", 0),
                    "days": item.get("consecutive_days", 3)
                }
            for item in (data.get("pension_buy_candidates") or []):
                ticker = str(item.get("ticker", "")).zfill(6)
                if ticker in buyers:
                    buyers[ticker]["flow_types"].append("Pension Streak")
                    buyers[ticker]["net_flow_sum"] += item.get("net_flow_sum", 0)
                else:
                    buyers[ticker] = {
                        "ticker": ticker,
                        "name": item.get("name"),
                        "flow_types": ["Pension Streak"],
                        "net_flow_sum": item.get("net_flow_sum", 0),
                        "days": item.get("consecutive_days", 3)
                    }
        except Exception as exc:
            print(f"Warning: Failed to parse flow streak candidates: {exc}", file=sys.stderr)

    # 2. Load foreign_streak_candidates
    if foreign_streak_path.exists():
        try:
            data = json.loads(foreign_streak_path.read_text(encoding="utf-8"))
            for item in (data.get("candidates") or []):
                ticker = str(item.get("ticker", "")).zfill(6)
                if ticker in buyers:
                    if "Foreigner Streak" not in buyers[ticker]["flow_types"]:
                        buyers[ticker]["flow_types"].append("Foreigner Streak (CSV)")
                    buyers[ticker]["net_flow_sum"] = max(buyers[ticker]["net_flow_sum"], item.get("foreign_net_buy_sum", 0))
                else:
                    buyers[ticker] = {
                        "ticker": ticker,
                        "name": item.get("name"),
                        "flow_types": ["Foreigner Streak (CSV)"],
                        "net_flow_sum": item.get("foreign_net_buy_sum", 0),
                        "days": item.get("consecutive_foreign_buy_days", 3)
                    }
        except Exception as exc:
            print(f"Warning: Failed to parse foreign streak candidates: {exc}", file=sys.stderr)
            
    return buyers


def get_offline_data() -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Return mock datasets for testing."""
    mock_market = {
        "generated_at": now_kst().isoformat(),
        "mode": "offline_sample",
        "items": [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "price": 331000,
                "change_rate": 1.8,
                "volume": 3000000,
                "technical": {
                    "volume_avg20": 1500000.0,
                    "rsi14": 58.0
                },
                "flow": {
                    "foreign_net_buy_5d": 57000000000,
                    "institution_net_buy_5d": 1000000000
                }
            },
            {
                "ticker": "402340",
                "name": "SK스퀘어",
                "price": 1251000,
                "change_rate": -1.5,
                "volume": 30000,
                "technical": {
                    "volume_avg20": 100000.0,
                    "rsi14": 52.0
                },
                "flow": {
                    "foreign_net_buy_5d": 34000000000,
                    "institution_net_buy_5d": -500000000
                }
            },
            {
                "ticker": "000660",
                "name": "SK하이닉스",
                "price": 2120000,
                "change_rate": 0.2,
                "volume": 600000,
                "technical": {
                    "volume_avg20": 800000.0,
                    "rsi14": 49.0
                },
                "flow": {
                    "foreign_net_buy_5d": -12000000000,
                    "institution_net_buy_5d": 15000000000
                }
            }
        ]
    }
    
    mock_streaks = {
        "005930": {
            "ticker": "005930",
            "name": "삼성전자",
            "flow_types": ["Foreigner Streak (CSV)"],
            "net_flow_sum": 57000000000,
            "days": 4
        },
        "402340": {
            "ticker": "402340",
            "name": "SK스퀘어",
            "flow_types": ["Foreigner Streak (CSV)"],
            "net_flow_sum": 34000000000,
            "days": 4
        }
    }
    
    return mock_market, mock_streaks


def analyze_candidates(
    market_data: Dict[str, Any], 
    streak_buyers: Dict[str, Dict[str, Any]], 
    breakout_ratio: float, 
    contraction_ratio: float
) -> List[Dict[str, Any]]:
    """Filter and identify breakout and pullback stocks based on volume indicators."""
    candidates = []
    
    for item in market_data.get("items", []) or []:
        ticker = str(item.get("ticker", "")).zfill(6)
        name = item.get("name", "")
        price = item.get("price")
        change_rate = item.get("change_rate")
        volume = item.get("volume", 0)
        
        # Read technical volume average
        tech = item.get("technical") or {}
        volume_avg20 = tech.get("volume_avg20") or tech.get("avg_volume_20") or tech.get("volume_ma20")
        
        if volume_avg20 is None or volume_avg20 <= 0 or price is None or change_rate is None:
            continue
            
        volume_ratio = volume / volume_avg20
        
        # Check flow metrics
        flow = item.get("flow") or {}
        foreign_5d = flow.get("foreign_net_buy_5d") or flow.get("foreign_5d") or 0.0
        institution_5d = flow.get("institution_net_buy_5d") or flow.get("institution_5d") or 0.0
        pension_5d = flow.get("pension_net_buy_5d") or flow.get("pension_5d") or 0.0
        
        # Has institutional buying flow?
        is_streak_buyer = ticker in streak_buyers
        has_positive_5d_flow = (foreign_5d > 0) or (institution_5d > 0) or (pension_5d > 0)
        
        if not (is_streak_buyer or has_positive_5d_flow):
            continue
            
        flow_desc = []
        if is_streak_buyer:
            flow_desc.extend(streak_buyers[ticker]["flow_types"])
        if foreign_5d > 0:
            flow_desc.append("Foreigner 5D net-buy")
        if institution_5d > 0:
            flow_desc.append("Institution 5D net-buy")
        if pension_5d > 0:
            flow_desc.append("Pension 5D net-buy")
            
        pattern = None
        rationale = ""
        
        # Case 1: Breakout Confirmation (돌파 상승형)
        if change_rate >= 0.5 and volume_ratio >= breakout_ratio:
            pattern = "Breakout (돌파 상승)"
            rationale = f"메이저 수급 유입 및 가격 상승(+{change_rate:.2f}%) 조건 하에 당일 거래량이 20일 평균 대비 {volume_ratio:.1f}배 급증하며 상승 에너지를 입증함."
            
        # Case 2: Pullback Contraction (눌림 수축형)
        elif -4.0 <= change_rate <= 0.5 and volume_ratio <= contraction_ratio:
            pattern = "Pullback (눌림 수축)"
            rationale = f"메이저 수급 유입 상태에서 당일 가격 보합/조정({change_rate:.2f}%)을 거치는 중 거래량이 20일 평균 대비 {volume_ratio:.1f}배 수준으로 극도로 수축(매도 건조)됨."
            
        if pattern:
            candidates.append({
                "ticker": ticker,
                "name": name,
                "pattern": pattern,
                "price": price,
                "change_rate": round(change_rate, 2),
                "volume": volume,
                "volume_avg20": round(volume_avg20, 1),
                "volume_ratio": round(volume_ratio, 2),
                "flow_indicators": sorted(list(set(flow_desc))),
                "rsi14": tech.get("rsi14") or tech.get("rsi_14"),
                "rationale": rationale
            })
            
    # Sort candidates: Breakouts first, then Pullbacks, then by volume ratio
    candidates.sort(key=lambda x: (x["pattern"] != "Breakout (돌파 상승)", -x["volume_ratio"]))
    return candidates


def update_obsidian_note(note_path: Path, timestamp: str, candidates: List[Dict[str, Any]], mode: str) -> None:
    """Generate and write a beautiful candidate note in the Obsidian Vault."""
    note_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Obsidian YAML Frontmatter
    frontmatter = f"""---
title: "Flow Volume Candidates"
date: {timestamp[:10]}
type: candidate-board
status: active
owner: obsi
evidence_type: report
tags:
  - stock-orchestrator
  - flow-volume-momentum
  - candidates
---

# 📈 수급 & 거래량 통합 관심 종목 (Flow-Volume Candidates)

이 보고서는 메이저 수급(외국인, 기관, 연기금)의 유입 동향과 개별 종목의 거래량 비율(20일 평균 대비)을 다각도로 분석하여 **돌파 상승형** 및 **눌림 수축형** 관심 종목을 선별한 결과입니다.

* **최근 갱신일시**: `{timestamp} KST` (조회 모드: `{mode}`)

---

## 🚀 1. 돌파 상승형 종목 (Breakout Candidates)
*메이저 수급 유입과 거래량 급증이 동반된 가격 상승 국면 종목*

"""
    breakouts = [c for c in candidates if "Breakout" in c["pattern"]]
    if not breakouts:
        frontmatter += "*현재 기준 조건을 충족하는 돌파 상승형 종목이 없습니다.*\n"
    else:
        frontmatter += "| # | 종목명 | 종목코드 | 현재가 | 등락률 | 거래량 비율 | 수급 요인 | 분석 근거 |\n"
        frontmatter += "|---|---|:---:|:---:|:---:|:---:|---|---|\n"
        for i, c in enumerate(breakouts, 1):
            flow_str = ", ".join(c["flow_indicators"])
            frontmatter += f"| {i} | {c['name']} | `{c['ticker']}` | {c['price']:,}원 | `{c['change_rate']:+.2f}%` | **`{c['volume_ratio']:.2f}배`** | {flow_str} | {c['rationale']} |\n"

    frontmatter += """
---

## 💤 2. 눌림 수축형 종목 (Pullback Contraction Candidates)
*메이저 매수세 대기 상태에서 가격 조정 시 거래량이 극도로 감소한 눌림목 종목*

"""
    pullbacks = [c for c in candidates if "Pullback" in c["pattern"]]
    if not pullbacks:
        frontmatter += "*현재 기준 조건을 충족하는 눌림 수축형 종목이 없습니다.*\n"
    else:
        frontmatter += "| # | 종목명 | 종목코드 | 현재가 | 등락률 | 거래량 비율 | 수급 요인 | 분석 근거 |\n"
        frontmatter += "|---|---|:---:|:---:|:---:|:---:|---|---|\n"
        for i, c in enumerate(pullbacks, 1):
            flow_str = ", ".join(c["flow_indicators"])
            frontmatter += f"| {i} | {c['name']} | `{c['ticker']}` | {c['price']:,}원 | `{c['change_rate']:+.2f}%` | **`{c['volume_ratio']:.2f}배`** | {flow_str} | {c['rationale']} |\n"

    frontmatter += "\n---\n*본 리스트는 스크리닝 결과물이며 매매 추천이 아닙니다. 실제 거래 전 pre-trade 진입 가이드 및 리스크 체크리스트 통과가 권장됩니다.*\n"
    
    note_path.write_text(frontmatter, encoding="utf-8")


def print_markdown_report(timestamp: str, candidates: List[Dict[str, Any]], mode: str) -> None:
    """Print markdown report to stdout."""
    print(f"\n## 📈 수급 & 거래량 통합 관심 종목 스캔 결과 ({mode} 모드)")
    print(f"**스캔 기준시각**: {timestamp} KST")
    
    breakouts = [c for c in candidates if "Breakout" in c["pattern"]]
    pullbacks = [c for c in candidates if "Pullback" in c["pattern"]]
    
    print("\n### 🚀 돌파 상승형 관심 종목 (Breakout)")
    if not breakouts:
        print("  *조건을 충족하는 종목이 없습니다.*")
    else:
        print("| # | 종목명 | 종목코드 | 현재가 | 등락률 | 거래량 비율 | 수급 요인 |")
        print("|---|---|:---:|:---:|:---:|:---:|---|")
        for i, c in enumerate(breakouts, start=1):
            flow_str = ", ".join(c["flow_indicators"])
            print(f"| {i} | {c['name']} | {c['ticker']} | {c['price']:,}원 | {c['change_rate']:+.2f}% | **{c['volume_ratio']:.2f}배** | {flow_str} |")

    print("\n### 💤 눌림 수축형 관심 종목 (Pullback)")
    if not pullbacks:
        print("  *조건을 충족하는 종목이 없습니다.*")
    else:
        print("| # | 종목명 | 종목코드 | 현재가 | 등락률 | 거래량 비율 | 수급 요인 |")
        print("|---|---|:---:|:---:|:---:|:---:|---|")
        for i, c in enumerate(pullbacks, start=1):
            flow_str = ", ".join(c["flow_indicators"])
            print(f"| {i} | {c['name']} | {c['ticker']} | {c['price']:,}원 | {c['change_rate']:+.2f}% | **{c['volume_ratio']:.2f}배** | {flow_str} |")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Scan for flow & volume momentum candidates.")
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--flow-streak-path", default=str(DEFAULT_FLOW_STREAK))
    parser.add_argument("--foreign-streak-path", default=str(DEFAULT_FOREIGN_STREAK))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--obsidian-note-path", default=str(DEFAULT_OBSIDIAN_NOTE))
    parser.add_argument("--breakout-ratio", type=float, default=1.5, help="Volume ratio threshold for breakout (>=)")
    parser.add_argument("--contraction-ratio", type=float, default=0.6, help="Volume ratio threshold for contraction (<=)")
    parser.add_argument("--offline-sample", action="store_true", help="Run with deterministic sample data.")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        timestamp_str = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Load inputs based on mode
        if args.offline_sample:
            market_data, streak_buyers = get_offline_data()
            mode = "offline_sample"
        else:
            market_data = read_json(Path(args.market_snapshot_path))
            streak_buyers = load_flow_buyers(Path(args.flow_streak_path), Path(args.foreign_streak_path))
            mode = "live"
            
        # 2. Run analysis
        candidates = analyze_candidates(
            market_data, 
            streak_buyers, 
            args.breakout_ratio, 
            args.contraction_ratio
        )
        
        # 3. Save output JSON
        result_json = {
            "generated_at": now_kst().isoformat(timespec="seconds"),
            "mode": mode,
            "breakout_ratio_threshold": args.breakout_ratio,
            "contraction_ratio_threshold": args.contraction_ratio,
            "candidates": candidates,
            "summary": {
                "total": len(candidates),
                "breakout": len([c for c in candidates if "Breakout" in c["pattern"]]),
                "pullback": len([c for c in candidates if "Pullback" in c["pattern"]])
            }
        }
        write_json(Path(args.output_path), result_json)
        print(f"wrote {args.output_path}", file=sys.stderr)
        
        # 4. Save Obsidian Vault Note
        update_obsidian_note(Path(args.obsidian_note_path), timestamp_str, candidates, mode)
        print(f"updated Obsidian candidate board at {args.obsidian_note_path}", file=sys.stderr)
        
        # 5. Print markdown report to stdout
        print_markdown_report(timestamp_str, candidates, mode)
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
