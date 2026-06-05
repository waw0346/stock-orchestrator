#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Build a market radar snapshot for long-term research context.

Outputs:
  picks/cache/market_radar.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_CANDIDATE = ROOT / "picks" / "cache" / "candidate_board.json"
DEFAULT_FLOW = ROOT / "picks" / "cache" / "flow_snapshot.json"
DEFAULT_FISCAL_AI_NEWS = ROOT / "picks" / "cache" / "fiscal_ai_investment_news.json"
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "market_radar.json"
KST = timezone(timedelta(hours=9))

THEME_KEYWORDS = {
    "AI semiconductor": {
        "tickers": {"005930", "000660", "007660", "009150", "353200", "240810"},
        "keywords": ("semiconductor", "hbm", "ai chip", "broadcom", "nvidia", "memory", "ai semiconductor"),
    },
    "Physical AI robotics": {
        "tickers": {"454910", "066570", "018260"},
        "keywords": ("robot", "robotics", "physical ai", "agentic ai", "nvidia", "automation"),
    },
    "Defense aerospace": {
        "tickers": {"012450"},
        "keywords": ("defense", "aerospace", "hanwha", "space", "missile"),
    },
    "Power infrastructure": {
        "tickers": {"267260"},
        "keywords": ("power", "grid", "electric", "transformer", "infrastructure"),
    },
    "Bio healthcare": {
        "tickers": {"207940"},
        "keywords": ("bio", "healthcare", "cdmo", "fda"),
    },
    "Financial liquidity": {
        "tickers": {"006800", "402340"},
        "keywords": ("securities", "liquidity", "ipo", "etf"),
    },
}


def configure_stdio() -> None:
    """Prefer UTF-8 console output when supported."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    """Read JSON if present, otherwise return an empty object."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any, default: float = 0.0) -> float:
    """Return a float from a number-like value."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    """Return an int from a number-like value."""
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def by_ticker(items: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index rows by six-digit ticker."""
    return {str(item.get("ticker", "")).zfill(6): item for item in items if item.get("ticker")}


def classify_themes(ticker: str, name: str) -> List[str]:
    """Classify a ticker into stable research themes."""
    lower_text = name.lower()
    themes = []
    for theme, rule in THEME_KEYWORDS.items():
        if ticker in rule["tickers"] or any(keyword in lower_text for keyword in rule["keywords"]):
            themes.append(theme)
    return themes or ["Unclassified"]


def volume_ratio(item: Dict[str, Any]) -> Optional[float]:
    """Calculate current volume over 20-day average volume."""
    volume = as_float(item.get("volume"), 0.0)
    avg = as_float((item.get("technical") or {}).get("volume_avg20"), 0.0)
    if volume <= 0 or avg <= 0:
        return None
    return round(volume / avg, 4)


def merge_rows(market: Dict[str, Any], candidate: Dict[str, Any], flow: Dict[str, Any], news: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Merge market, candidate, flow, and news context by ticker."""
    market_by_ticker = by_ticker(market.get("items", []) or [])
    candidate_by_ticker = by_ticker(candidate.get("rows", []) or [])
    flow_by_ticker = by_ticker(flow.get("items", []) or [])
    tickers = sorted(set(market_by_ticker) | set(candidate_by_ticker) | set(flow_by_ticker))

    rows = []
    for ticker in tickers:
        market_item = market_by_ticker.get(ticker, {})
        candidate_item = candidate_by_ticker.get(ticker, {})
        flow_item = flow_by_ticker.get(ticker, {})
        merged_flow = dict(market_item.get("flow") or {})
        merged_flow.update({key: value for key, value in flow_item.items() if key != "ticker"})
        name = str(market_item.get("name") or candidate_item.get("name") or ticker)
        ratio = volume_ratio(market_item)
        rows.append({
            "ticker": ticker,
            "name": name,
            "price": market_item.get("price"),
            "change_rate": as_float(market_item.get("change_rate")),
            "volume": market_item.get("volume"),
            "volume_ratio_20d": ratio,
            "decision": candidate_item.get("decision"),
            "score": candidate_item.get("score"),
            "themes": classify_themes(ticker, name),
            "foreign_net_buy_5d": as_int(merged_flow.get("foreign_net_buy_5d")),
            "institution_net_buy_5d": as_int(merged_flow.get("institution_net_buy_5d")),
            "rsi14": (market_item.get("technical") or {}).get("rsi14"),
        })
    return rows


def build_theme_flows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate ticker rows into theme flow summaries."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        for theme in row.get("themes", []):
            grouped.setdefault(theme, []).append(row)

    flows = []
    for theme, members in grouped.items():
        avg_change = round(sum(as_float(row.get("change_rate")) for row in members) / len(members), 4)
        positive = len([row for row in members if as_float(row.get("change_rate")) > 0])
        top_member = sorted(members, key=lambda row: (as_float(row.get("change_rate")), as_float(row.get("volume_ratio_20d") or 0.0)), reverse=True)[0]
        flows.append({
            "theme": theme,
            "member_count": len(members),
            "positive_count": positive,
            "average_change_rate": avg_change,
            "breadth_ratio": round(positive / len(members), 4),
            "top_ticker": top_member.get("ticker"),
            "top_name": top_member.get("name"),
            "top_change_rate": top_member.get("change_rate"),
            "net_foreign_5d": sum(as_int(row.get("foreign_net_buy_5d")) for row in members),
            "net_institution_5d": sum(as_int(row.get("institution_net_buy_5d")) for row in members),
        })
    flows.sort(key=lambda item: (item["average_change_rate"], item["breadth_ratio"], item["member_count"]), reverse=True)
    return flows


def build_alerts(rows: List[Dict[str, Any]], theme_flows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build conservative research alerts, not trading signals."""
    alerts: List[Dict[str, Any]] = []
    for theme in theme_flows:
        if theme["theme"] == "Unclassified":
            continue
        if theme["member_count"] >= 2 and theme["breadth_ratio"] >= 0.5 and theme["average_change_rate"] > 0:
            alerts.append({
                "signal": "THEME_ACTIVE",
                "theme": theme["theme"],
                "reason": "Theme breadth and average change are positive.",
                "evidence_type": "analysis",
            })
    for row in rows:
        change = as_float(row.get("change_rate"))
        ratio = as_float(row.get("volume_ratio_20d") or 0.0)
        if change <= -5:
            alerts.append({
                "signal": "RISK_DOWN",
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "reason": "Sharp negative intraday move; review thesis and news before any action.",
                "evidence_type": "research_fact",
            })
        elif change >= 5 and ratio >= 1.5:
            alerts.append({
                "signal": "NO_TRADE_CHASE",
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "reason": "Strong price and volume move; mark as chase-risk for long-term research.",
                "evidence_type": "analysis",
            })
        elif ratio >= 2 and change > 0:
            alerts.append({
                "signal": "WATCH_UP",
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "reason": "Positive move with elevated volume versus 20-day average.",
                "evidence_type": "research_fact",
            })
    return alerts


def build_market_context() -> Dict[str, Any]:
    """Return watch blocks for future Kiwoom/KRX/FRED provider attachment."""
    return {
        "futures": {
            "status": "watch_slot",
            "preferred_provider": "Kiwoom API",
            "fields": ["KOSPI200 futures", "basis", "foreign futures net flow", "program trading"],
        },
        "etf": {
            "status": "watch_slot",
            "preferred_provider": "KRX/pykrx/FinanceDataReader",
            "fields": ["sector ETF return", "ETF trading value", "money flow by theme"],
        },
        "fx_rates": {
            "status": "watch_slot",
            "preferred_provider": "FinanceDataReader/FRED/ECOS",
            "fields": ["USD/KRW", "DXY", "US 10Y", "risk-on/risk-off"],
        },
        "big_money": {
            "status": "watch_slot",
            "preferred_provider": "Kiwoom API + KRX after-close",
            "fields": ["foreign net buy", "institution net buy", "pension flow", "program flow"],
        },
    }


def build_obsi_map(args: argparse.Namespace) -> Dict[str, Any]:
    """Describe how Obsidian should classify this output."""
    return {
        "target_notes": {
            "news": "03_market_news",
            "artifact": "04_candidate_boards",
            "analysis": "09_decision_journal",
            "report": "07_stock_analysis",
        },
        "evidence_map": [
            {"evidence_type": "artifact", "source": args.output_path, "note": "Market radar JSON output."},
            {"evidence_type": "artifact", "source": args.market_snapshot_path, "note": "Market data input snapshot."},
            {"evidence_type": "research_fact", "source": args.market_snapshot_path, "note": "Prices, change rates, volume, RSI, and 5-day flow."},
            {"evidence_type": "news", "source": args.fiscal_ai_news_path, "note": "Fiscal.ai/company news catalysts."},
            {"evidence_type": "analysis", "source": args.output_path, "note": "Theme flow, alerts, and market interpretation."},
        ],
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    """Build market radar output."""
    market = read_json(Path(args.market_snapshot_path))
    candidate = read_json(Path(args.candidate_board_path))
    flow = read_json(Path(args.flow_snapshot_path))
    news = read_json(Path(args.fiscal_ai_news_path))

    rows = merge_rows(market, candidate, flow, news)
    theme_flows = build_theme_flows(rows)
    alerts = build_alerts(rows, theme_flows)
    top_movers = sorted(rows, key=lambda row: abs(as_float(row.get("change_rate"))), reverse=True)[:10]
    priority_themes = [theme["theme"] for theme in theme_flows if theme["theme"] != "Unclassified"][:3]

    return {
        "generated_at": now_kst(),
        "mode": args.mode,
        "source": "market+candidate+flow+fiscal_ai_news",
        "inputs": {
            "market_generated_at": market.get("generated_at"),
            "candidate_generated_at": candidate.get("generated_at"),
            "flow_generated_at": flow.get("generated_at"),
            "fiscal_ai_news_generated_at": news.get("generated_at"),
        },
        "preopen": {
            "purpose": "Frame the day before the open using US catalysts, macro watch slots, and candidate board state.",
            "checklist": ["US catalysts", "futures/FX watch", "ETF theme watch", "today risk events"],
            "priority_themes": priority_themes,
        },
        "intraday": {
            "purpose": "Track where money is moving without issuing trade instructions.",
            "alerts": alerts,
            "top_movers": top_movers,
        },
        "after_close": {
            "purpose": "Reconcile intraday interpretation with closing price, KRX-confirmed flow, and Obsidian review.",
            "review_questions": [
                "Did theme breadth expand or stay leader-only?",
                "Did foreign/institution flow confirm price moves?",
                "Did FX/futures/ETF context support risk-on or risk-off?",
                "Does any long-term thesis need an update?",
            ],
        },
        "theme_flows": theme_flows,
        "market_context": build_market_context(),
        "rows": rows,
        "obsi": build_obsi_map(args),
        "note": "Research radar outputs are not direct trading instructions; use them to organize evidence and review long-term theses.",
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build market radar snapshot.")
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--candidate-board-path", default=str(DEFAULT_CANDIDATE))
    parser.add_argument("--flow-snapshot-path", default=str(DEFAULT_FLOW))
    parser.add_argument("--fiscal-ai-news-path", default=str(DEFAULT_FISCAL_AI_NEWS))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mode", choices=("preopen", "intraday", "after_close"), default="intraday")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        radar = run(args)
        write_json(Path(args.output_path), radar)
        print(f"wrote {args.output_path}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
