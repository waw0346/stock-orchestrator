# Flow Comparison & ETF Filtering Pipeline

`scripts/run_flow_comparison.py`는 실시간 장중(Intraday) 수급과 장마감 후(After-Close) 수급을 비교하여 메이저 세력(외국인, 연기금)의 흐름 변화를 추적하고, ETF와 일반 주식을 자동으로 분류해주는 자체 스크리닝 파이프라인입니다.

---

## 🎯 주요 기능

1. **ETF / 일반 주식 자율 분류 (ETF Filtering)**
   * 국내 ETF 브랜드 접두사명(`KODEX`, `TIGER`, `RISE`, `PLUS`, `ACE`, `SOL`, `HANARO` 등)을 바탕으로 수집된 종목들을 `ETF`와 `STOCK`으로 100% 분리 분류합니다.
2. **장중 vs 장마감 수급 비교 (Divergence 계산)**
   * 동일 거래일의 장중 수급 스냅샷과 장마감 후의 최종 확정 수급을 비교합니다.
   * **Divergence (종가 괴리도)** = `장마감 최종 순매수` - `장중 실시간 순매수`
   * 이 수치로 장 후반 또는 종가 동시호가에서 급격히 매수가 유입된 종목(Positive Divergence)과 매도가 집중된 종목(Negative Divergence)을 가려냅니다.

---

## 💾 파일 구조 및 캐시 규격

### 1. 누적 데이터베이스 (`picks/cache/flow_comparison_history.json`)
매일 기록된 장중 및 장마감 데이터를 누적 저장합니다.
```json
{
  "2026-06-08": {
    "intraday": {
      "generated_at": "2026-06-08T10:00:00+09:00",
      "foreign_buy": [ { "ticker": "005930", "name": "삼성전자", "net_buy": 1000, "close": 75000, "volume": 100000 }, ... ],
      "foreign_sell": [...],
      "pension_buy": [...],
      "pension_sell": [...]
    },
    "after_close": {
      "generated_at": "2026-06-08T16:00:00+09:00",
      "foreign_buy": [ { "ticker": "005930", "name": "삼성전자", "net_buy": 1800, "close": 75000, "volume": 120000 }, ... ],
      "foreign_sell": [...],
      "pension_buy": [...],
      "pension_sell": [...]
    }
  }
}
```

### 2. 최신 비교 결과 (`picks/cache/flow_comparison_latest.json`)
마지막 분석의 요약 보고서와 분류 목록, 괴리 분석 결과가 저장됩니다.
* **주요 필드**:
  * `has_comparison`: `true`일 경우 장중/장마감 괴리도가 계산되어 `divergences` 노드에 탑재됩니다.
  * `etfs`: 외국인/연기금 매수/매도 ETF 리스트
  * `stocks`: 외국인/연기금 매수/매도 일반 주식 리스트
  * `divergences`: 카테고리별 종가 매수 유입/매도 이탈 Top 5 종목군

---

## 🚀 실행 가이드

### A. 네트워크 배제 검증 (Offline Sample Mode)
실제 API 키 없이 로컬 목 데이터를 시뮬레이션하여 데이터 비교 엔진의 정상 작동을 확인합니다.

```powershell
# 1단계: 장중 상태 시뮬레이션 기록 ( flow_comparison_history.json 에 intraday가 저장됨 )
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_comparison.ps1 -Mode Intraday -OfflineSample

# 2단계: 장마감 후 비교 시뮬레이션 ( 1단계에 저장된 데이터와 비교하여 괴리도 계산 및 마크다운 출력 )
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_comparison.ps1 -Mode AfterClose -OfflineSample
```

### B. 실시간 API 연동 모드
장중과 장마감 후에 정기 스케줄 또는 수동 실행을 통해 수급 변화를 추적합니다.

```powershell
# 1. 장중 (09:00 ~ 15:30) 실행: 당일 실시간 장중 스냅샷 기록
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_comparison.ps1 -Mode Intraday

# 2. 장마감 후 (15:30 이후) 실행: 당일 최종 마감 데이터를 가져와 장중 데이터와 괴리 비교 리포트 출력
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_comparison.ps1 -Mode AfterClose
```
* **자동 감지**: `-Mode` 인수를 생략하면 KST 현재 시각을 기준으로 자동 감지하여 실행됩니다.

---

## 🚦 활용 규칙
이 비교 분석 결과는 세력들이 장 후반 동시호가에 집중 매수한 '종가 배팅' 종목군 및 반대로 장중에 강하게 샀다가 마감 때 개인에게 떠넘긴 종목군을 잡아내어, 익일 장전 전략(`us-close-korea-strategist`)을 보강하고 매수 진입 검토 리스트에 추가할 후보군 선별에 도움을 줍니다.
투자 비중 설정 전 리스크 확인용이며 직접적인 매매 지시어가 아닙니다.
