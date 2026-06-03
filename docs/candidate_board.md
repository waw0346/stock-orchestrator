# 후보 통합판

`scripts/run_candidate_board.py`는 preopen, pullback, fundamentals, market 결과를 종목 단위로 합쳐 `picks/cache/candidate_board.json`을 만듭니다.

## 실행

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_candidate_board.ps1
```

## 입력

- `picks/cache/market_data_snapshot.json`
- `picks/cache/pullback_candidates.json`
- `picks/cache/preopen_filtered_candidates.json`
- `picks/cache/fundamentals_snapshot.json`
- `picks/cache/fiscal_ai_investment_news.json`

## 산출물

`picks/cache/candidate_board.json`

- `rows[]`: 종목별 통합 상태
- `checks.preopen`: 미국장 장전 후보 필터 결과
- `checks.pullback`: 풀백 4신호 결과
- `checks.fundamentals`: 펀더멘탈 수집/게이트 상태
- `us_catalysts[]`: Fiscal.ai 회사 뉴스 기반 미국장 보조 촉매
- `decision`: `FOCUS`, `WATCH`, `BLOCK`, `PASS`

`us_catalysts`는 점수에 직접 더하지 않고, 한국장 후보를 해석할 때 AI/반도체/클라우드 같은 미국장 촉매를 확인하는 보조 맥락으로만 사용합니다. `FOCUS`와 `WATCH`는 리서치 큐 상태이며 직접 매매 지시가 아닙니다.
