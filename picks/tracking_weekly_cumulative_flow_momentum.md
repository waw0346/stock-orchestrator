---
tracking_name: flow_momentum_weekly_cumulative
created_at: 2026-05-12
base_price_date: 2026-05-11
frequency: weekly
status: active
exit_rule: "If weekly close is at or below stop_loss, mark excluded_stop_loss and remove from active table in the next report."
---

# 수급·모멘텀 PICK 주간 누적 추적 보고서

기준 포트폴리오: `picks/2026-05-12_flow_momentum_picks.md`
최초 작성: 2026-05-12 01:00 KST

## Active Tracking

| 종목 | 코드 | 기준가 | 현재가 | 목표가 | 손절가 | 누적수익률 | 목표달성률 | 상태 | 최근점검 |
|------|------|--------|--------|--------|--------|------------|------------|------|----------|
| SK하이닉스 | 000660 | 1,880,000원 | 1,880,000원 | 2,160,000원 | 1,650,000원 | 0.0% | 0.0% | active | 2026-05-12 |
| 삼성전자 | 005930 | 285,500원 | 285,500원 | 330,000원 | 257,000원 | 0.0% | 0.0% | active | 2026-05-12 |
| 삼성SDS | 018260 | 173,900원 | 173,900원 | 200,000원 | 160,000원 | 0.0% | 0.0% | active | 2026-05-12 |

## Excluded Stop-Loss

| 제외일 | 종목 | 코드 | 제외가 | 기준가 대비 | 제외 사유 |
|--------|------|------|--------|-------------|-----------|
| - | - | - | - | - | - |

## Week 0: 2026-05-12

시장 상태:
- 작성 시각은 2026-05-12 01:00 KST로 KRX 정규장 전이다.
- 최초 기준가는 모두 2026-05-11 종가를 사용한다.

선정 요약:
- SK하이닉스: AI 메모리 수급 집중과 신고가 추세가 가장 강하지만 RSI 과열이 커서 손절 규칙 엄격 적용.
- 삼성전자: 외국인 순매수 집중과 대형 반도체 랠리 중심축. 단기 과열이나 거래량 동반 상승.
- 삼성SDS: KKR 투자와 AI 인프라 기대. 상대적으로 RSI 부담이 낮아 보완형 모멘텀 픽.

다음 업데이트:
- 2026-05-18 장 마감 후 주간 종가 기준으로 누적 수익률·목표달성률·손절 제외 여부 업데이트.

통합 실행 검증:
- 2026-05-12 01:24 KST 기준 `scripts/validate_project.ps1` 실행 결과 Errors 0, Warnings 0.
- `tests/run_validation_tests.ps1` 및 `tests/run_integration_tests.ps1` 통과.
- 전용 에이전트 `flow-momentum-tracker` 생성 및 주간 자동 모니터링 작업 `flow-momentum-weekly-tracker`와 연결 완료.
