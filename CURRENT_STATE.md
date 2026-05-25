# Current Project State

기준일: 2026-05-18

이 파일은 현재 운영 기준을 빠르게 확인하기 위한 상태표입니다. 혼동이 생기면 이 파일과 `README.md`, `CLAUDE.md`를 우선합니다.

## Canonical Files

- `README.md` — 최신 사용 설명서
- `CLAUDE.md` — 최신 오케스트레이터 운영 지침
- `INVESTMENT_POLICY.md` — 최상위 투자 운영 정책
- `docs/pre_trade_checklist.md` — 신규 픽 발행 전 체크리스트
- `.mcp.json` — PlayMCP 프로젝트 MCP 설정
- `scripts/validate_project.ps1` — 운영 구조 검증
- `scripts/review_changes.ps1` — 변경사항 위험도 점검
- `tests/run_all_tests.ps1` — 전체 검증 루틴

## Archived Files

아래 파일은 보관본입니다. 최신 운영 기준으로 사용하지 않습니다.

- `README_v2.md`
- `CLAUDE_v2.md`
- `00_setup_guide.md`
- `01_project_instructions.md`

## Active Agent Groups

분석:
- `company-analyst`
- `financial-analyst`
- `industry-analyst`
- `momentum-analyst`
- `flow-analyst`
- `risk-analyst`

추적:
- `weekly-tracker`
- `monthly-tracker`
- `flow-momentum-tracker`
- `entry-exit-timing-strategist`
- `us-close-korea-strategist`

운영 통제:
- `market-regime-analyst`
- `portfolio-manager`
- `position-sizing-analyst`
- `performance-reviewer`

## Current Risk Controls

신규 픽 발행 전 필수 관문:

1. Market Regime
2. Portfolio Fit
3. Position Size
4. Pre-Trade Gate

`portfolio-manager` 또는 `position-sizing-analyst`가 `BLOCK`이면 신규 픽 저장 금지입니다.

## Pick Status Rules

- `active`: 추적 대상. 신규 또는 유지 판단.
- `watch`: 관찰 대상. 신규 대규모 편입 금지, 조건 충족 시 재검토.
- `closed`: 종료 또는 손절.
- `completed`: 목표 달성 완료.

`picks/INDEX.md`의 status와 개별 픽 frontmatter의 `status`는 반드시 일치해야 합니다. `validate_project.ps1`가 이 불일치를 잡습니다.

## Validation Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\tests\run_all_tests.ps1

# 개별 실행이 필요할 때:
powershell -ExecutionPolicy Bypass -File .\scripts\validate_project.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\review_changes.ps1
powershell -ExecutionPolicy Bypass -File .\tests\run_validation_tests.ps1
powershell -ExecutionPolicy Bypass -File .\tests\run_change_review_tests.ps1
powershell -ExecutionPolicy Bypass -File .\tests\run_integration_tests.ps1
powershell -ExecutionPolicy Bypass -File .\tests\run_paper_trading_tests.ps1
```

## Known Operational Note

`picks/*.md` 파일은 투자 리서치 기록입니다. 과거 발행 당시 표현이 현재 정책 표현과 다를 수 있으므로, 최신 판단은 frontmatter, review_history, `picks/INDEX.md`, Capital Protection Gate 섹션을 우선합니다.
