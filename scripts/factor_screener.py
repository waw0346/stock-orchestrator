#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,f-string-without-interpolation,line-too-long
# pylint: disable=too-many-arguments
"""
모멘텀 팩터 스크리너 — KOSPI 주요 종목 대상
사용법: python scripts/factor_screener.py
출력:  picks/factor_scores.md (최신이 상단에 누적)

의존성: pip install pykrx pandas
"""

import sys
import os
import warnings
import argparse
from datetime import datetime, timedelta
from typing import Optional, Tuple

warnings.filterwarnings("ignore")


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


configure_stdio()


try:
    from pykrx import stock as krx
    import pandas as pd
except ImportError:
    print("필수 패키지 없음. 설치 후 재실행:")
    print("  pip install pykrx pandas")
    sys.exit(1)


# ── 스크리닝 대상 (KOSPI 시총 상위 · 현재 포트폴리오 외) ──────────────────
UNIVERSE = {
    "005380": "현대차",
    "000270": "기아",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "373220": "LG에너지솔루션",
    "035420": "NAVER",
    "035720": "카카오",
    "003670": "포스코홀딩스",
    "068270": "셀트리온",
    "012330": "현대모비스",
    "028260": "삼성물산",
    "055550": "신한지주",
    "105560": "KB금융",
    "086790": "하나금융지주",
    "009150": "삼성전기",
    "247540": "에코프로비엠",
    "012450": "한화에어로스페이스",
    "047810": "한국항공우주",
    "064350": "현대로템",
    "003490": "대한항공",
    "000100": "유한양행",
    "017670": "SK텔레콤",
    "030200": "KT",
    "032830": "삼성생명",
    "010950": "S-Oil",
    "000810": "삼성화재",
    "096770": "SK이노베이션",
    "302440": "SK바이오사이언스",
    "263750": "펄어비스",
    "036570": "엔씨소프트",
}

# 현재 포트폴리오 — 스크리닝에서 제외
CURRENT_PORTFOLIO = {
    "005930", "000660", "011790", "454910",
    "329180", "046890", "066570", "006800", "207940",
}

# 팩터 가중치 (합계 = 1.0)
WEIGHTS = {
    "rs_3m":   0.35,   # 3개월 상대 강도  — 중기 모멘텀 핵심
    "rs_1m":   0.20,   # 1개월 상대 강도  — 단기 모멘텀 가속
    "vol_surge": 0.20, # 거래량 서지      — 수요 급증 신호
    "foreign": 0.25,   # 외국인 순매수    — 스마트머니 방향성
}

TOP_N = 10
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "picks", "factor_scores.md")


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────

def trading_date(dt: datetime) -> str:
    """주말이면 전 금요일로 보정해 KRX 거래일 반환"""
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def date_window(today: datetime) -> Tuple[str, str, str, str]:
    """Return KRX date strings for end, 3-month, 1-month, and 20-day windows."""
    end = trading_date(today)
    start_3m = trading_date(today - timedelta(days=95))
    start_1m = trading_date(today - timedelta(days=35))
    start_20d = trading_date(today - timedelta(days=35))
    return end, start_3m, start_1m, start_20d


def print_probe(name: str, ok: bool, detail: str) -> bool:
    """Print a diagnostic probe result and return its status."""
    status = "OK" if ok else "FAIL"
    print(f"{status:<4} {name}: {detail}")
    return ok


def print_info(name: str, detail: str) -> None:
    """Print diagnostic context that does not affect pass/fail status."""
    print(f"INFO {name}: {detail}")


def diagnose_index(start: str, end: str) -> bool:
    """Check whether KOSPI benchmark data can be fetched."""
    try:
        df = krx.get_index_ohlcv_by_date(start, end, "1001")
        if df.empty:
            return print_probe("KOSPI index", False, "empty response")
        return print_probe(
            "KOSPI index",
            True,
            f"rows={len(df)}, columns={','.join(str(c) for c in df.columns)}",
        )
    except Exception as exc:
        return print_probe("KOSPI index", False, repr(exc))


def diagnose_ohlcv(ticker: str, start: str, end: str) -> bool:
    """Check whether ticker OHLCV data can be fetched."""
    try:
        df = krx.get_market_ohlcv_by_date(start, end, ticker)
        if df.empty:
            return print_probe("Ticker OHLCV", False, f"{ticker}: empty response")
        return print_probe(
            "Ticker OHLCV",
            True,
            f"{ticker}: rows={len(df)}, columns={','.join(str(c) for c in df.columns)}",
        )
    except Exception as exc:
        return print_probe("Ticker OHLCV", False, f"{ticker}: {exc!r}")


def diagnose_foreign(ticker: str, start: str, end: str) -> bool:
    """Check whether ticker foreign flow data can be fetched."""
    try:
        df = krx.get_market_trading_volume_by_date(start, end, ticker)
        if df.empty:
            return print_probe("Foreign flow", False, f"{ticker}: empty response")
        col = next((c for c in ["외국인합계", "외국인"] if c in df.columns), None)
        detail = f"{ticker}: rows={len(df)}, columns={','.join(str(c) for c in df.columns)}"
        if not col:
            return print_probe("Foreign flow", False, f"{detail}; missing foreign column")
        return print_probe("Foreign flow", True, f"{detail}; using={col}")
    except Exception as exc:
        return print_probe("Foreign flow", False, f"{ticker}: {exc!r}")


def run_diagnostics(ticker: str, today: datetime) -> int:
    """Run data-source diagnostics without writing screener output."""
    end, start_3m, start_1m, start_20d = date_window(today)
    print(f"\n{'═'*64}")
    print(f"  모멘텀 팩터 스크리너 진단  |  {today.strftime('%Y-%m-%d')}")
    print(f"{'═'*64}\n")
    print(f"date window: end={end}, 3m={start_3m}, 1m={start_1m}, 20d={start_20d}")
    print(f"sample ticker: {ticker}\n")
    print_info("KRX_ID env", "set" if os.environ.get("KRX_ID") else "missing")
    print_info("KRX_PW env", "set" if os.environ.get("KRX_PW") else "missing")

    checks = [
        diagnose_index(start_1m, end),
        diagnose_ohlcv(ticker, start_3m, end),
        diagnose_foreign(ticker, start_20d, end),
    ]
    return 0 if all(checks) else 2


def kospi_return(start: str, end: str) -> Optional[float]:
    """Return KOSPI percentage return between two KRX date strings."""
    try:
        df = krx.get_index_ohlcv_by_date(start, end, "1001")
        if df.empty or len(df) < 2:
            return None
        return (df["종가"].iloc[-1] / df["종가"].iloc[0] - 1) * 100
    except Exception as exc:
        print(f"  ⚠ KOSPI 기준 수익률 조회 실패: {exc}")
        return None


def benchmark_returns(start_3m: str, start_1m: str, end: str) -> Optional[Tuple[float, float]]:
    """Return validated 3-month and 1-month KOSPI benchmark returns."""
    kp_3m = kospi_return(start_3m, end)
    kp_1m = kospi_return(start_1m, end)
    if kp_3m is None or kp_1m is None:
        print("  ⚠ 기준지수 데이터가 불완전해 스크리닝 결과 저장을 중단합니다.")
        return None
    return kp_3m, kp_1m


def foreign_net_buy(ticker: str, start_20d: str, end: str) -> int:
    """Return recent cumulative foreign net-buy volume when available."""
    try:
        inv = krx.get_market_trading_volume_by_date(start_20d, end, ticker)
        if inv.empty:
            return 0
        col = next((c for c in ["외국인합계", "외국인"] if c in inv.columns), None)
        return int(inv[col].sum()) if col else 0
    except Exception:
        return 0


def ohlcv_metrics(df: pd.DataFrame, kp_3m: float, kp_1m: float) -> dict:
    """Calculate price, relative-strength, and volume metrics from OHLCV data."""
    close = df["종가"]
    volume = df["거래량"]
    ret_3m = (close.iloc[-1] / close.iloc[0] - 1) * 100
    ret_1m = (close.iloc[-1] / close.iloc[-22] - 1) * 100 if len(close) >= 22 else ret_3m
    avg_60d = volume.tail(60).mean() if len(volume) >= 60 else volume.mean()
    vol_surge = volume.tail(5).mean() / avg_60d if avg_60d > 0 else 1.0
    return {
        "price": int(close.iloc[-1]),
        "ret_3m": round(ret_3m, 1),
        "ret_1m": round(ret_1m, 1),
        "rs_3m": round(ret_3m - kp_3m, 1),
        "rs_1m": round(ret_1m - kp_1m, 1),
        "vol_surge": round(float(vol_surge), 2),
    }


def calc_factors(ticker: str, name: str, kp_3m: float, kp_1m: float,
                 end: str, start_3m: str, start_20d: str) -> Optional[dict]:
    """Calculate momentum, volume, and foreign-flow factors for one ticker."""
    try:
        df = krx.get_market_ohlcv_by_date(start_3m, end, ticker)
        if df.empty or len(df) < 20:
            return None

        metrics = ohlcv_metrics(df, kp_3m, kp_1m)
        return {
            "ticker":      ticker,
            "name":        name,
            **metrics,
            "foreign_net": foreign_net_buy(ticker, start_20d, end),
        }
    except Exception as e:
        print(f"    ⚠ {name}({ticker}) 오류: {e}")
        return None


def normalize(series: pd.Series) -> pd.Series:
    """Scale a numeric series to a 0-100 range."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    return (series - mn) / (mx - mn) * 100


def collect_records(kp_3m: float, kp_1m: float, end: str,
                    start_3m: str, start_20d: str) -> list:
    """Collect factor records for tickers outside the current portfolio."""
    targets = {k: v for k, v in UNIVERSE.items() if k not in CURRENT_PORTFOLIO}
    print(f"▶ {len(targets)}개 종목 팩터 계산 중...\n")

    records = []
    for i, (ticker, name) in enumerate(targets.items(), 1):
        print(f"  [{i:02d}/{len(targets)}] {name:<12} ({ticker})", end=" ... ", flush=True)
        record = calc_factors(ticker, name, kp_3m, kp_1m, end, start_3m, start_20d)
        if record:
            records.append(record)
            print(
                f"RS3M={record['rs_3m']:+.1f}%  "
                f"Vol={record['vol_surge']:.2f}x  "
                f"외국인={record['foreign_net']:+,}주"
            )
        else:
            print("스킵")
    return records


def score_records(records: list) -> pd.DataFrame:
    """Normalize factors and return the highest-scoring tickers."""
    df = pd.DataFrame(records).set_index("ticker")
    df["n_rs3m"] = normalize(df["rs_3m"])
    df["n_rs1m"] = normalize(df["rs_1m"])
    df["n_vol"] = normalize(df["vol_surge"])
    df["n_foreign"] = normalize(df["foreign_net"])
    df["score"] = (
        df["n_rs3m"] * WEIGHTS["rs_3m"] +
        df["n_rs1m"] * WEIGHTS["rs_1m"] +
        df["n_vol"] * WEIGHTS["vol_surge"] +
        df["n_foreign"] * WEIGHTS["foreign"]
    ).round(1)
    df.sort_values("score", ascending=False, inplace=True)
    return df.head(TOP_N)


def print_scores(top: pd.DataFrame) -> None:
    """Print the top score table to the console."""
    print(f"\n{'═'*64}")
    print(f"  TOP {TOP_N}  모멘텀 팩터 스코어")
    print(f"{'─'*64}")
    header = f"{'순위':<4} {'종목':<12} {'현재가':>8}  {'RS3M':>7} {'RS1M':>7} {'거래량':>6} {'점수':>6}"
    print(f"  {header}")
    print(f"  {'─'*58}")
    for rank, (_ticker, row) in enumerate(top.iterrows(), 1):
        flag = " 🔥" if rank <= 3 else ""
        print(
            f"  {rank:<3} {row['name']:<12} {row['price']:>8,}원  "
            f"{row['rs_3m']:>+6.1f}% {row['rs_1m']:>+6.1f}% "
            f"{row['vol_surge']:>5.2f}x  {row['score']:>5.1f}{flag}"
        )


def build_markdown(today: datetime, kp_3m: float, kp_1m: float,
                   record_count: int, top: pd.DataFrame) -> str:
    """Build the Markdown section for the latest screener run."""
    lines = [
        f"## {today.strftime('%Y-%m-%d')} 스크리닝 결과\n",
        f"> KOSPI 기준 3M {kp_3m:+.1f}% / 1M {kp_1m:+.1f}% | 대상 {record_count}개 종목\n",
        "",
        "| 순위 | 종목코드 | 종목명 | 현재가 | RS 3M | RS 1M | 거래량배수 | 외국인(20일) | 종합점수 |",
        "|------|---------|--------|--------|-------|-------|----------|------------|--------|",
    ]
    for rank, (ticker, row) in enumerate(top.iterrows(), 1):
        star = " 🔥" if rank <= 3 else ""
        lines.append(
            f"| {rank}{star} | {ticker} | {row['name']} | {row['price']:,}원 | "
            f"{row['rs_3m']:+.1f}% | {row['rs_1m']:+.1f}% | "
            f"{row['vol_surge']:.2f}x | {row['foreign_net']:+,}주 | **{row['score']:.1f}** |"
        )
    lines += [
        "",
        f"_가중치: RS3M {WEIGHTS['rs_3m']*100:.0f}% · "
        f"RS1M {WEIGHTS['rs_1m']*100:.0f}% · "
        f"거래량 {WEIGHTS['vol_surge']*100:.0f}% · "
        f"외국인 {WEIGHTS['foreign']*100:.0f}%_",
        "",
    ]
    return "\n".join(lines)


def write_report(section: str) -> None:
    """Prepend a Markdown screener section to the output file."""
    out_path = os.path.normpath(OUTPUT_PATH)
    header_md = (
        "# 모멘텀 팩터 스코어링\n\n"
        "> 매주 금요일 자동 갱신 — factor-screener 루틴  \n"
        "> 상위 종목은 오케스트레이터 Deep 분석 후보입니다.\n\n"
    )

    existing_body = ""
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
        idx = content.find("\n## ")
        if idx != -1:
            existing_body = content[idx + 1:]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header_md + section + "---\n\n" + existing_body)


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="KOSPI momentum factor screener")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="check KRX/KOSPI/OHLCV/foreign-flow data sources without writing output",
    )
    parser.add_argument(
        "--diagnose-ticker",
        default="005380",
        help="sample ticker for --diagnose, default: 005380",
    )
    return parser.parse_args()


# ── 메인 ───────────────────────────────────────────────────────────────────

def main():
    """Run the screener and write the Markdown report."""
    args = parse_args()
    today = datetime.now()
    if args.diagnose:
        sys.exit(run_diagnostics(args.diagnose_ticker, today))

    end, start_3m, start_1m, start_20d = date_window(today)

    print(f"\n{'═'*64}")
    print(f"  모멘텀 팩터 스크리너  |  {today.strftime('%Y-%m-%d')}")
    print(f"{'═'*64}\n")

    # KOSPI 기준 수익률
    print("▶ KOSPI 기준 수익률 계산 중...")
    benchmark = benchmark_returns(start_3m, start_1m, end)
    if benchmark is None:
        sys.exit(2)
    kp_3m, kp_1m = benchmark
    print(f"  KOSPI  3M: {kp_3m:+.1f}%   1M: {kp_1m:+.1f}%\n")

    records = collect_records(kp_3m, kp_1m, end, start_3m, start_20d)
    if not records:
        print("\n⚠  유효한 데이터가 없습니다.")
        sys.exit(2)

    top = score_records(records)
    print_scores(top)
    write_report(build_markdown(today, kp_3m, kp_1m, len(records), top))
    print(f"\n✅ 저장 완료: picks/factor_scores.md")
    top1 = top.iloc[0]
    print(f"   1위: {top1['name']} ({top.index[0]})  점수={top1['score']:.1f}  RS3M={top1['rs_3m']:+.1f}%")
    print(f"\n→ 상위 종목을 오케스트레이터에 전달해 Deep 분석을 실행하세요.")
    print(f"   예: \"[종목명] 분석해줘\"\n")


if __name__ == "__main__":
    main()
