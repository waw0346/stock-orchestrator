# 추천픽 리포트 템플릿

## Phase 4 리포트 형식

```markdown
# 📌 [종목명] ([종목코드]) 추천픽
**발행일**: YYYY-MM-DD | **현재가**: XX,XXX원 | **시가총액**: X조원

## 🎯 투자의견 종합
**등급**: ⭐⭐⭐⭐☆ (5점 만점)
**시간 지평**: 단기(1~3M) / 중기(3~12M) / 장기(12M+)
**확신도**: 높음 / 중간 / 낮음
**데이터 품질**: 실시간 / 부분실시간 / 학습데이터기반

## 📊 7단계 분석 요약

### 1️⃣ 기업분석
[company-analyst 핵심 발견 3~4줄]

### 2️⃣ 재무분석
[financial-analyst 핵심 발견 3~4줄 + 핵심 수치]

### 3️⃣ 산업분석
[industry-analyst 핵심 발견 3~4줄]

### 4️⃣ 모멘텀분석
[momentum-analyst 핵심 발견 3~4줄]

### 5️⃣ 리스크요인분석
[risk-analyst 핵심 발견 — 🔴 Critical / 🟡 Warning 위주]

### 6️⃣ 외국인/기관동향
[flow-analyst 핵심 발견 3~4줄]

### 7️⃣ 종합의견
**Bull Case** (확률 X%): [조건 → 기대 가격 X원]
**Base Case** (확률 X%): [조건 → 예상 가격 X원]
**Bear Case** (확률 X%): [조건 → 하락 가능 X원]

## 📍 추천 포지션
- **진입 가격대**: XX,XXX원 ~ XX,XXX원
- **1차 목표가**: XX,XXX원 (+X%)
- **2차 목표가**: XX,XXX원 (+X%)
- **손절선**: XX,XXX원 (-X%)
- **권장 포지션 크기**: 총자산 대비 X%
- **손절 시 예상 계좌 손실**: 총자산 대비 Y%
- **분할 진입 계획**: 1차/2차/3차 조건

## 🛡️ Capital Protection Gate
- **Market Regime**: Risk-On / Neutral / Risk-Off
- **Pre-Trade Gate**: PASS / HOLD / BLOCK
- **Portfolio Fit**: PASS / HOLD / BLOCK
- **Position Size**: PASS / HOLD / BLOCK
- **차단/보류 사유**: [있으면 명시]

## 🔍 모니터링 포인트
[향후 점검할 핵심 이벤트/지표 3~5개]

---
*본 자료는 공개 데이터 기반 리서치이며, 투자 권유가 아닙니다.*
```

## Phase 5 픽 파일 frontmatter 스키마

```yaml
---
date: YYYY-MM-DD
ticker: "005930"
name: 삼성전자
market: KOSPI
sector: 반도체
rating: 4
horizon: 중기
entry_price_low: 70000
entry_price_high: 73000
target_1: 85000
target_2: 95000
stop_loss: 62000
current_price_at_pick: 71500
status: active
data_quality: 실시간|부분실시간|학습데이터기반
last_review: YYYY-MM-DD
review_history: []
---
```

## INDEX.md 행 형식

```
| YYYY-MM-DD | 005930 | 삼성전자 | ⭐⭐⭐⭐ | 중기 | 71,500원 | - | - | active | YYYY-MM-DD |
```

## 에이전트 JSON 출력 형식

모든 서브에이전트 프롬프트 마지막에 반드시 포함:

```
[출력 형식 — 반드시 준수]
분석 완료 후 다음 JSON을 응답의 맨 마지막에 추가하세요.

```json
{
  "agent": "company|industry|flow|financial|momentum",
  "ticker": "종목코드",
  "data_date": "YYYY-MM-DD",
  "data_source": "실시간|학습데이터(YYYY-MM)",
  "findings": ["핵심발견1", "핵심발견2", "핵심발견3"],
  "key_metrics": {"지표명": "값"},
  "risk_candidates": ["잠재리스크1", "잠재리스크2"],
  "confidence": "높음|중간|낮음",
  "signal": "긍정|중립|부정"
}
```

도구 권한 거부 시: 중단 금지. 학습데이터로 계속, data_source="학습데이터(YYYY-MM)", confidence="낮음", 텍스트 상단 ⚠️ 한 줄.
```
