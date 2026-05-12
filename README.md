# 🏦 한국 주식 리서치 에이전트

증권사 리서치팀 구조로 설계된 Claude Code 기반 한국 주식 분석 에이전트입니다.
Anthropic의 [subagent 패턴](https://docs.claude.com/en/docs/claude-code/sub-agents)을 활용해
시니어 애널리스트 한 명과 6명의 전문 분석 에이전트, 2명의 추적 에이전트로 팀을 구성했습니다.

## 🎯 무엇을 할 수 있나요?

- **종목 풀 리서치**: 펀더멘털 + 시장 + 밸류에이션 + 기술 + 리스크 종합 분석
- **부분 분석**: "재무만", "리스크 점검만" 등 필요한 부분만 호출
- **종목 비교**: 두 개 이상 종목을 동일 기준으로 비교
- **산업 분석**: 특정 업종의 환경과 주요 종목 평가

## 🏗️ 아키텍처

```
┌────────────────────────────────────────────┐
│   메인 에이전트 (시니어 애널리스트)         │
│   CLAUDE.md — 작업 분배 & 종합              │
└─────┬──────────────────────────────────────┘
      │ 위임 (Agent tool)
      ↓
┌─────────────────────────────────────────────┐
│  서브에이전트 (.claude/agents/)             │
├─────────────────────────────────────────────┤
│  company-analyst    (기업·사업모델)         │
│  financial-analyst  (재무·DART)             │
│  industry-analyst   (산업·거시환경)         │
│  momentum-analyst   (주가·기술적 모멘텀)    │
│  flow-analyst       (외국인·기관 수급)      │
│  risk-analyst       (공시·다운사이드)       │
│  weekly/monthly-tracker (추천픽 추적)       │
│  flow-momentum-tracker (수급·모멘텀 추적)  │
│  entry-exit-timing-strategist (타이밍 전략)│
└─────────────────────────────────────────────┘
```

각 서브에이전트는:
- **독립된 컨텍스트 윈도우**에서 작업 → 메인 컨텍스트 절약
- **자기 역할에 필요한 도구만** 사용 가능
- **Project memory**로 분석 노하우 축적
- 결과를 **구조화된 요약**으로 메인에 반환

## 📦 디렉토리 구조

```
stock-analyst-agent/
├── README.md                          ← 이 파일
├── CLAUDE.md                          ← 시니어 애널리스트 페르소나
└── .claude/
    └── agents/
        ├── company-analyst.md
        ├── financial-analyst.md
        ├── industry-analyst.md
        ├── momentum-analyst.md
        ├── flow-analyst.md
        ├── risk-analyst.md
        ├── weekly-tracker.md
        ├── monthly-tracker.md
        ├── flow-momentum-tracker.md
        └── entry-exit-timing-strategist.md
├── picks/                              ← 추천픽 저장·추적
├── scripts/validate_project.ps1        ← 현재 시각 기준 운영 점검
└── tests/run_validation_tests.ps1      ← 검증 스크립트 테스트
```

## 🛠️ 설치

### 1. Claude Code 설치

```bash
# Node.js 18+ 필요
npm install -g @anthropic-ai/claude-code
```

설치 확인:
```bash
claude --version
```

### 2. 프로젝트 디렉토리 준비

이 패키지를 원하는 위치에 압축 해제 후, 해당 디렉토리로 이동:

```bash
cd path/to/stock-analyst-agent
```

### 3. PlayMCP (DART 데이터) 연결

PlayMCP는 한국 DART 전자공시 데이터를 제공하는 원격 MCP 서버입니다.

```bash
# 원격 MCP 서버 추가 (HTTP 방식)
claude mcp add --scope project playmcp \
  --transport http \
  https://playmcp.kakao.com/mcp
```

설치 후 인증이 필요합니다. Claude Code 실행 시 안내되는 URL로 접속해 카카오 계정으로 로그인하세요.

> 📝 **참고**: PlayMCP에 포함된 `opendart-*` 도구들이 한국 상장기업의
> 재무제표·공시·주주현황 데이터를 가져오는 핵심입니다.

### 4. 첫 실행

```bash
claude
```

세션이 시작되면 다음 명령으로 등록된 서브에이전트를 확인:

```
/agents
```

6개의 분석 에이전트와 2개의 추적 에이전트가 모두 보이면 정상입니다.

### 5. 운영 점검

현재 로컬 시간, KRX 정규장 여부, 에이전트 JSON 출력 계약, 추천픽 메타데이터를 점검합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\validate_project.ps1
```

테스트까지 확인하려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\run_validation_tests.ps1
```

## 🚀 사용법

### 풀 리서치 요청

```
삼성전자 분석해줘
```

시니어 애널리스트가 자동으로:
1. company, financial, industry, momentum, flow 분석을 **병렬** 실행
2. 그 결과를 받아 risk-analyst를 **순차** 실행
3. 모든 결과를 종합해 투자 분석 리포트 출력

### 특정 분석만 요청

```
@financial-analyst NAVER 재무 점검해줘
@risk-analyst 카카오 최근 공시 레드플래그 있는지 봐줘
```

`@` 멘션으로 특정 서브에이전트만 호출할 수 있습니다.

### 비교 분석

```
LG에너지솔루션과 삼성SDI 비교 분석해줘. 재무·밸류에이션 중심으로.
```

### 산업 분석

```
@industry-analyst 2026년 한국 반도체 산업 환경 분석해줘
```

### 수급·모멘텀 추적

```
수급·모멘텀 PICK 주간 누적 보고서 업데이트해줘
```

`@flow-momentum-tracker`가 `picks/2026-05-12_flow_momentum_picks.md`와
`picks/tracking_weekly_cumulative_flow_momentum.md`를 기준으로 목표가/손절가/누적수익률을 갱신합니다.
손절가를 종가 기준으로 이탈한 종목은 `excluded_stop_loss`로 제외됩니다.

### 진입·청산 타이밍 전략

```
수급·모멘텀 PICK의 진입 청산 전략 업데이트해줘
```

`@entry-exit-timing-strategist`가 버핏식 안전마진과 모멘텀 리스크 관리를 결합해
`picks/entry_exit_timing_playbook.md`에 `entry_zone`, `avoid_zone`, `stop_loss`, `exit_plan`,
`Kelly-style sizing`을 조건부 시나리오로 정리합니다.
직접 매매 지시가 아니라 리서치 기반 의사결정 프레임입니다.

## 💡 사용 팁

### 1. 분석 깊이 조절
- **빠른 점검**: "○○ 간단히 봐줘" → 시니어가 핵심 서브에이전트만 호출
- **풀 리서치**: "○○ 깊게 분석해줘" → 6개 분석 에이전트 모두 활용

### 2. 메모리 활용
- 같은 종목을 재분석하면 서브에이전트가 이전 노트를 참고합니다
- `.claude/agent-memory/`에 누적된 인사이트 확인 가능

### 3. 백그라운드 실행
긴 분석은 백그라운드로 돌리고 다른 작업 가능:
```
백그라운드로 셀트리온 풀 리서치 돌려줘
```

### 4. 서브에이전트 직접 편집
필요하면 `/agents` 명령으로 인터랙티브 편집:
- 시스템 프롬프트 수정
- 도구 권한 조정
- 모델 변경 (sonnet ↔ haiku ↔ opus)

## ⚠️ 한계와 면책

### 데이터 한계
- DART는 **분기 공시 기준**이라 최신 분기 미공시 시점에는 직전 분기 자료가 최신
- 실시간 시세는 웹 검색에 의존 — 약간의 시차 가능
- 비공개 정보(감독 당국 조사 등)는 알 수 없음

### 분석 한계
- 본 에이전트의 분석은 **공개 데이터 기반 리서치 자료**입니다
- **투자 권유나 자문이 아닙니다**
- 최종 투자 판단은 본인 책임입니다
- 생성된 정보의 정확성을 항상 교차 검증하세요

## 🔧 커스터마이징

### 자기만의 투자 철학 반영
`CLAUDE.md`를 편집해 시니어 애널리스트의 페르소나를 수정:
- 가치투자 / 성장주 / 모멘텀 / 배당주 등 투자 스타일 반영
- 선호 산업, 기피 산업 명시
- 보유 종목 워치리스트 추가

### 새 서브에이전트 추가
예시: ESG 전문가
```bash
/agents
```
인터랙티브 메뉴에서 "Create new agent" 선택 → 시스템 프롬프트 작성

### 모델 비용 최적화
간단한 작업은 Haiku로:
```yaml
# financial-analyst.md 상단
model: haiku  # 비용 절감, 약간의 분석력 손실
```

복잡한 종합 분석은 Opus로:
```yaml
model: opus  # 더 깊은 분석, 비용 증가
```

## 📚 참고 자료

- [Claude Code Subagents 문서](https://docs.claude.com/en/docs/claude-code/sub-agents)
- [MCP 서버 설정 가이드](https://docs.claude.com/en/docs/claude-code/mcp)
- [DART 전자공시 시스템](https://dart.fss.or.kr)

## 다음 단계

이 에이전트를 더 강화하고 싶다면:

1. **자체 투자 원칙 문서**를 `CLAUDE.md`에 추가
2. **관심 종목 워치리스트** 파일을 두고 정기 점검 루틴 만들기
3. **포트폴리오 트래커 서브에이전트** 추가 (보유 종목 종합 모니터링)
4. **백테스트 서브에이전트** 추가 (과거 시점 가정 시나리오)

---

**Disclaimer**: 본 에이전트는 교육·정보 제공 목적의 도구이며,
어떠한 투자 권유나 자문도 제공하지 않습니다.
모든 투자 결정과 그 결과는 사용자 본인의 책임입니다.
