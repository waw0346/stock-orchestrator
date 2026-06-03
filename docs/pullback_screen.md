# Pullback 스크리너

`scripts/run_pullback_screen.py`는 `picks/INDEX.md`의 active/watch 종목과 `picks/cache/market_data_snapshot.json`의 현재가를 비교해 눌림 진입 후보를 보수적으로 점검합니다.

## 흐름

```text
picks/INDEX.md
→ active/watch 종목과 entry zone 파싱
→ picks/cache/market_data_snapshot.json 현재가/등락률/technical/flow 매칭
→ 4신호(4-signal) 모델 중 자동 확인 가능한 항목만 채점
→ picks/cache/pullback_candidates.json 생성
→ pullback-analyst / entry-exit-timing-strategist 검토
```

## 실행

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_pullback_screen.ps1
```

네트워크 없는 검증용 샘플:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_pullback_screen.ps1 -OfflineSample -OutputPath picks\cache\pullback_candidates.test.json
```

## 산출물

`picks/cache/pullback_candidates.json`

- `candidates[]`: 종목별 pullback 점검 결과
- `signal_scores`: 4신호(4-signal) 점수
- `decision`: `STRONG_ENTRY`, `PROBE_ENTRY`, `WAIT`, `PASS`, `BLOCK`
- `data_gaps`: 자동 데이터 부족 항목

`market_data_snapshot.json`의 종목 항목에 아래 필드가 있으면 자동 채점합니다.

- `technical.ma20`, `technical.ma60`, `technical.ma120`, `technical.rsi14`
- `volume`, `technical.volume_avg20`
- `flow.foreign_net_buy_5d`, `flow.institution_net_buy_5d`

부족한 신호는 0점 처리됩니다. `STRONG_ENTRY`와 `PROBE_ENTRY`는 스크리닝 상태일 뿐 직접 매매 지시가 아니며, 실제 실행 전에는 `pullback-analyst`가 최신 기술지표와 수급을 재확인해야 합니다.
