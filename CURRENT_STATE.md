# Current Project State

기준일: 2026-06-12

이 파일은 현재 운영 기준을 빠르게 확인하기 위한 상태표입니다. 내용 충돌 시 `CLAUDE.md` 및 `INVESTMENT_POLICY.md`가 최우선 기준입니다. 이 파일은 참고용 현황 요약이며 자동 갱신되지 않습니다.

## Canonical Files

- `README.md` — 최신 사용 설명서
- `CLAUDE.md` — 최신 오케스트레이터 운영 지침
- `INVESTMENT_POLICY.md` — 최상위 투자 운영 정책
- `docs/pre_trade_checklist.md` — 신규 픽 발행 전 체크리스트
- `docs/deca_system_spec.md` — DECA 실시간 모니터 및 모의투자 시스템 사양서
- `.mcp.json` — PlayMCP 프로젝트 MCP 설정
- `scripts/validate_project.ps1` — 운영 구조 검증
- `scripts/review_changes.ps1` — 변경사항 위험도 점검
- `tests/run_all_tests.ps1` — 전체 검증 루틴

## DECA (실시간 모니터 및 모의투자) 스킬
- `scripts/generate_vwap_anchors.py` — VWAP 기준 평단가 닻 생성기
- `scripts/check_morning_disclosure.py` — 장전 공시 악재 블랙리스트 생성기
- `scripts/realtime_stock_monitor.py` — 실시간 감시 및 가상 매매 체결 엔진
- `scripts/check_deca_trigger.py` — 실시간 뉴스 및 공시 인지형 검증 스크립트

## Archived Files

아래 파일은 보관본입니다. 최신 운영 기준으로 사용하지 않습니다.

- `README_v2.md`
- `CLAUDE_v2.md`
- `00_setup_guide.md`
- `01_project_instructions.md`
- `.claude/agents/kfc/` — 과거 설계 스펙 보관본 (서브폴더에 위치, 에이전트로 자동 인식되지 않음. 정식 아카이브: `docs/archive/kfc/`)

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
- `theme-tracker`

운영 통제 및 메타인지:
- `market-regime-analyst`
- `portfolio-manager`
- `position-sizing-analyst`
- `performance-reviewer`
- `metacognitive-analyst`
- `deca-analyst` — DECA 실시간 인지형 감사 에이전트

스크리닝:
- `preopen-foreign-scanner`
- `pullback-analyst`

기록/DB:
- `obsi` — Obsidian Vault 기록, 오류 메모, 실행 로그, Todo 분류 관리


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
powershell -ExecutionPolicy Bypass -File .\tests\run_market_radar_tests.ps1
powershell -ExecutionPolicy Bypass -File .\tests\run_paper_trading_tests.ps1

# 밸류에이션 보강 포함 펀더멘탈 수집
powershell -ExecutionPolicy Bypass -File .\scripts\collect_fundamentals.ps1

# 보강 없이 OpenDART만 수집
powershell -ExecutionPolicy Bypass -File .\scripts\collect_fundamentals.ps1 -SkipEnrich

# 장마감 후 외국인 연속 순매수 후보 스캔
powershell -ExecutionPolicy Bypass -File .\scripts\find_foreign_streaks.ps1 -InputCsvPath .\picks\cache\foreign_flow_history.csv

# 장전/장중/장후 장기투자 시황 레이더
powershell -ExecutionPolicy Bypass -File .\scripts\run_market_radar.ps1 -Mode intraday
```

## Known Operational Note

`picks/*.md` 파일은 투자 리서치 기록입니다. 과거 발행 당시 표현이 현재 정책 표현과 다를 수 있으므로, 최신 판단은 frontmatter, review_history, `picks/INDEX.md`, Capital Protection Gate 섹션을 우선합니다.
