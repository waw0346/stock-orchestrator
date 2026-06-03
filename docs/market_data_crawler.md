# 운영 시세 수집기

`scripts/collect_market_data.py`는 운영 점검용 시세, 업종, 테마 힌트를 수집해 `picks/cache/market_data_snapshot.json`에 저장합니다.

## 데이터 소스

- 네이버 증권 모바일 JSON: 현재가, 등락, 거래량, 거래대금, 시가총액 후보 필드
- 네이버 증권 종목 페이지: 업종/테마 보조 크롤링
- 네이버 증권 일별 시세: `ma5`, `ma20`, `ma60`, `ma120`, `rsi14`, `volume_avg20` 계산
- 토스증권 공식 Open API: 사전신청과 토큰 발급 후 `TOSS_INVEST_TOKEN`, `TOSS_INVEST_QUOTE_URL_TEMPLATE`이 있을 때 사용
- 토스증권 공개 웹: `--IncludeTossPublic` 사용 시 공개 페이지를 보강 소스로 시도

토스증권 공식 API는 2026년 현재 사전신청 기반입니다. 승인 전에는 네이버 데이터를 주 소스로 사용하고, 토스 항목은 `not_configured`로 기록됩니다.

## 실행

전체 운영 종목 수집:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_market_data.ps1
```

기본 universe는 `picks/INDEX.md`, `picks/paper_trading_rules.json`, `picks/cache/preopen_candidates.json`를 합칩니다. 그래서 미국장 마감 루틴이 만든 장전 후보도 가격/기술지표 수집 대상에 포함됩니다.

수집 결과로 모의매매 가격 스냅샷까지 갱신:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_market_data.ps1 -UpdatePaperPriceSnapshot
```

특정 종목만 수집:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_market_data.ps1 -Tickers "005930,000660,006800"
```

기술지표 히스토리 페이지 수 조정 또는 비활성화:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_market_data.ps1 -HistoryPages 12
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_market_data.ps1 -HistoryPages 0
```

기본 동작은 live 수집에서 모든 가격이 결측이면 기존 운영 스냅샷을 보존하고 실패본을 `market_data_snapshot.failed.json`으로 남깁니다. 결측 결과도 강제로 저장해야 할 때만 `-AllowPartialWrite`를 사용합니다.

네트워크 없이 검증용 샘플 생성:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_market_data.ps1 -OfflineSample -UpdatePaperPriceSnapshot
```

## 산출물

`picks/cache/market_data_snapshot.json`

- `generated_at`: KST 생성 시각
- `items[]`: 종목별 현재가, 등락률, 거래량, 업종, 테마, `technical`, 원천별 상세 상태
- `items[].technical`: 풀백 스크리너가 읽는 MA/RSI/20일 평균 거래량
- `prices`: 모의매매와 자동 점검에 바로 쓰는 `{ ticker: price }` 맵

현재가 API에서 당일 누적 거래량이 비어 있으면, 네이버 일별 시세의 최신 row 거래량을 `volume` fallback으로 사용합니다.

`picks/cache/market_data_snapshot.failed.json`

- live 수집이 네트워크/원천 장애로 전 종목 가격 결측일 때 저장되는 실패 진단 파일입니다.
- 정상 운영 입력으로 쓰지 않고 오류 원인 확인에만 사용합니다.

`picks/paper_price_snapshot.json`

- `-UpdatePaperPriceSnapshot` 옵션을 줄 때만 갱신합니다.
- 실거래 주문이 아니라 모의매매/운영 점검용 입력입니다.
