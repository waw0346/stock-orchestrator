# 미국장 마감 후 한국장 장전 루틴

`scripts/collect_us_close_data.py`는 미국 지수, 섹터 ETF, 주도주, 매크로 신호를 수집해 한국장 장전 후보를 JSON으로 생성합니다.

## 흐름

```text
미국장 마감 데이터
→ picks/cache/us_close_snapshot.json
→ 미국 신호/한국 섹터 매핑
→ picks/cache/preopen_candidates.json
→ scripts/run_preopen_filter.ps1
→ picks/cache/preopen_filtered_candidates.json
→ preopen-foreign-scanner 검토
→ WATCHLIST.md 업데이트안
→ Capital Protection Gate 통과 시에만 신규 픽 발행
```

## 수집 대상

- 지수: S&P 500, Nasdaq, Russell 2000, VIX
- 섹터 ETF: SMH, SOXX, XLK, XLE, XLF, XLI, XBI
- 주도주: NVDA, AMD, MU, AVGO, TSLA, AAPL, MSFT, AMZN, GOOGL, LLY
- 매크로: 미국 10년물, 달러인덱스, WTI, 구리, 금

## 실행

실제 수집:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_us_close_data.ps1
```

네트워크 없는 검증용 샘플:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_us_close_data.ps1 -OfflineSample
```

테스트 산출물 경로 지정:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_us_close_data.ps1 -OfflineSample -SnapshotPath picks\cache\us_close_snapshot.test.json -CandidatesPath picks\cache\preopen_candidates.test.json
```

한국장 가격/갭 필터 적용:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_preopen_filter.ps1
```

네트워크 없는 검증용 필터:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_preopen_filter.ps1 -OfflineSample -CandidatesPath picks\cache\preopen_candidates.test.json -OutputPath picks\cache\preopen_filtered_candidates.test.json
```

## 산출물

`picks/cache/us_close_snapshot.json`

- `mode`: `live` 또는 `offline_sample`
- `quotes[]`: 미국 종목/ETF/지수별 가격, 전일 대비 등락률, 원천 상태

`picks/cache/preopen_candidates.json`

- `market_regime_hint`: `Risk-On`, `Neutral`, `Risk-Off`
- `preopen_candidates[]`: 최대 3개 한국 장전 관찰 후보
- `pass_candidates[]`: 점수 미달 후보
- `hard_blocks[]`: 추격 금지/게이트 조건

`picks/cache/preopen_filtered_candidates.json`

- `final_candidates[]`: 갭/손익비 필터를 통과한 후보. 외국인 수급이 없으면 `NEEDS_FOREIGN_CONFIRMATION` 상태로 남습니다.
- `blocked[]`: 갭 +5% 이상, 손익비 부족 등으로 차단된 후보
- `passed[]`: 가격 데이터 없음 등으로 보류된 후보

이 스크립트는 자동 추천픽 발행기가 아닙니다. 후보 JSON은 장전 검토 입력이며, 신규 픽 저장은 반드시 Capital Protection Gate 통과 후에만 허용됩니다.
현재 공개 자동 데이터만으로는 장전 외국인 수급을 확정하지 않습니다. 외국인 수급이 확인되기 전 후보는 `FOCUS`가 아니라 `NEEDS_FOREIGN_CONFIRMATION`으로 유지됩니다.
