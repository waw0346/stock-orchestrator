# 펀더멘탈 수집기

`scripts/collect_fundamentals.py`는 OpenDART API를 기본 provider로 사용해 공시 기반 재무지표와 주요 계정값을 수집합니다. `pykrx`는 KRX 일자 기준 밸류에이션 보조 provider로 남겨둡니다.

## Provider

- `opendart`: 기본값. OpenDART `fnlttSinglIndx`, `fnlttSinglAcnt`, `corpCode` API를 사용합니다.
- `pykrx`: KRX 일자 기준 `BPS`, `PER`, `PBR`, `EPS`, `DIV`, `DPS` 조회를 시도합니다.
- `offline_sample`: 네트워크 없이 테스트용 샘플 데이터를 생성합니다.

OpenDART는 공시 기반 재무정보 원천입니다. KRX daily `BPS`, `PER`, `PBR`, `EPS`, `DIV`, `DPS`를 그대로 제공하지 않으므로, OpenDART provider의 해당 필드는 `null`로 남기고 `financial_indicators`, `account_values`에 공시 지표와 계정값을 저장합니다.
운영 게이트에서 바로 쓰기 쉬운 핵심 지표는 `gate_metrics`에 별도로 요약됩니다.

기본 universe는 `picks/INDEX.md`, `picks/paper_trading_rules.json`, `picks/cache/market_data_snapshot.json`, `picks/cache/preopen_candidates.json`를 합칩니다. 장전 후보와 시장 스냅샷에 새로 들어온 종목도 펀더멘탈 보강 대상에 포함됩니다.

## Enrichment (밸류에이션 보강)

기본 실행 시 OpenDART 수집 후 Google Finance와 DATA.GO.KR에서 밸류에이션 지표를 자동 보강합니다.

### Google Finance
- `https://www.google.com/finance/quote/{ticker}:KRX` 페이지에서 PER, 시가총액, 52주 고저, 배당수익률을 스크래핑합니다.
- 별도 인증 불필요. 네트워크 장애 시 해당 필드가 null로 남습니다.

### DATA.GO.KR (공공데이터포털)
- 금융위원회 주식시세정보 API에서 시가총액(`mrktTotAmt`)과 상장주식수(`lstgStCnt`)를 조회합니다.
- T+1 기준 데이터입니다.

### DATA.GO.KR 키 설정

공공데이터포털(https://www.data.go.kr)에서 '금융위원회_주식시세정보' API를 신청하고 인증키를 발급받습니다.

```powershell
setx DATA_GO_KR_API_KEY "발급받은_공공데이터포털_인증키(Decoding)"
```

또는 `.env.local`에 추가:

```
DATA_GO_KR_API_KEY=발급받은_공공데이터포털_인증키(Decoding)
```

### 밸류에이션 자동 계산

- PER: Google Finance → 시가총액 / 당기순이익
- PBR: 시가총액 / 자본총계
- EPS: Google Finance → 당기순이익 / 상장주식수
- BPS: 자본총계 / 상장주식수

보강을 건너뛰려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fundamentals.ps1 -SkipEnrich
```

## OpenDART 키 설정

OpenDART 인증키를 사용자 환경변수로 설정합니다. 키를 코드, README, 커밋에 넣지 마세요.

```powershell
setx OPENDART_API_KEY "발급받은_OpenDART_인증키"
```

새 PowerShell 창을 열어 환경변수를 확인합니다.

```powershell
echo $env:OPENDART_API_KEY
```

또는 git에 올라가지 않는 로컬 파일 `.env.local`에 저장할 수 있습니다.

```powershell
OPENDART_API_KEY=발급받은_OpenDART_인증키
```

`.env.local`은 `.gitignore`에 포함되어 커밋 대상에서 제외됩니다. 예시 파일은 `.env.example`입니다.

## pykrx 설치

`pykrx` provider를 사용할 때만 필요합니다.

```powershell
python -m pip install pykrx pandas
```

## 실행

전체 운영 종목 수집:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fundamentals.ps1
```

OpenDART 연도/보고서 지정:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fundamentals.ps1 -Provider opendart -BusinessYear 2025 -ReportCode 11011
```

특정 종목만 수집:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fundamentals.ps1 -Provider opendart -Tickers "005930,000660,006800"
```

pykrx로 특정 기준일과 시장 지정:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fundamentals.ps1 -Provider pykrx -Date 20260602 -Market ALL
```

네트워크 없이 검증용 샘플 생성:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fundamentals.ps1 -Provider offline_sample -SnapshotPath picks\cache\fundamentals_snapshot.test.json
```

`offline_sample`은 운영 기본 파일 `picks\cache\fundamentals_snapshot.json`에 직접 쓸 수 없습니다. 테스트/샘플 파일 경로를 명시해야 합니다.

## 산출물

`picks/cache/fundamentals_snapshot.json`

- `generated_at`: KST 생성 시각
- `date`: KRX 조회 기준일
- `provider`: `opendart`, `pykrx`, `offline_sample`
- `items[]`: 종목별 결과
- `items[].financial_indicators`: OpenDART 주요 재무지표
- `items[].account_values`: OpenDART 주요 계정값
- `items[].gate_metrics`: 운영 게이트용 핵심 지표(`roe`, `debt_ratio`, `current_ratio`, `operating_income_growth_yoy`, `revenue_growth_yoy`, `net_income_margin`)
- `items[].valuation_fields_available`: KRX daily valuation 필드 사용 가능 여부 (enrichment 후 true)
- `items[].bps`, `per`, `pbr`, `eps`, `div`, `dps`: pykrx provider에서 채워지는 KRX daily valuation 필드
- `items[].market_cap`: 시가총액 (Google Finance 또는 DATA.GO.KR)
- `items[].listed_shares`: 상장주식수 (DATA.GO.KR)
- `items[].week52_high`: 52주 최고가 (Google Finance)
- `items[].week52_low`: 52주 최저가 (Google Finance)
- `items[].enrichment_sources`: 보강에 사용된 소스 목록

이 수집기는 실시간 시세 수집기를 대체하지 않습니다. 네이버/토스 수집기는 장중 가격 확인용, OpenDART 수집기는 공시 기반 재무 건전성 확인용입니다.
