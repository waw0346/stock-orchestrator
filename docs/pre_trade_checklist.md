# Pre-Trade Checklist

신규 픽 발행 또는 포지션 확대 전 반드시 점검한다. Hard Block에 하나라도 걸리면 픽 저장 또는 비중 확대를 보류한다.

## Hard Block

- 손절선 또는 무효화 조건이 없다.
- Bear Case 손실폭이 Base Case 기대수익보다 크다.
- 최근 공시에서 횡령, 배임, 감사의견, 대규모 유상증자, 관리종목, 불성실공시 등 Critical 이슈가 확인됐다.
- 단일 종목 비중이 INVESTMENT_POLICY.md의 상한을 초과한다.
- 동일 업종 노출이 총자산의 25%를 초과한다.
- 실시간 데이터가 필요한 판단인데 모든 핵심 데이터가 학습 데이터 기반이다.
- 최근 급등으로 진입가가 손절선 대비 과도하게 멀어져 손익비가 1.5:1 미만이다.

## Quality Gate

- 사업 모델과 이익 동인이 한 문장으로 설명된다.
- 최근 3년 매출/영업이익/순이익 방향성이 확인됐다.
- 수급과 모멘텀이 가격 시나리오와 충돌하지 않는다.
- 산업 국면이 Bull/Base/Bear 시나리오에 반영됐다.
- Critical 리스크가 없거나, 발생 시 대응 조건이 명확하다.
- 목표가보다 먼저 손절/무효화 조건이 기록됐다.
- 재점검 날짜와 모니터링 이벤트가 있다.

## Position Gate

- 손절 도달 시 계좌 손실이 0.5%~1.0% 범위 안에 있다.
- 고변동성 종목은 총자산 3% 이하로 제한했다.
- 신규 편입 후 최소 현금 비중을 유지한다.
- 기존 보유/추천픽과 상관관계가 과도하지 않다.

## Output Requirement

최종 리포트에는 아래 문장을 포함한다.

```text
Pre-Trade Gate: PASS|HOLD|BLOCK
Portfolio Fit: PASS|HOLD|BLOCK
Position Size: 총자산 대비 X%, 손절 시 예상 손실 Y%
Market Regime: Risk-On|Neutral|Risk-Off
```
