# Fiscal.ai 연결 방안

Fiscal.ai는 회사 프로필, 표준화 재무제표, 비율, KPI, 주가, 공시, 뉴스 데이터를 제공하는 금융 데이터 API입니다. 한국장 외국인/기관 순매수 데이터를 직접 대체하는 원천으로 보기는 어렵고, 이 프로젝트에서는 펀더멘탈/공시/뉴스/가격 보강 provider로 쓰는 것이 맞습니다.

## 인증

Fiscal.ai 문서 기준 API key는 두 방식으로 사용할 수 있습니다.

- REST API: 요청마다 `apiKey` 파라미터 또는 `X-Api-Key` 헤더 사용
- MCP: `Authorization: Bearer <key>` 헤더 사용

환경변수:

```powershell
setx FISCAL_AI_API_KEY "발급받은_Fiscal_ai_API_key"
```

## MCP 연결

Fiscal.ai MCP 서버:

```text
https://api.fiscal.ai/mcp
```

Claude Code 방식:

```powershell
claude mcp add --transport http fiscal https://api.fiscal.ai/mcp --header "Authorization: Bearer YOUR-API-KEY"
```

일반 MCP JSON 형태:

```json
{
  "mcpServers": {
    "fiscal": {
      "url": "https://api.fiscal.ai/mcp",
      "headers": {
        "Authorization": "Bearer ${FISCAL_AI_API_KEY}"
      }
    }
  }
}
```

## REST API 사용 후보

공식 문서에서 확인한 주요 endpoint 범위:

- `GET /v2/companies-list`: 지원 회사 목록
- `GET /v2/company/profile`: 회사 프로필
- 재무제표/비율/KPI/조정 지표
- `GET /v2/company/filings`: 회사 공시 목록
- 주가/인트라데이 주가
- 회사 뉴스/상위 뉴스

## 연결 점검

키가 `.env.local` 또는 환경변수에 설정되어 있으면 다음 명령으로 Fiscal.ai 연결을 확인할 수 있습니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_fiscal_ai.ps1 -CompanyKey NASDAQ_MSFT
```

점검 스크립트는 키 값을 출력하지 않고 `key_present=true` 여부와 요청 결과만 표시합니다.

## 스냅샷 수집

미국장 신호 보강용 회사 프로필 스냅샷을 만들 수 있습니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fiscal_ai.ps1 -CompanyKeys "NASDAQ_MSFT,NASDAQ_NVDA,NASDAQ_AAPL"
```

산출물:

`picks/cache/fiscal_ai_snapshot.json`

- `items[].company_key`: Fiscal.ai company key
- `items[].name`: 회사명
- `items[].sector`, `items[].industry`: 가능한 경우 업종/산업
- `items[].source`: `fiscal_ai` 또는 `offline_fixture`

키/플랜에서 접근 가능한 회사 목록 일부를 확인하려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fiscal_ai.ps1 -ListCompanies -PageSize 25
```

이 결과는 Fiscal.ai plan/company coverage 점검에 사용합니다.

최신 투자 관련 뉴스/이벤트를 수집하려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fiscal_ai.ps1 -TopNews -PageSize 25 -SnapshotPath picks\cache\fiscal_ai_investment_news.json
```

기본 event type은 `earnings`, `guidance`, `buyback`, `ma`, `partnership`, `financing`, `analyst`, `market_commentary`, `technology`, `product_launch`, `expansion`, `regulatory`입니다. `importance` 1~3만 수집해 후보판의 보조 리서치 맥락으로 사용합니다.

`top-news`가 키/플랜에서 제한될 경우 회사별 최신 뉴스를 수집합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_fiscal_ai.ps1 -CompanyNews -CompanyKeys "NASDAQ_MSFT,NASDAQ_NVDA" -PageSize 10 -SnapshotPath picks\cache\fiscal_ai_investment_news.json
```

회사 뉴스도 같은 event type과 `importance` 필터를 적용합니다. 산출물은 `items[].title`, `items[].summary`, `items[].event_type`, `items[].importance`, `items[].source_url`, `items[].collected_at`을 포함하며, 미국장 AI/반도체/클라우드 촉매를 한국장 후보 해석에 붙이는 보조 입력으로 씁니다.

Fiscal.ai 공식 문서에서 확인된 직접 원천은 `company/news`, `top-news`, `company/filings`입니다. 투자자 서신이나 earnings call 회의록/transcript 전용 endpoint는 현재 API reference에서 별도 확인되지 않았으므로, 관련 내용은 공시(`filings`)와 뉴스 이벤트로 우선 대체합니다.

## 프로젝트 적용 위치

1. `collect_fundamentals.py` 보조 provider
   - OpenDART가 약한 글로벌 비교, 표준화 재무비율, KPI 보강
   - `provider=fiscal_ai` 후보

2. `collect_us_close_data.py` 보조 provider
   - Yahoo chart 실패 시 미국 주가/뉴스 보강
   - 미국장 마감 신호의 설명력 강화

3. `candidate_board.json` 보강 필드
   - `fiscal_ai_profile`
   - `fiscal_ai_ratios`
   - `fiscal_ai_news`
   - 단, 한국 투자자별 수급 필드의 대체값으로 사용하지 않음

## 주의

- Fiscal.ai 무료 플랜은 접근 가능한 회사와 호출 수가 제한될 수 있습니다.
- 회사 식별자는 미국/캐나다는 `NASDAQ_MSFT` 같은 exchange+ticker 형식, 그 외 국가는 MIC 기반 company key를 사용합니다.
- 한국 종목 커버리지는 실제 API key로 `companies-list` 조회 후 확인해야 합니다.
