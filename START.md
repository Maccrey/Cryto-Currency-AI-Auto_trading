# START.md

## 1. 목적
이 문서는 Upbit Momentum Auto Trader를 로컬에서 설치, 설정, 실행, 점검하는 방법을 정리한다.

기본 운영 순서는 다음과 같다.

1. `demo` 모드로 실행한다.
2. 대시보드, 학습 로그, 손절, 재기동 흐름을 검증한다.
3. 승격 기준과 수동 승인 절차를 확인한다.
4. 충분히 검증된 뒤에만 `live` 모드로 전환한다.

---

## 2. 사전 요구사항
- Python 3.12 이상
- `uv` 또는 `pip`
- 업비트 API 키
- 텔레그램 봇 토큰과 채팅 ID

현재 프로젝트는 FastAPI와 Uvicorn 기반으로 실행된다.

---

## 3. 설치

### uv 사용
```bash
uv sync
```

### pip 사용
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 4. 환경 변수 설정

`.env.example`을 기준으로 `.env`를 만든다.

```bash
cp .env.example .env
```

최소 설정:

```bash
TRADING_MODE=demo
LEARNING_ENABLED=true

TRADE_MARKET=KRW-XRP
TRADE_COIN=XRP

UPBIT_ACCESS_KEY=발급받은_액세스키
UPBIT_SECRET_KEY=발급받은_시크릿키

TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
TELEGRAM_CHAT_ID=텔레그램_채팅_ID
```

전체 환경 변수 스펙은 `ENV_SPEC.md`를 따른다.

중요 규칙:
- `TRADING_MODE`는 `demo` 또는 `live`만 허용된다.
- `LEARNING_ENABLED=false`이면 앱이 시작되지 않는다.
- 실거래 전에는 반드시 `TRADING_MODE=demo`로 먼저 검증한다.
- `.env`는 저장소에 커밋하지 않는다.

---

## 5. demo 모드 실행

`demo` 모드는 실제 주문 API를 호출하지 않고 가상 체결을 사용한다.

```bash
TRADING_MODE=demo
LEARNING_ENABLED=true
```

### uv
```bash
uv run uvicorn app.main:app --reload
```

### pip
```bash
uvicorn app.main:app --reload
```

기본 접속 주소:

```text
http://127.0.0.1:8000
```

헬스 체크:

```bash
curl http://127.0.0.1:8000/health
```

---

## 6. 주요 API

### 헬스 체크
```bash
curl http://127.0.0.1:8000/health
```

응답에는 실행 모드, 학습 활성화 상태, SAFE_MODE, HARD_STOP, 거래 준비 상태가 포함된다.

### 대시보드 요약
```bash
curl http://127.0.0.1:8000/dashboard
```

보유 현금, 보유 코인, 손익, 매수/매도/손절 횟수, 학습 상태, 복구 상태, 승격 상태를 확인한다.

### 의사결정 실행
```bash
curl -X POST http://127.0.0.1:8000/decision \
  -H 'Content-Type: application/json' \
  -d '{
    "ticks": [
      {"price": 800.0, "volume": 10.0, "timestamp": "2026-04-28T10:00:00+09:00"},
      {"price": 824.0, "volume": 30.0, "timestamp": "2026-04-28T10:00:30+09:00"}
    ],
    "cash_balance": 500000.0,
    "asset_balance": 0.0,
    "avg_buy_price": 0.0,
    "spread_bps": 10.0,
    "slippage_bps": 12.0,
    "recent_loss_streak": 0,
    "safe_mode": false
  }'
```

### 현재 포지션
```bash
curl http://127.0.0.1:8000/position
```

### 승격 상태
```bash
curl http://127.0.0.1:8000/promotion/status
```

---

## 7. 로그와 상태 파일

학습 로그:

```text
logs/learning/
```

decision log:

```text
logs/learning/decision.jsonl
```

재기동 복구 상태:

```text
logs/recovery/restart-state.json
```

관련 환경 변수:

```bash
LEARNING_LOG_DIR=./logs/learning
RESTART_STATE_PATH=./logs/recovery/restart-state.json
```

---

## 8. live 모드 전환

`live` 모드는 실제 업비트 주문 경로를 사용한다. 전환 전 아래를 확인한다.

- `demo` 모드에서 실주문 0건
- 대시보드 요약 정상
- 손절가 주입 정상
- 가격 손절/기대 불일치 손절 정상
- 재기동 복구 상태 정상
- 텔레그램 알림 정상
- 승격 기준 검토 완료
- 운영자 수동 승인 완료

전환 설정:

```bash
TRADING_MODE=live
LEARNING_ENABLED=true
PROMOTION_REQUIRE_MANUAL_APPROVAL=true
```

실행:

```bash
uv run uvicorn app.main:app --reload
```

주의:
- `live`는 실제 주문 API를 사용할 수 있으므로 API 키 권한과 주문 금액을 반드시 점검한다.
- `SAFE_MODE`와 `HARD_STOP` 상태에서는 live 주문이 차단된다.
- 운영 전 `RUNBOOK.md`의 live 운영 절차를 확인한다.

---

## 9. 테스트

전체 테스트:

```bash
pytest
```

uv 사용:

```bash
uv run pytest
```

특정 테스트:

```bash
pytest tests/unit/test_live_executor.py
pytest tests/unit/test_recovery_orchestrator.py
pytest tests/unit/test_sizing_engine.py
```

커밋 전 권장 확인:

```bash
pytest
pre-commit run --all-files
```

---

## 10. 운영 체크리스트

demo 시작 전:
- [ ] `.env` 생성
- [ ] `TRADING_MODE=demo`
- [ ] `LEARNING_ENABLED=true`
- [ ] 업비트 키 입력
- [ ] 텔레그램 토큰/채팅 ID 입력
- [ ] `pytest` 통과

demo 운영 중:
- [ ] `/health` 정상
- [ ] `/dashboard` 정상
- [ ] 학습 로그 생성 확인
- [ ] 손절 라인/마커 확인
- [ ] 재기동 상태 파일 생성 확인
- [ ] 텔레그램 알림 확인

live 전환 전:
- [ ] 승격 기준 검토
- [ ] 수동 승인 완료
- [ ] SAFE_MODE/HARD_STOP 상태 확인
- [ ] 주문 금액과 API 키 권한 확인
- [ ] `RUNBOOK.md` 확인

---

## 11. 문제 해결

### 앱 시작 시 설정 오류
`TRADING_MODE`와 `LEARNING_ENABLED`를 확인한다.

```bash
TRADING_MODE=demo
LEARNING_ENABLED=true
```

### 로그가 생성되지 않음
`LEARNING_LOG_DIR` 경로에 쓰기 권한이 있는지 확인한다.

### 재기동 상태가 남지 않음
`RESTART_STATE_PATH`의 상위 디렉터리에 쓰기 권한이 있는지 확인한다.

### live 주문이 차단됨
`/health`에서 `safe_mode`, `hard_stop`, `trading_ready` 값을 확인한다.

차단 사유 예:
- `LIVE_MODE_REQUIRED`
- `SAFE_MODE_ACTIVE`
- `HARD_STOP_ACTIVE`
- `LIVE_PRECHECK_FAILED`

---

## 12. 참고 문서
- `README.md`
- `ENV_SPEC.md`
- `RUNBOOK.md`
- `Tasklist.md`
- `PRD.md`
- `STRATEGY_SPEC.md`
