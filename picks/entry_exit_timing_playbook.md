---
created_at: 2026-05-12
source_pick_file: picks/2026-05-12_flow_momentum_picks.md
source_tracking_file: picks/tracking_weekly_cumulative_flow_momentum.md
agent: entry-exit-timing-strategist
status: active
---

# 진입·청산 타이밍 플레이북

기준일: 2026-05-12 01:30 KST
가격 기준: 2026-05-11 종가
원본 PICK: `picks/2026-05-12_flow_momentum_picks.md`

> No direct trading instruction. 이 문서는 공개 데이터 기반 리서치와 조건부 시나리오이며, 실제 매매 지시가 아닙니다.

## 종합 판단

| 종목 | 타이밍 등급 | entry_zone | stop_loss | exit_plan | Kelly-style sizing |
|------|-------------|------------|-----------|-----------|--------------------|
| SK하이닉스 | A: Wait for pullback | 1,700,000~1,780,000원 또는 RSI 70 이하 진정 후 재상승 | 1,650,000원 | 2,050,000원 근접 시 1차 축소, 2,160,000원 도달 시 목표 점검 | 최대 3~5% 관찰 비중 |
| 삼성전자 | B: Probe only | 270,000~278,000원 눌림 또는 288,500원 돌파 후 안착 | 257,000원 | 315,000원 1차, 330,000원 목표 도달 시 추세 보유 여부 재평가 | 최대 4~6% 분할 비중 |
| 삼성SDS | C: Confirm breakout | 168,000~174,000원 지지 확인 또는 180,000원 거래량 돌파 | 160,000원 | 190,000원 1차, 200,000원 도달 시 절반 이상 방어적 축소 검토 | 최대 3~4% 관찰 비중 |

## SK하이닉스 (000660)

- 타이밍 등급: A: Wait for pullback
- entry_zone: 1,700,000~1,780,000원 눌림 후 종가 회복, 또는 RSI 70 이하 진정 뒤 전일 고점 재돌파 확인
- add_zone: 1,900,000원 위에서 거래량이 20일 평균을 재상회하고 외국인 순매수가 유지될 때만 소폭 증액 검토
- avoid_zone: RSI 85 이상에서 1,900,000원 위 추격 구간
- stop_loss: 1,650,000원 종가 이탈 시 전략 무효화 및 추적 제외
- exit_plan: 2,050,000원 근접 시 일부 수익 보호, 2,160,000원 도달 시 목표 달성으로 주간 보고서에서 재평가
- invalidation: HBM/AI 메모리 모멘텀 약화, 외국인 2주 연속 순매도, 20일선 이탈 후 회복 실패
- Kelly-style sizing: 급등 과열과 변동성을 감안해 이론적 Kelly가 아니라 1/4 이하의 관찰 비중만 허용
- weekly_monitoring: RSI 70 이하 진정 여부, 외국인 순매수 지속, 52주 고점 재돌파 여부

## 삼성전자 (005930)

- 타이밍 등급: B: Probe only
- entry_zone: 270,000~278,000원 눌림에서 거래량 감소와 외국인 매수 유지 확인, 또는 288,500원 돌파 후 2거래일 이상 안착
- add_zone: 300,000원 위에서 KOSPI 전기전자 업종 상대강도가 유지될 때
- avoid_zone: 뉴스 없이 300,000원 위로 단기 급등하는 구간
- stop_loss: 257,000원 종가 이탈 시 모멘텀 훼손으로 추적 제외
- exit_plan: 315,000원 근접 시 일부 방어, 330,000원 도달 시 목표가 달성으로 추세 지속 여부 재평가
- invalidation: 반도체 대형주 수급 이탈, 파업/공급망 이벤트 확대, 20일선 이탈 후 회복 실패
- Kelly-style sizing: 대형주 유동성은 우수하나 과열 구간이므로 분할 비중을 4~6% 이내로 제한
- weekly_monitoring: 외국인 순매수 순위 유지, 288,500원 돌파 안착, 거래량 동반 여부

## 삼성SDS (018260)

- 타이밍 등급: C: Confirm breakout
- entry_zone: 168,000~174,000원 지지 확인 또는 180,000원 거래량 돌파
- add_zone: 185,000원 위에서 KKR/AI 인프라 모멘텀이 재확인될 때
- avoid_zone: 190,000원 위에서 거래량 없이 상승하는 구간
- stop_loss: 160,000원 종가 이탈 시 4월 이벤트 상승분 훼손으로 추적 제외
- exit_plan: 190,000원 1차 수익 보호, 200,000원 도달 시 목표 달성으로 절반 이상 방어적 축소 검토
- invalidation: KKR 투자 기대 약화, AI 인프라 투자 뉴스 부재, 기관 매도 확대
- Kelly-style sizing: 과열 부담은 낮지만 촉매 의존도가 있어 3~4% 관찰 비중 이하가 적절
- weekly_monitoring: 180,000원 돌파 거래량, 기관 수급 전환, 198,800원 52주 고점 접근 여부

## 공통 리스크 통제

- No direct trading instruction.
- 모든 가격 판단은 장중 터치보다 장마감 종가를 우선한다.
- 손절가 종가 이탈 종목은 `excluded_stop_loss`로 이동하고 다음 주간 추적에서 제외한다.
- 목표가 도달 종목은 신규 욕심보다 보유 thesis와 수급 지속 여부를 재검토한다.
- 시장 전체가 급락하면 개별 종목 모멘텀이 살아 있어도 신규 진입은 보류한다.

## 운영 연결

- 담당 에이전트: `entry-exit-timing-strategist`
- 주간 자동화: `flow-momentum-weekly-tracker`가 추적 보고서를 갱신한 뒤 이 플레이북의 `entry_zone`, `avoid_zone`, `exit_plan`, `Kelly-style sizing`을 함께 갱신한다.
- 마지막 통합 검증: 2026-05-12 01:41 KST, `tests/run_integration_tests.ps1`, `tests/run_validation_tests.ps1`, `scripts/validate_project.ps1` 통과.
