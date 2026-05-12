# 🏦 한국 주식 리서치 오케스트레이터

증권사 리서치팀 구조를 Claude Code subagent 패턴으로 구현한 한국 주식 분석 시스템.
6명의 전문 애널리스트가 분담 분석하고, 시니어가 종합해 추천픽을 발간하며,
주/월 단위로 자동 추적합니다.

## 🎯 7단계 분석 프레임워크

```
1. 기업분석     (company-analyst)    — 사업 모델, 지배구조
2. 재무분석     (financial-analyst)  — 재무제표, 비율, 현금흐름
3. 산업분석     (industry-analyst)   — 사이클, 경쟁구도, 매크로
4. 모멘텀분석   (momentum-analyst)   — 추세, 거래량, 변동성
5. 리스크분석   (risk-analyst)       — 공시 레드플래그, 다운사이드
6. 외인/기관동향 (flow-analyst)      — 수급, 외국인, 공매도
7. 종합의견     (오케스트레이터)     — 추천픽 발간
        ↓
   [추천픽 picks/ 저장]
        ↓
   주간 추적 (weekly-tracker)
   월간 추적 (monthly-tracker)
```

## 📦 디렉토리 구조

```
stock-orchestrator/
├── README.md                    ← 이 파일
├── CLAUDE.md                    ← 메인 오케스트레이터 (시니어 페르소나)
├── .claude/
│   └── agents/                  ← 8개 서브에이전트 정의
│       ├── company-analyst.md
│       ├── financial-analyst.md
│       ├── industry-analyst.md
│       ├── momentum-analyst.md
│       ├── risk-analyst.md
│       ├── flow-analyst.md
│       ├── weekly-tracker.md
│       └── monthly-tracker.md
└── picks/                       ← 발간된 추천픽 저장소
    ├── INDEX.md                 ← 마스터 인덱스
    └── YYYY-MM-DD_[ticker].md   ← 개별 픽 파일들
```

## 🛠️ 설치

### 1. Claude Code 설치

```bash
# Node.js 18 이상 필요
npm install -g @anthropic-ai/claude-code

# 설치 확인
claude --version
```

### 2. 프로젝트 디렉토리 준비

압축 해제 후 디렉토리로 이동:

```bash
cd path/to/stock-orchestrator
```

### 3. PlayMCP (DART) 연결

한국 DART 전자공시 데이터에 접근하기 위한 원격 MCP 서버 등록:

```bash
claude mcp add --scope project playmcp \
  --transport http \
  https://playmcp.kakao.com/mcp
```

설치 후 카카오 계정 인증 진행 (브라우저로 안내됨).

### 4. 첫 실행

```bash
claude
```

세션 시작 후:

```
/agents
```

다음 8개 서브에이전트가 보이면 설치 성공:
- company-analyst
- financial-analyst
- industry-analyst
- momentum-analyst
- risk-analyst
- flow-analyst
- weekly-tracker
- monthly-tracker

---

## 🚀 사용법

### A. 신규 종목 분석 & 추천픽 발간

```
삼성전자 분석해줘
```

오케스트레이터가 자동으로:
1. **Phase 1 병렬**: company + industry + flow analysts
2. **Phase 2 병렬**: financial + momentum analysts
3. **Phase 3**: risk-analyst (앞 결과 종합)
4. **Phase 4**: 오케스트레이터가 종합의견 작성
5. **Phase 5**: `picks/2026-XX-XX_005930.md`에 저장 + INDEX 업데이트

### B. 부분 분석 (픽 저장 안 함)

```
@financial-analyst NAVER 재무 점검해줘
@risk-analyst 카카오 최근 공시 레드플래그 봐줘
@industry-analyst 2026년 한국 반도체 산업 어때?
```

### C. 비교 분석

```
LG에너지솔루션과 삼성SDI 비교 분석해줘
```

종목별로 7단계 분석 후 비교 리포트 생성.

### D. 주간 추적

```
이번주 픽 점검해줘
```
또는
```
주간 추적 돌려줘
```

`weekly-tracker`가 active 픽들을 일괄 점검하고 보고서 생성.

### E. 월간 추적

```
이번달 픽 결산해줘
```
또는
```
월간 추적 돌려줘
```

`monthly-tracker`가 thesis 검증과 펀더멘털 변화 점검까지 깊이 있게 추적.

### F. 단일 픽 재점검

```
삼성전자 픽 어떻게 됐어?
```

특정 종목만 골라서 재점검.

### G. 픽 목록 확인

```
현재 픽 목록 보여줘
```

INDEX.md를 읽어서 표로 출력.

---

## 📝 추천픽 저장 형식

각 픽은 다음과 같은 YAML frontmatter + 마크다운 형식으로 저장됩니다:

```yaml
---
date: 2026-05-04
ticker: "005930"
name: 삼성전자
market: KOSPI
sector: 반도체
rating: 4              # 1~5 (별점)
horizon: 중기          # 단기 / 중기 / 장기
entry_price_low: 70000
entry_price_high: 73000
target_1: 85000
target_2: 95000
stop_loss: 62000
current_price_at_pick: 71500
status: active
last_review: 2026-05-04
review_history: []
---

# (이하 7단계 분석 본문)
```

이 메타데이터를 통해 추적기들이 자동으로 픽을 식별하고 성과를 계산합니다.

---

## 💡 사용 팁

### 1. 분석 깊이 조절
- **빠른 점검**: `@financial-analyst ○○만 봐줘`
- **풀 리서치**: `○○ 분석해서 추천픽 내줘`

### 2. 정기 추적 루틴
- **매주 월요일 아침**: "지난 주 픽 점검해줘"
- **매월 첫 영업일**: "지난 달 결산해줘"

### 3. 메모리 활용
8개 서브에이전트 모두 `memory: project` 설정.
같은 산업·종목 분석을 반복하면 누적된 인사이트가 분석 품질을 향상시킵니다.

### 4. 백그라운드 실행
긴 풀 리서치는 백그라운드로:

```
백그라운드로 셀트리온 분석 돌려줘
```

`Ctrl+B`로도 백그라운드 전환 가능.

### 5. 분석 결과 검토 후 픽 거부
오케스트레이터가 종합의견을 제시했지만 마음에 안 들 때:

```
이 픽은 저장하지 마, 등급 낮춰서 다시 작성해줘
```

또는 직접 픽 파일 수정 가능.

### 6. 자기 투자 스타일 반영

`CLAUDE.md`에 본인 투자 철학을 추가하세요:

```markdown
## 추가 가이드라인

- 가치투자 스타일 선호 (PER 15배 이하 우선)
- 배당수익률 3% 이상 종목 가산점
- 부채비율 100% 초과 시 자동 등급 하향
- 보유 종목 워치리스트:
  - 005930 삼성전자
  - 035420 NAVER
  - 035720 카카오
```

---

## 🎚️ 커스터마이징

### 모델 선택
각 서브에이전트는 기본적으로 Sonnet을 사용합니다. 비용 절감하려면 Haiku로:

```yaml
# 예: momentum-analyst.md 상단
model: haiku  # 단순 데이터 처리는 Haiku로 충분
```

복잡한 종합 분석은 Opus로:

```yaml
# 예: risk-analyst.md 상단
model: opus  # 깊은 분석이 필요한 영역
```

### 새 서브에이전트 추가
예: ESG 전문가, 매크로 전략가, 외국 시장 비교 분석 등

```bash
/agents
```

인터랙티브 메뉴에서 "Create new agent" 선택.

### 특정 서브에이전트 제외
일부 분석을 건너뛰고 싶다면 `CLAUDE.md`의 워크플로우 섹션 수정:

```
# 모멘텀 분석 생략 (장기 가치투자만)
# Phase 2에서 momentum-analyst 호출 제거
```

---

## ⚠️ 한계와 면책

### 데이터 한계
- DART는 **분기 공시 기준** — 미공시 분기 정보 알 수 없음
- 실시간 시세는 웹 검색 의존, 약간의 시차 가능
- 비공개 정보(검찰 조사, 미공개 협상 등) 알 수 없음

### 분석 한계
- 본 시스템의 분석은 **공개 데이터 기반 리서치**
- **투자 권유나 자문이 아님**
- 최종 투자 판단은 본인 책임
- 모든 정보를 교차 검증하세요

### 추적 한계
- 추적은 picks/ 디렉토리의 픽들에 한정
- 사용자의 실제 매매 비용·세금·심리 부담을 알지 못함
- 가격 정보는 추적 시점 기준이며, 시장 휴장일은 직전 거래일 데이터 사용

---

## 📚 참고 자료

- [Claude Code Subagents](https://docs.claude.com/en/docs/claude-code/sub-agents)
- [MCP 서버 설정](https://docs.claude.com/en/docs/claude-code/mcp)
- [DART 전자공시](https://dart.fss.or.kr)
- [한국거래소](https://www.krx.co.kr)

---

## 🔄 향후 확장 아이디어

이 시스템에 추가할 수 있는 기능:

1. **포트폴리오 트래커**: 실제 보유 종목 리스트와 결합
2. **백테스트 서브에이전트**: 과거 시점 가정 시뮬레이션
3. **알림 자동화**: hooks를 사용해 손절선 도달 시 자동 알림
4. **외국 시장 비교**: 미국·중국·일본 동종업계 비교 서브에이전트
5. **매크로 헤드**: FOMC, 한은 금통위, 환율 분석 전담 서브에이전트
6. **결산 대시보드**: monthly-tracker 결과를 HTML 대시보드로 출력

---

**Disclaimer**: 본 시스템은 교육·정보 제공 목적이며,
어떠한 투자 권유나 자문도 제공하지 않습니다.
모든 투자 결정과 그 결과는 사용자 본인의 책임입니다.
