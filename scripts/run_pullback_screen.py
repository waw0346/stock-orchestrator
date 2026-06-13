#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long,too-many-branches
"""
Screen tracked/watch picks for conservative pullback readiness.

Outputs:
  picks/cache/pullback_candidates.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.io import read_json, write_json
from lib.status import normalize_pick_status


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "picks" / "INDEX.md"
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "pullback_candidates.json"
KST = timezone(timedelta(hours=9))


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")


def parse_price(text: str) -> Optional[int]:
    """Parse the first won-like integer from text."""
    match = re.search(r"([0-9,]+)", str(text))
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def parse_entry_range(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse entry range like 130,000~145,000원."""
    numbers = [int(value.replace(",", "")) for value in re.findall(r"([0-9][0-9,]*)", str(text))]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return None, None





def parse_index(path: Path) -> List[Dict[str, Any]]:
    """Read tracked active/watch rows from picks/INDEX.md."""
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Tracked"):
            section = "tracked"
            continue
        if line.startswith("## "):
            section = ""
            continue
        if section != "tracked" or not re.match(r"^\|\s*20\d{2}-", line):
            continue
        columns = [column.strip() for column in line.split("|")]
        if len(columns) < 11:
            continue
        status = normalize_pick_status(columns[9])
        if status not in {"active", "watch"}:
            continue
        entry_low, entry_high = parse_entry_range(columns[6])
        rows.append({
            "published_at": columns[1],
            "ticker": columns[2].zfill(6),
            "name": columns[3],
            "rating": columns[4],
            "horizon": columns[5],
            "entry_text": columns[6],
            "entry_low": entry_low,
            "entry_high": entry_high,
            "index_price": parse_price(columns[7]),
            "return_text": columns[8],
            "status": status,
            "last_review": columns[10],
        })
    return rows





def as_float(value: Any) -> Optional[float]:
    """Convert common finance number strings to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {"-", "N/A", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def metric(item: Optional[Dict[str, Any]], *keys: str) -> Optional[float]:
    """Read a metric from top-level, technical, or flow payloads."""
    if not item:
        return None
    containers = [item]
    for child in ("technical", "technicals", "flow", "flows"):
        if isinstance(item.get(child), dict):
            containers.append(item[child])
    for container in containers:
        for key in keys:
            value = as_float(container.get(key))
            if value is not None:
                return value
    return None


def market_by_ticker(market: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index market snapshot items by ticker."""
    return {str(item.get("ticker", "")).zfill(6): item for item in market.get("items", [])}


def score_trend(price: Optional[float], market_item: Optional[Dict[str, Any]], notes: List[str], gaps: List[str]) -> int:
    """Score trend strength with moving averages when present."""
    ma20 = metric(market_item, "ma20", "ma_20", "moving_average_20")
    ma60 = metric(market_item, "ma60", "ma_60", "moving_average_60")
    ma120 = metric(market_item, "ma120", "ma_120", "moving_average_120")
    if price is None or ma20 is None or ma60 is None:
        gaps.append("MA20/60 unavailable")
        return 0
    if price > ma20 > ma60 and (ma120 is None or ma60 >= ma120):
        notes.append("price > MA20 > MA60 trend alignment")
        return 3
    if price > ma20 and ma20 >= ma60:
        notes.append("price above MA20 with non-deteriorating MA20/60")
        return 2
    if price > ma60:
        notes.append("price above MA60, but short trend is mixed")
        return 1
    notes.append("price below MA60 trend support")
    return 0


def score_volume(market_item: Optional[Dict[str, Any]], notes: List[str], gaps: List[str]) -> int:
    """Score volume contraction against 20-day average when present."""
    volume = metric(market_item, "volume")
    avg20 = metric(market_item, "volume_avg20", "avg_volume_20", "volume_ma20")
    if volume is None or avg20 is None or avg20 <= 0:
        gaps.append("volume_avg20 unavailable")
        return 0
    ratio = volume / avg20
    notes.append(f"volume/avg20={ratio:.2f}")
    if ratio <= 0.4:
        return 3
    if ratio <= 0.6:
        return 2
    if ratio <= 0.8:
        return 1
    return 0


def score_flow(market_item: Optional[Dict[str, Any]], notes: List[str], gaps: List[str]) -> int:
    """Score five-day foreign/institution flow when present."""
    foreign = metric(market_item, "foreign_net_buy_5d", "foreign_5d", "foreign_flow_5d")
    institution = metric(market_item, "institution_net_buy_5d", "institution_5d", "institution_flow_5d")
    if foreign is None and institution is None:
        gaps.append("foreign/institution 5-day flow unavailable")
        return 0
    foreign = foreign or 0
    institution = institution or 0
    total = foreign + institution
    notes.append(f"5d flow foreign={foreign:.0f}, institution={institution:.0f}")
    if foreign > 0 and institution > 0:
        return 3
    if total > 0 and min(foreign, institution) >= 0:
        return 2
    if total > 0:
        return 1
    return 0


def score_pullback(
    row: Dict[str, Any],
    market_item: Optional[Dict[str, Any]],
    rsi_max: float = 75.0,
    sharp_drop_max: float = -20.0,
    basis_risk_level: str = "NORMAL",
    avg_basis_15m: float = 0.0
) -> Dict[str, Any]:
    """Score one row with conservative available-data pullback checks."""
    ticker = row["ticker"]
    price = market_item.get("price") if market_item else row.get("index_price")
    change_rate = market_item.get("change_rate") if market_item else None
    entry_low = row.get("entry_low")
    entry_high = row.get("entry_high")

    signals = {
        "trend_strength": 0,
        "pullback_depth": 0,
        "volume_contraction": 0,
        "flow_check": 0,
    }
    notes: List[str] = []
    block_reasons: List[str] = []
    data_gaps: List[str] = []

    if price is None:
        block_reasons.append("market_price_missing")
        notes.append("가격 데이터가 없어 pullback 판정 불가")
    if entry_low is None or entry_high is None:
        block_reasons.append("entry_zone_missing")
        notes.append("INDEX 진입 구간 파싱 실패")

    if price is not None and entry_low is not None and entry_high is not None:
        if entry_low <= price <= entry_high:
            signals["pullback_depth"] = 3
            notes.append("현재가가 entry zone 내부")
        elif price < entry_low:
            signals["pullback_depth"] = 1
            notes.append("현재가가 entry zone 하단 이탈, 추세 훼손 여부 확인 필요")
        else:
            premium = ((price - entry_high) / entry_high) * 100 if entry_high else 0
            if premium <= 5:
                signals["pullback_depth"] = 2
                notes.append("entry zone 상단 5% 이내 접근")
            else:
                signals["pullback_depth"] = 0
                notes.append(f"entry zone 상단 대비 +{premium:.1f}%로 아직 눌림 부족")

    signals["trend_strength"] = score_trend(as_float(price), market_item, notes, data_gaps)
    signals["volume_contraction"] = score_volume(market_item, notes, data_gaps)
    signals["flow_check"] = score_flow(market_item, notes, data_gaps)

    if change_rate is not None:
        if change_rate <= sharp_drop_max:
            block_reasons.append(f"sharp_drop_over_{abs(int(sharp_drop_max))}pct")
        elif change_rate <= -5:
            notes.append("단기 하락폭이 커서 당일 종가 확인 필요")
        elif change_rate >= 5:
            block_reasons.append("gap_or_rally_over_5pct")

    rsi14 = metric(market_item, "rsi14", "rsi_14")
    if rsi14 is None:
        data_gaps.append("RSI14 unavailable")
    elif rsi14 >= rsi_max:
        block_reasons.append("rsi_overheated")
    elif 45 <= rsi14 <= 60:
        notes.append("RSI14 is in pullback support range")

    # Apply Futures Basis Gate Filter
    if basis_risk_level == "HIGH" or avg_basis_15m <= -2.0:
        block_reasons.append("futures_basis_backwardation")
        notes.append(f"선물 베이시스 위험 감지 (15분 평균: {avg_basis_15m:.3f}). 프로그램 매도 우려로 진입 제한.")

    known_signal_count = len([score for score in signals.values() if score > 0])
    total = sum(signals.values())
    if block_reasons:
        decision = "BLOCK"
    elif total >= 10 and known_signal_count >= 4:
        decision = "STRONG_ENTRY"
    elif total >= 8 and known_signal_count >= 3:
        decision = "PROBE_ENTRY"
    elif signals["pullback_depth"] >= 2:
        decision = "WAIT"
    else:
        decision = "PASS"

    if decision in {"STRONG_ENTRY", "PROBE_ENTRY"}:
        notes.append("Screening signal only; run pullback-analyst before any order decision")

    return {
        "ticker": ticker,
        "name": row["name"],
        "status": row["status"],
        "price": price,
        "change_rate": change_rate,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "signal_scores": {**signals, "total": total},
        "known_signal_count": known_signal_count,
        "decision": decision,
        "confidence": "보통" if known_signal_count >= 3 else "낮음",
        "data_gaps": data_gaps,
        "notes": notes,
        "block_reasons": block_reasons,
    }


def offline_market_snapshot() -> Dict[str, Any]:
    """Return deterministic market snapshot for tests."""
    return {
        "generated_at": now_kst(),
        "mode": "offline_sample",
        "items": [
            {
                "ticker": "066570",
                "price": 228000,
                "change_rate": -2.1,
                "technical": {
                    "ma20": 221000,
                    "ma60": 205000,
                    "ma120": 198000,
                    "rsi14": 54,
                    "volume_avg20": 210000,
                },
                "volume": 105000,
                "flow": {
                    "foreign_net_buy_5d": 1200000000,
                    "institution_net_buy_5d": 800000000,
                },
            },
            {"ticker": "006800", "price": 57800, "change_rate": -1.4},
            {"ticker": "353200", "price": 157500, "change_rate": 6.2},
            {"ticker": "007660", "price": 136300, "change_rate": -2.2},
        ],
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    """Run pullback screen."""
    rows = parse_index(Path(args.index_path))
    market = offline_market_snapshot() if args.offline_sample else read_json(Path(args.market_snapshot_path), default={})
    by_ticker = market_by_ticker(market)
    
    # Load dynamic rules if available
    config_path = ROOT / "picks" / "cache" / "dynamic_rules_config.json"
    rsi_max = 75.0
    sharp_drop_max = -20.0
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            params = config.get("parameters", {})
            rsi_max = float(params.get("pullback_rsi_max", rsi_max))
            sharp_drop_max = float(params.get("pullback_sharp_drop_max", sharp_drop_max))
            print(f"Loaded dynamic parameters: pullback_rsi_max = {rsi_max}, pullback_sharp_drop_max = {sharp_drop_max}%", file=sys.stderr)
        except Exception as exc:
            print(f"Warning: Failed to load dynamic rules config: {exc}", file=sys.stderr)
            
    # Load broadcast basis status
    status_path = ROOT / "picks" / "cache" / "futures_monitor_status.json"
    basis_risk_level = "NORMAL"
    avg_basis_15m = 0.0
    if status_path.exists():
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
            basis_risk_level = status_data.get("risk_level", "NORMAL")
            avg_basis_15m = status_data.get("avg_basis_15m", 0.0)
            print(f"Loaded futures basis status: risk_level={basis_risk_level}, 15m_avg={avg_basis_15m:.3f}", file=sys.stderr)
        except Exception as exc:
            print(f"Warning: Failed to load futures basis status: {exc}", file=sys.stderr)

    results = [
        score_pullback(
            row,
            by_ticker.get(row["ticker"]),
            rsi_max=rsi_max,
            sharp_drop_max=sharp_drop_max,
            basis_risk_level=basis_risk_level,
            avg_basis_15m=avg_basis_15m
        )
        for row in rows
    ]
    return {
        "generated_at": now_kst(),
        "mode": "offline_sample" if args.offline_sample else "live",
        "source": "INDEX+market_data_snapshot",
        "market_snapshot_generated_at": market.get("generated_at"),
        "strategy": "pullback_4_signal_conservative",
        "candidates": results,
        "summary": {
            "strong_entry": len([item for item in results if item["decision"] == "STRONG_ENTRY"]),
            "wait": len([item for item in results if item["decision"] == "WAIT"]),
            "probe_entry": len([item for item in results if item["decision"] == "PROBE_ENTRY"]),
            "block": len([item for item in results if item["decision"] == "BLOCK"]),
            "pass": len([item for item in results if item["decision"] == "PASS"]),
        },
        "note": "Missing technical/flow inputs are scored as 0. ENTRY labels are screening states, not direct trading instructions.",
    }





def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run conservative pullback screen.")
    parser.add_argument("--index-path", default=str(DEFAULT_INDEX))
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--offline-sample", action="store_true")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        result = run(args)
        write_json(Path(args.output_path), result)
        print(f"wrote {args.output_path}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
