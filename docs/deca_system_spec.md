# 📊 DECA (Deterministic Engine + Cognitive AI Agent) System Specification

본 규격서는 **DECA 시스템**의 구동 방식, 수학적 지표 공식, 파일 교환 규격 및 다종 인공지능(Cross-AI) 환경에서의 호환성 표준을 정의합니다. 본 문서를 통해 상이한 AI 모델 및 실행 환경에서도 시스템의 작동 원리를 100% 이해하고 참여 및 보완할 수 있습니다.

---

## 1. 시스템 아키텍처 및 철학 (Architecture Overview)

DECA는 **결정론적 규칙 엔진(Deterministic Engine)**과 **인지적 판단 에이전트(Cognitive AI Agent)**를 파일 기반으로 느슨하게 결합(Loose Coupling)한 2-티어 아키텍처입니다.

*   **Deterministic Engine (`realtime_stock_monitor.py`)**: 실시간 데이터 폴링, 수치 지표 연산, 손절/익절 청산 등의 기계적 영역을 100% 신뢰성 있게 처리합니다.
*   **Cognitive AI Agent (`deca-analyst`, `check_deca_trigger.py`)**: 실시간 유입되는 대량의 복잡한 정성적 뉴스, 기업 비하인드 이슈, 공시 맥락 등을 인지적으로 감사(Audit)하여 불확실성을 최종 통제합니다.

```
+------------------------------------------------------------+
|                  Deterministic Engine                      |
|  - 5s Naver Price/Vol Polling                              |
|  - RVOL & Vol Power Calculation                            |
|  - Undercut & Spring State Machine                         |
|  - simulation_ledger.csv virtual exits (+7% / -4%)         |
+-----------------------------+------------------------------+
                              |
                     Writes deca_trigger.json
                              |
                              v
+------------------------------------------------------------+
|                   Cognitive AI Agent                       |
|  - Scrapes 6-Hour news list for triggered ticker           |
|  - Filters bad news keywords (litigation, deficit, etc.)   |
|  - Writes deca_audit_result.json (PASS/BLOCK)              |
+------------------------------------------------------------+
```

---

## 2. 파일 교환 규격 (Data Exchange Schemas)

모든 모듈은 메모리가 아닌 파일 인터페이스를 통해 협업하므로, 어떠한 AI나 스크립트도 아래 JSON/CSV 파일을 읽고 씀으로써 시스템에 참여할 수 있습니다.

### ① `picks/cache/vwap_anchors.json` (VWAP 기준 평단가)
장 전 전일(D-1) 마감 후 세력의 매집 평균단가를 닻(Anchor)으로 지정합니다.
```json
{
  "generated_at": "2026-06-12 00:00:00",
  "base_date": "2026-06-11",
  "model_name": "VWAP Baseline Anchor Model",
  "tickers": {
    "066570": {
      "name": "LG전자",
      "ticker": "066570",
      "base_date": "2026-06-11",
      "close_baseline": 226000,
      "vwap_ma20": 226000.0,
      "formulas_documentation": {
        "undercut_and_spring_threshold": "Threshold = vwap_ma20 * 0.96 (Undercut by 4%)",
        "spring_recovery_trigger": "Price recoveries back above vwap_ma20 * 0.98"
      }
    }
  }
}
```

### ② `picks/cache/volume_anchors.json` (시간대별 기대 누적 거래량)
U자형 Intraday Volume 분포 모델을 사용하여, 15분 단위로 하루의 기대 거래량 비율을 산출합니다.
*   **RVOL 연산**: `RVOL(T) = Actual_Cumulative_Volume / Expected_Cumulative_Volume_At_T`
```json
{
  "generated_at": "2026-06-12 11:04:45",
  "model_name": "U-shaped Intraday Volume Model",
  "anchors": {
    "066570": {
      "name": "LG전자",
      "ticker": "066570",
      "vol_avg20_daily": 4667702,
      "time_slices_15m": {
        "09:15": { "ratio": 0.1000, "expected_cum_vol": 466770 },
        "09:30": { "ratio": 0.2000, "expected_cum_vol": 933540 }
      }
    }
  }
}
```

### ③ `picks/cache/deca_trigger.json` (장중 매수 경보 신호)
결정론적 조건 충족 시 실시간 생성되는 AI 호출장입니다.
```json
{
  "timestamp": "2026-06-12 09:45:00",
  "ticker": "066570",
  "name": "LG전자",
  "price": 224500,
  "vwap": 226000.0,
  "rvol": 2.14,
  "volume_power": 135.0,
  "trigger_type": "Spring_Recovery"
}
```

### ④ `picks/cache/deca_audit_result.json` (AI 인지형 최종 결과 보고서)
AI 에이전트의 뉴스 심사 결과서입니다.
```json
{
  "timestamp": "2026-06-12 11:39:00",
  "ticker": "066570",
  "name": "LG전자",
  "decision": "PASS",
  "reasons": [],
  "audited_news_count": 1,
  "fresh_news_list": [
    {
      "title": "25거래일 만에 사자 돌아온 外人",
      "publisher": "문화일보",
      "time": "2026-06-12 11:39:00",
      "url": "https://n.news.naver.com/..."
    }
  ]
}
```

### ⑤ `picks/cache/simulation_ledger.csv` (모의투자 장부)
모든 모의투자 기록이 저장되는 가상 원장입니다.
*   **헤더 구조**: `trade_id,ticker,name,entry_time,entry_price,exit_time,exit_price,exit_reason,status,target_price,stop_loss,rvol,volume_power,profit_pct`
*   **상태 값**: `HOLDING` (보유 중), `CLOSED` (청산 완료)

---

## 3. 핵심 규칙 및 연산 공식 (Algorithms & Logic)

### ① 실시간 체결강도 (Volume Power) 동적 추정 공식
Naver Finance 실시간 API는 체결강도를 직접 반환하지 않으므로, 엔진이 메모리 상에서 아래 규칙으로 틱단위 추정합니다.
*   **가격 상승 틱 ($P_t > P_{t-1}$)**: $Volume_{tick}$을 $Buy\_Volume$에 누적.
*   **가격 하락 틱 ($P_t < P_{t-1}$)**: $Volume_{tick}$을 $Sell\_Volume$에 누적.
*   **가격 보합 틱 ($P_t = P_{t-1}$)**: 직전 틱 방향을 그대로 추종하여 누적.
*   **체결강도 공식**:
    $$Volume\_Power (\%) = \left( \frac{Buy\_Volume}{Sell\_Volume} \right) \times 100$$

### ② 언더컷 & 스프링 역전 상태 머신 (State Machine)
*   **Undercut 진입**: 주가가 $VWAP\_Anchor \times 0.98$ 이하로 떨어질 때 `undercut = True`로 활성화.
*   **Spring Trigger (KOSPI/KOSDAQ)**: `undercut`이 `True`인 상태에서 주가가 $VWAP\_Anchor \times 0.99$ 이상으로 회복하고, 동시 조건 $RVOL \ge 1.5$ 및 $Volume\_Power \ge 105\%$ 달성 시 매수 트리거 발동.
*   **Corning(GLW) 상관성 트리거**: 미국 코닝(GLW)의 전일 종가가 $VWAP\_Anchor \times 0.98$ 이하로 하락하여 마감했을 경우, 국내 상관 종목인 대한광통신(010170)이 자신의 $VWAP\_Anchor$ 가격선 위로 올라서는 즉시 `Spring_Recovery` 매수 트리거를 인정함.

### ③ 자동 청산 규칙 (Auto-Exit Rules)
가상 매수 진입 시점 대비:
*   **목표가 (Target Profit)**: $+7\%$ 도달 시 즉시 청산 (`exit_reason: "TARGET"`)
*   **손절가 (Stop Loss)**: $-4\%$ 도달 시 즉시 청산 (`exit_reason: "STOP_LOSS"`)

---

## 4. 다종 인공지능 및 런타임 호환성 가이드 (Cross-AI Adaptation)

본 프로젝트는 어떠한 환경에서도 다른 AI가 분석에 참여하고 보완할 수 있도록 설계되었습니다.

1.  **동작 검증 및 스킬 실행**:
    - **가상 테스트 시뮬레이션**: `python scripts/realtime_stock_monitor.py --mock`
    - **장전 공시 블랙리스트 갱신**: `python scripts/check_morning_disclosure.py`
    - **장중 실시간 뉴스 감사**: `python scripts/check_deca_trigger.py`
2.  **타사 AI 참여 시 시나리오**:
    - **수집기 확장**: Naver 외에 다른 증권사 API나 키움 API를 붙이고자 할 때, 수집 스크립트에서 시세 추출 후 `realtime_stock_monitor.py`에 맞추어 `picks/cache/monitor_ticks.jsonl`에 한 줄만 써주면 메모리가 자동 동기화됩니다.
    - **에이전트 변경 (예: GPT-4o, Claude 3.5 Sonnet)**: 에이전트는 `.claude/agents/deca-analyst.md` 프롬프트 사양서에 적힌 역할과 `deca_trigger.json` 포맷을 참고하여 자기 런타임에 맞게 최종 승인 루프를 개발 및 교체할 수 있습니다.
3.  **크로스 플랫폼 사운드 가드**:
    - `winsound` 라이브러리는 Windows 전용이므로 Linux, macOS, headless 컨테이너 환경에서 실행 시 `ImportError`를 감지하여 텍스트 알람(`\a`) 및 콘솔 출력으로 안전하게 자동 전환됩니다.
