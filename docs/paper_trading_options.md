# 모의 매수·매도 자동 실행 검증 방법

목표는 실제 주문 전에 전략의 주문 생성, 포지션 크기, 손절 제외, 목표가 청산 규칙을 반복 검증하는 것이다.

## 권장 순서

1. 로컬 페이퍼 트레이딩 시뮬레이터
   - 계좌/API 키 없이 즉시 실행 가능
   - 실제 주문 없음
   - `picks/paper_trading_state.json`와 `picks/paper_trading_ledger.csv`만 갱신

2. 한국투자증권 KIS Developers 모의투자
   - REST API 기반이라 Windows/Mac/Linux에서 운영 가능
   - 국내주식 주문/계좌, 현재가, 일별 주문체결, 잔고 조회 API 제공
   - 공식 개발자센터에서 모의투자 앱키와 계좌를 발급받아 연결

3. 키움증권 OpenAPI+ 모의투자
   - 국내 개인 자동매매에서 많이 쓰이지만 Windows/HTS/COM 환경 의존
   - 모의투자 신청 후 OpenAPI+와 KOA Studio로 함수 테스트 가능

## 로컬 실행

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\paper_trade_simulator.ps1
```

테스트용 실행:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\run_paper_trading_tests.ps1
```

## KIS 모의투자 연결 시 필요한 값

- `KIS_APP_KEY`
- `KIS_APP_SECRET`
- `KIS_ACCOUNT_TYPE=VIRTUAL`
- `KIS_CANO`
- `KIS_ACNT_PRDT_CD=01`

주문/정정/취소 기능은 반드시 별도 안전 게이트를 둔다. MCP 서버를 쓴다면 주문 도구는 기본 차단 상태로 두고, 모의투자에서만 명시적으로 활성화한다.

## 안전 규칙

- 실거래 계좌 연결 금지
- 기본 실행 모드는 항상 `paper`
- 실제 주문 API는 별도 승인 없이는 호출하지 않음
- 주문 장부와 상태 파일을 매 실행마다 남김
- 손절가 이탈 시 자동 제외하고 재진입은 수동 검토

## 참고 출처

- KIS Developers: https://apiportal.koreainvestment.com/
- KIS API 문서: https://apiportal.koreainvestment.com/apiservice
- KIS MCP 안전 기본값: https://mcpservers.org/ko/servers/migusdn/KIS_MCP_Server
- 한국투자증권 eFriend Expert Open API: https://truefriend.com/main/customer/systemdown/OpenAPI.jsp
