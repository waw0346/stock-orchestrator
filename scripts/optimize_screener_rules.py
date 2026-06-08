#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Analyze historical pick returns and current market conditions to optimize screener parameters dynamically.

Outputs:
  picks/cache/dynamic_rules_config.json
  obsidian/stock_log/10_strategy_playbooks/Dynamic Rules Log.md
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "picks" / "INDEX.md"
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_CONFIG = ROOT / "picks" / "cache" / "dynamic_rules_config.json"
_obsidian_vault = os.environ.get("OBSIDIAN_VAULT_PATH")
DEFAULT_OBSIDIAN_LOG = (
    Path(_obsidian_vault) / "stock_log" / "10_strategy_playbooks" / "Dynamic Rules Log.md"
    if _obsidian_vault
    else ROOT / "obsidian" / "stock_log" / "10_strategy_playbooks" / "Dynamic Rules Log.md"
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


def parse_closed_picks(index_path: Path) -> Tuple[float, float, int]:
    """Parse INDEX.md to return (win_rate_pct, average_return_pct, closed_count)."""
    wins = 0
    total_pnl = 0.0
    count = 0
    
    if not index_path.exists():
        return 50.0, 0.0, 0
        
    lines = index_path.read_text(encoding="utf-8").splitlines()
    in_closed_section = False
    
    for line in lines:
        if "## Closed 픽" in line:
            in_closed_section = True
            continue
        if in_closed_section and line.startswith("## "):
            in_closed_section = False
            continue
        if not in_closed_section:
            continue
            
        if line.startswith("|") and not line.startswith("|--") and "발행일" not in line:
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 8:
                pnl_text = cols[6].replace("%", "").replace("+", "").strip()
                if pnl_text == "-" or not pnl_text:
                    continue
                try:
                    pnl = float(pnl_text)
                    count += 1
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1
                except ValueError:
                    pass
    if count == 0:
        return 50.0, 0.0, 0
    win_rate = (wins / count) * 100.0
    avg_return = total_pnl / count
    return win_rate, avg_return, count


def get_market_average_return(market_path: Path) -> float:
    """Calculate the average change rate of the universe in market snapshot."""
    if not market_path.exists():
        return 0.0
    market_data = read_json(market_path)
    items = market_data.get("items") or []
    if not items:
        return 0.0
    total_rate = 0.0
    count = 0
    for item in items:
        rate = item.get("change_rate")
        if rate is not None:
            try:
                total_rate += float(rate)
                count += 1
            except ValueError:
                pass
    if count == 0:
        return 0.0
    return total_rate / count


def decide_scenario(avg_rate: float, win_rate: float) -> Tuple[str, Dict[str, Any], str]:
    """Decide on a scenario and map optimized parameters and rationale."""
    # Scenario A: Panic Risk-Off
    if avg_rate <= -4.0 or win_rate < 50.0:
        params = {
            "flow_streak_consecutive_days": 4,
            "kelly_sizing_factor": 0.2,
            "pullback_rsi_max": 65,
            "pullback_sharp_drop_max": -15,
            "top_limit": 50
        }
        rationale = "시장 급락(평균 등락률 -4.0% 이하) 또는 픽 성과 부진(승률 50% 미만)으로 인한 극단적 위험 회피 국면(Panic Risk-Off). 매매 비중을 절반 이하로 줄이고 스캐너 기준을 대폭 강화하여 자산을 보수적으로 보호합니다."
        return "Panic Risk-Off", params, rationale
        
    # Scenario B: Correction/Neutral
    elif -4.0 < avg_rate <= 0.0 or 50.0 <= win_rate < 60.0:
        params = {
            "flow_streak_consecutive_days": 3,
            "kelly_sizing_factor": 0.3,
            "pullback_rsi_max": 70,
            "pullback_sharp_drop_max": -18,
            "top_limit": 100
        }
        rationale = "시장 조정기 또는 성과 정체기(승률 50%~60%). 비중을 다소 하향 조정하고 보수적인 진입 장벽을 설정하여 시장 안정을 대기합니다."
        return "Correction/Neutral", params, rationale
        
    # Scenario C: Risk-On
    else:
        params = {
            "flow_streak_consecutive_days": 3,
            "kelly_sizing_factor": 0.5,
            "pullback_rsi_max": 75,
            "pullback_sharp_drop_max": -20,
            "top_limit": 100
        }
        rationale = "시장 안정화 및 양호한 성과(승률 60% 이상). 표준 켈리 공식 비중과 표준 스캐너 임계치를 적용하여 적극적으로 시장 기회를 추적합니다."
        return "Risk-On", params, rationale


def update_obsidian_log(log_path: Path, date_str: str, avg_rate: float, win_rate: float, avg_return: float, closed_count: int, regime: str, params: Dict[str, Any], rationale: str) -> None:
    """Append the optimization run details to the Obsidian strategy log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize note if not present
    if not log_path.exists():
        header = """---
title: "Dynamic Rules Log"
type: strategy-playbook
status: active
owner: obsi
tags:
  - stock-orchestrator
  - dynamic-rules
---

# ⚙️ 스크리너 매개변수 동적 최적화 로그 (Dynamic Rules Log)

이 일지는 시스템이 과거 투자 성과(INDEX.md 승률)와 당일 시장 등락률(Market Regime)을 바탕으로 스크리너 임계치를 동적으로 자동 조정한 이력을 기록합니다.

## 최적화 이력
"""
        log_path.write_text(header, encoding="utf-8")
        
    # Build run entry
    entry = f"""
### 📅 {date_str} 최적화 실행
* **시장 평균 등락률**: `{avg_rate:.2f}%`
* **최근 청산 종목 승률**: `{win_rate:.1f}%` (평균 수익률: `{avg_return:.2f}%`, 총 `{closed_count}`개 종목)
* **판정된 시장 시나리오**: **`{regime}`**
* **조정된 매개변수**:
  * 외국인/연기금 연속 수급 일수 (`flow_streak_consecutive_days`): **`{params['flow_streak_consecutive_days']}`일** (기본 3일)
  * 매매 비중 계수 (`kelly_sizing_factor`): **`{params['kelly_sizing_factor']}`** (기본 0.5)
  * 풀백 최대 허용 RSI (`pullback_rsi_max`): **`{params['pullback_rsi_max']}`** (기본 75)
  * 풀백 당일 최대 하락폭 제약 (`pullback_sharp_drop_max`): **`{params['pullback_sharp_drop_max']}%`** (기본 -20%)
  * 수급 수집 랭킹 한도 (`top_limit`): **`{params['top_limit']}`개** (기본 100개)
* **최적화 근거**: {rationale}
"""
    
    # Append to log
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def print_markdown_report(date_str: str, avg_rate: float, win_rate: float, avg_return: float, closed_count: int, regime: str, params: Dict[str, Any], rationale: str) -> None:
    """Print the markdown optimization report to stdout."""
    print("\n## ⚙️ 스크리너 매개변수 자가 최적화(Auto-Tuner) 결과")
    print(f"**최적화 기준일시**: {date_str} KST")
    print(f"**과거 피드백 수치**: 승률 `{win_rate:.1f}%` (평균 수익률 `{avg_return:.2f}%`, 총 `{closed_count}`개 종목 청산 이력)")
    print(f"**시장 등락 분석**: 추적 종목 평균 등락률 `{avg_rate:.2f}%` -> **`{regime}`** 판정")
    print(f"**최적화 근거**: {rationale}")
    
    print("\n### 🛠️ 실시간 자동 조정 매개변수 리스트")
    print("| 매개변수명 | 기본값 | 조정된 적용값 | 의미 |")
    print("|---|:---:|:---:|---|")
    print(f"| `flow_streak_consecutive_days` | 3일 | **{params['flow_streak_consecutive_days']}일** | 연속 수급 요구 일수 |")
    print(f"| `kelly_sizing_factor` | 0.5 | **{params['kelly_sizing_factor']}** | 켈리 비중 계수 (낮을수록 보수적) |")
    print(f"| `pullback_rsi_max` | 75 | **{params['pullback_rsi_max']}** | 풀백 과열 제한 RSI |")
    print(f"| `pullback_sharp_drop_max` | -20% | **{params['pullback_sharp_drop_max']}%** | 풀백 최대 당일 낙폭 제약 |")
    print(f"| `top_limit` | 100 | **{params['top_limit']}개** | 수급 수집 순위 한도 |")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Optimize screener parameters dynamically.")
    parser.add_argument("--index-path", default=str(DEFAULT_INDEX))
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG))
    parser.add_argument("--obsidian-log-path", default=str(DEFAULT_OBSIDIAN_LOG))
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        # 1. Parse historical performance
        win_rate, avg_return, closed_count = parse_closed_picks(Path(args.index_path))
        
        # 2. Parse current market return
        avg_rate = get_market_average_return(Path(args.market_snapshot_path))
        
        # 3. Decide parameters based on matrix
        regime, params, rationale = decide_scenario(avg_rate, win_rate)
        
        # 4. Save dynamic config JSON
        output_data = {
            "generated_at": now_kst().isoformat(timespec="seconds"),
            "feedback_metrics": {
                "win_rate_pct": round(win_rate, 2),
                "avg_return_pct": round(avg_return, 2),
                "closed_count": closed_count
            },
            "market_metrics": {
                "average_change_rate_pct": round(avg_rate, 2)
            },
            "market_regime_decision": regime,
            "parameters": params,
            "rationale": rationale
        }
        write_json(Path(args.config_path), output_data)
        print(f"wrote {args.config_path}", file=sys.stderr)
        
        # 5. Append to Obsidian Dynamic Rules Log
        timestamp = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        update_obsidian_log(
            Path(args.obsidian_log_path),
            timestamp,
            avg_rate,
            win_rate,
            avg_return,
            closed_count,
            regime,
            params,
            rationale
        )
        print(f"updated Obsidian log at {args.obsidian_log_path}", file=sys.stderr)
        
        # 6. Render report
        print_markdown_report(
            timestamp,
            avg_rate,
            win_rate,
            avg_return,
            closed_count,
            regime,
            params,
            rationale
        )
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
