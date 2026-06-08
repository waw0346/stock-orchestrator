# 📊 수급 & 거래량 통합 모멘텀 스캐너 (Flow-Volume Integration Scanner)

이 모듈은 외국인, 기관, 연기금 등의 **메이저 투자 주체의 수급 정보**와 개별 종목의 **20일 평균 대비 거래량 비율**을 결합 분석하여, 단기적으로 주목해야 할 핵심 관심 종목군을 필터링 및 분류합니다.

---

## 🎯 1. 두 가지 핵심 매칭 패턴

수급과 거래량의 상호작용 분석을 통해 종목들을 아래의 두 가지 핵심 패턴으로 자동 분류합니다:

### 🚀 돌파 상승형 (Breakout Candidates)
* **목표**: 기관/외인 수급의 대규모 매집세와 함께 강한 가격 돌파가 일어난 종목을 포착합니다.
* **조건**:
  1. **수급 요건**: 메이저 주체의 연속 수급 유입 발생 (Streak) 또는 최근 5일 누적 수급 유입 양수 (`> 0`).
  2. **가격 요건**: 당일 가격 등락률이 `+0.5%` 이상 상승.
  3. **거래량 요건**: 당일 거래량이 20일 평균 거래량(`volume_avg20`) 대비 **1.5배(150%) 이상** 급증.

### 💤 눌림 수축형 (Pullback Contraction Candidates)
* **목표**: 메이저 매수 유입은 확인되었으나, 단기 조정 또는 가격 횡보 국면에서 개인 및 단기 매도 매물이 메말라 거래량이 극도로 감소한 **안정적인 눌림목 진입 찬스** 종목을 포착합니다.
* **조건**:
  1. **수급 요건**: 메이저 주체의 연속 수급 유입 발생 (Streak) 또는 최근 5일 누적 수급 유입 양수 (`> 0`).
  2. **가격 요건**: 당일 가격 등락률이 `-4.0%`에서 `+0.5%` 사이로 보합/약조정 국면.
  3. **거래량 요건**: 당일 거래량이 20일 평균 거래량(`volume_avg20`) 대비 **0.6배(60%) 이하**로 극도로 수축.

---

## 💾 2. 입출력 데이터 규격

### 입력 파일 (Inputs)
* `picks/cache/market_data_snapshot.json` — 실시간 종가, 등락률, 당일 거래량 및 20일 평균 거래량(`technical.volume_avg20`) 수치.
* `picks/cache/flow_streak_candidates.json` — 외국인/연기금 연속 수급 일수 매치 후보.
* `picks/cache/foreign_streak_candidates.json` — 외국인 연속 순매수 후보.

### 출력 파일 (Outputs)
* **JSON 캐시**: `picks/cache/flow_volume_candidates.json` — 판정된 결과 캐시.
* **Obsidian 일지**: `obsidian/stock_log/04_candidate_boards/Flow Volume Candidates.md` — Obsidian Vault 내 마크다운 일지 자동 동기화.

---

## 🛠️ 3. 실행 방법 (Usage)

### 오프라인 시뮬레이션 테스트
로컬 목 데이터를 사용하여 스캐너 규칙 및 출력을 점검합니다.
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_volume_filter.ps1 -OfflineSample
```

### 라이브 연동 실행 (정규 정산)
실시간 캐시 데이터를 로드하여 금일 거래량 비율 분석 관심 종목판을 발간합니다.
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_volume_filter.ps1
```
* 임계값 커스터마이징 (돌파 기준 2.0배, 수축 기준 0.5배로 강화):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_volume_filter.ps1 -BreakoutRatio 2.0 -ContractionRatio 0.5
```
