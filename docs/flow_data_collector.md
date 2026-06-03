# 수급 데이터 수집기

`scripts/collect_flow_data.py`는 시장 스냅샷의 종목 universe를 기준으로 최근 5거래일 외국인/기관 순매수 스냅샷 구조를 관리합니다.

KRX/pykrx live 수급 조회는 이 환경에서 `empty_response`를 반환해 운영 루프에서 제거했습니다. 기본 실행은 네트워크 조회를 하지 않고 `disabled` 스냅샷을 남깁니다. 오프라인 샘플은 테스트와 향후 provider 연결 검증용으로 유지합니다.

## 실행

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_flow_data.ps1 -UpdateMarketSnapshot
```

네트워크 없는 검증용 샘플:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_flow_data.ps1 -OfflineSample -UpdateMarketSnapshot
```

## 산출물

`picks/cache/flow_snapshot.json`

- `items[].foreign_net_buy_5d`: 외국인 5거래일 누적 순매수
- `items[].institution_net_buy_5d`: 기관 5거래일 누적 순매수
- `items[].combined_net_buy_5d`: 외국인+기관 합산

`-UpdateMarketSnapshot`을 주면 성공한 flow 항목만 `picks/cache/market_data_snapshot.json`의 각 종목에 `flow` 필드로 병합합니다. 기본 `disabled` 모드에서는 병합할 성공 항목이 없으므로 후보판에 `flow=MISSING`을 표시하지 않습니다.
