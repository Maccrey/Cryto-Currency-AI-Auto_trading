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
- macOS에서는 `./start.sh`가 Python 3.12 이상이 없을 때 Homebrew와 Python 설치를 자동으로 시도한다.
- Linux에서는 `apt-get`, `dnf`, `yum` 중 사용 가능한 패키지 관리자로 Python 설치를 자동으로 시도한다.
- 업비트 API 키는 `live` 모드에서만 필수다.
- 텔레그램 봇 토큰과 채팅 ID는 알림을 사용할 때 필요하다.

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

## 4. 가장 쉬운 시작

아래 한 줄만 실행한다.

```bash
./start.sh
```

동작:
- `.env`가 없으면 `.env.example`을 복사해 만든다.
- `SERVER_NAME`이 없거나 예시값이면 현재 컴퓨터 이름을 기본 서버 이름으로 저장한다.
- Python 3.12 이상이 없으면 설치를 시도한다.
- `.venv` 가상환경을 만들고 필요한 Python 패키지를 설치한다.
- 서버가 꺼져 있으면 macOS `launchd` KeepAlive로 등록해 `0.0.0.0:8080`으로 시작한다.
- 서버가 이미 실행 중이면 중복 실행하지 않는다.
- 크롬에서 `http://127.0.0.1:8080/settings` 설정창을 연다.
- 같은 네트워크의 다른 기기에서는 `http://<내 컴퓨터 LAN IP>:8080/settings`와 `http://<내 컴퓨터 LAN IP>:8080/dashboard`로 접속한다.
- 텔레그램 봇 토큰과 채팅 ID가 등록되어 있으면 앱 서버 시작 시 설정창/대시보드 접속 주소와 자동 트레이딩이 아직 시작되지 않았다는 안내를 텔레그램으로 보낸다.
- 트레이딩 시스템은 터미널을 닫아도 백그라운드에서 계속 돌고, 프로세스가 종료되면 macOS가 다시 시작한다.
- 로그는 `logs/runtime/server.log`에 쌓인다.

실행 상태 확인:

```bash
curl http://127.0.0.1:8080/health
```

백그라운드 서비스를 수동으로 내릴 때만 아래 명령을 사용한다.

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.crypto-auto-trading.plist
```

---

## 5. 환경 변수 설정 방식

설정은 두 가지 방식으로 할 수 있다.

1. 앱 실행 후 브라우저의 `/settings` 화면에서 입력한다.
2. `.env.example`을 복사해 `.env` 파일을 직접 편집한다.

처음 실행은 API 키 없이 `demo` 모드로 시작할 수 있으므로, 가장 쉬운 방식은 앱을 먼저 실행한 뒤 설정 화면에서 값을 저장하는 것이다.

### GUI 설정 권장 흐름

1. 앱을 실행한다.
2. 브라우저에서 `http://127.0.0.1:8080/settings`를 연다.
3. DEMO/LIVE 스위치로 모드를 고른다.
4. 마켓, 코인, 데모 시작 투자금, 업비트 키, 텔레그램 값을 입력한다.
5. 저장한다.
6. 필수값이 충족되면 표시되는 `서버 시작` 버튼을 눌러 트레이딩 서버를 시작한다.

GUI 동작 규칙:
- `demo` 모드는 업비트 API 키 없이 저장하고 실행할 수 있지만, 필수값이 저장되어 있어야 `서버 시작` 버튼이 보인다.
- `demo` 모드 기본 시작 투자금은 `1,000,000 KRW`이며 설정 화면의 `데모 시작 투자금`에서 변경할 수 있다.
- `live` 모드는 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY`가 저장되어 있을 때만 `서버 시작` 버튼이 보인다.
- 필수 입력 항목은 설정 화면에서 `*`로 표시된다.
- 기존 `.env`에 API 키가 있으면 설정 화면의 키 입력칸을 비워 저장해도 기존 키를 보존한다.
- 설정 화면에서 현재 투자성향의 학습 데이터를 리셋할 수 있다. 기존 로그는 `logs/learning/reset_archive/<TRADING_PROFILE>/`로 이동하고 새 로그를 다시 쌓는다.
- `/settings/current` 응답에서는 API 키와 토큰이 `***`로 마스킹된다.

### 파일 직접 설정

```bash
cp .env.example .env
```

demo 최소 설정:

```bash
TRADING_MODE=demo
LEARNING_ENABLED=true

TRADE_MARKET=KRW-XRP
TRADE_COIN=XRP
DEMO_INITIAL_CAPITAL=1000000
```

live 전환 시 추가 필수 설정:

```bash
TRADING_MODE=live

UPBIT_ACCESS_KEY=발급받은_액세스키
UPBIT_SECRET_KEY=발급받은_시크릿키
```

알림 사용 시 설정:

```bash
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
TELEGRAM_CHAT_ID=텔레그램_채팅_ID
SERVER_NAME=서울-데모-1
```

텔레그램 메시지는 항상 첫 줄에 `[SERVER_NAME]` 형식으로 서버 이름을 붙인다. 설정 화면에서 서버 이름을 저장하면 이후 알림부터 최신 `.env`의 `SERVER_NAME`을 다시 읽어 사용하므로, 같은 텔레그램 방에 여러 서버를 연결해도 어떤 서버의 알림인지 구분할 수 있다.

전체 환경 변수 스펙은 `ENV_SPEC.md`를 따른다.

중요 규칙:
- `TRADING_MODE`는 `demo` 또는 `live`만 허용된다.
- `LEARNING_ENABLED=false`이면 앱이 시작되지 않는다.
- `demo` 모드는 업비트 API 키 없이도 학습/검증용으로 작동한다.
- `live` 모드 저장 또는 실행 전에는 업비트 API 키를 준비한다.
- `.env`는 저장소에 커밋하지 않는다.
- 다른 경로의 설정 파일을 쓰려면 `ENV_FILE_PATH`를 지정한다.

```bash
ENV_FILE_PATH=/path/to/.env uv run uvicorn app.main:app --reload
```

---

## 6. demo 모드 실행

`demo` 모드는 실제 주문 API를 호출하지 않고 가상 체결을 사용한다. 기본 가상 투자금은 `1,000,000 KRW`다.

```bash
TRADING_MODE=demo
LEARNING_ENABLED=true
```

### 권장
```bash
./start.sh
```

### uv 직접 실행
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### pip 직접 실행
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 명시적 demo 실행
```bash
env TRADING_MODE=demo LEARNING_ENABLED=true uvicorn app.main:app --host 0.0.0.0 --port 8080
```

기본 접속 주소:

```text
http://127.0.0.1:8080
```

헬스 체크:

```bash
curl http://127.0.0.1:8080/health
```

설정 화면:

```text
http://127.0.0.1:8080/settings
```

이 화면에서 demo/live 모드를 스위치로 변경하고 `.env`에 필요한 값을 저장할 수 있다.
demo 모드는 업비트 API 키 없이 저장/실행할 수 있으며, live 모드는 업비트 API 키가 없으면 저장이 거절된다.
저장 후 조건이 충족되면 설정 화면에 `서버 시작` 버튼이 나타나며, 이 버튼을 눌렀을 때 자동 트레이딩 루프가 시작된다.

대시보드:

```text
http://127.0.0.1:8080/dashboard
```

대시보드에서는 현재가, 데모 투자금, 손익, 학습 상태, AI 운용 상태, 최근 체결, 실거래 전환 준비 상태를 확인한다. demo 모드의 투자금과 보유 코인 수량은 체결 결과가 반영된 가상 포트폴리오 기준으로 표시된다.
현재가는 업비트 공개 ticker API를 사용해 1초 주기로 갱신된다.

---

## 6. 주요 API

### 헬스 체크
```bash
curl http://127.0.0.1:8080/health
```

응답에는 실행 모드, 학습 활성화 상태, SAFE_MODE, HARD_STOP, 거래 준비 상태가 포함된다.

### 설정 화면
브라우저에서 연다.

```text
http://127.0.0.1:8080/settings
```

현재 설정 API:

```bash
curl http://127.0.0.1:8080/settings/current
```

설정 저장 API:

```bash
curl -X POST http://127.0.0.1:8080/settings \
  -H 'Content-Type: application/json' \
  -d '{
    "TRADING_MODE": "demo",
    "LEARNING_ENABLED": "true",
    "TRADE_MARKET": "KRW-XRP",
    "TRADE_COIN": "XRP",
    "DEMO_INITIAL_CAPITAL": "1000000"
  }'
```

live 저장 예:

```bash
curl -X POST http://127.0.0.1:8080/settings \
  -H 'Content-Type: application/json' \
  -d '{
    "TRADING_MODE": "live",
    "LEARNING_ENABLED": "true",
    "TRADE_MARKET": "KRW-XRP",
    "TRADE_COIN": "XRP",
    "UPBIT_ACCESS_KEY": "access-key",
    "UPBIT_SECRET_KEY": "secret-key"
  }'
```

live 저장 시 키가 없으면 다음처럼 저장되지 않는다.

```json
{
  "status": "missing_required",
  "saved": false,
  "missing_for_live": ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"],
  "message": "live mode requires Upbit API keys"
}
```

### 대시보드 화면
브라우저에서 연다.

```text
http://127.0.0.1:8080/dashboard
```

표시 항목:
- 실행 모드
- 현재 가격
- 데모 투자금 또는 실계좌 사용 가능 현금
- 학습 완료율
- 수익 성공률
- 실현/미실현 손익
- AI 운용 모드
- 현재 상황
- 학습 상태
- 최근 체결
- 실거래 전환 준비

AI 운용 모드에는 다음 값이 표시된다.

```text
AI 상태: 관찰 중
자동매매: 대기
리스크 등급: 보통
마지막 분석: 현재가 수집 시각
```

상태 설명 표는 기본적으로 접혀 있으며 `상태 설명 펼치기` 버튼으로 열고 닫을 수 있다.

### 안정 운용 규칙
진입 전에는 아래 조건을 추가로 검사한다.

- 저유동성 구간이면 신호를 차단한다.
- 1초 수익률이 급격히 음수로 돌아서면 초단기 역방향 모멘텀으로 보고 신호를 차단한다.
- 단기 변동성이 과도하게 커지면 신호를 차단한다.
- 매수 금액은 손절가까지 하락했을 때의 예상 손실이 `MAX_DAILY_LOSS`의 25%를 넘지 않도록 자동 축소된다.

예를 들어 `MAX_DAILY_LOSS=150000`이면 1회 진입의 예상 손절 손실 예산은 37,500원이다. 신호가 강해도 이 예산을 넘는 주문 크기는 자동으로 줄어든다.

### 대시보드 API
```bash
curl http://127.0.0.1:8080/dashboard
```

HTML 대시보드가 반환된다. JSON 요약은 아래 API를 사용한다.

```bash
curl http://127.0.0.1:8080/dashboard/summary
curl http://127.0.0.1:8080/dashboard/market
curl http://127.0.0.1:8080/dashboard/learning
curl http://127.0.0.1:8080/dashboard/executions
curl http://127.0.0.1:8080/dashboard/promotion
```

보유 현금, 보유 코인, 손익, 매수/매도/손절 횟수, 학습 상태, 복구 상태, 승격 상태를 확인한다.

### 의사결정 실행
```bash
curl -X POST http://127.0.0.1:8080/decision \
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
curl http://127.0.0.1:8080/position
```

### 승격 상태
```bash
curl http://127.0.0.1:8080/promotion/status
```

---

## 7. 로그와 상태 파일

학습 로그:

```text
storage/logs/learning/
```

decision log:

```text
storage/logs/learning/decision.jsonl
```

재기동 복구 상태:

```text
storage/runtime/recovery/restart-state.json
```

관련 환경 변수:

```bash
STORAGE_DIR=./storage
LEARNING_LOG_DIR=./storage/logs/learning
LEARNING_DATASET_DIR=./storage/data/learning
RESTART_STATE_PATH=./storage/runtime/recovery/restart-state.json
```

기존 데이터를 유지하며 업데이트할 때는 앱을 중지한 뒤 `mkdir -p storage && mv logs storage/logs && mv data storage/data`로 기존 로그와 데이터셋을 옮긴다. 기존 경로를 그대로 쓰려면 `.env`의 `LEARNING_LOG_DIR`와 `LEARNING_DATASET_DIR`를 변경하지 않는다.

자동 복구 동작:
- live 부팅 중 잔고 동기화가 실패하면 기본 3회까지 자동 재시도한다.
- 오픈오더 정리가 실패해도 기본 3회까지 자동 재시도한다.
- 재시도 중 실패와 최종 복구 성공은 `recovery_attempt` 학습 이벤트로 기록된다.
- 끝까지 복구하지 못하면 `SAFE_MODE`가 유지되고 live 주문은 차단된다.

---

## 8. 텔레그램 정기 리포트

`TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`가 모두 설정되어 있으면 앱 시작 시 텔레그램 정기 리포트가 자동 활성화된다.

발송 규칙:
- 06:00부터 24:00 전까지 매시 정각 현재 트레이딩 리포트를 발송한다.
- 매일 06:00에는 전날 트레이딩 결과 리포트도 함께 발송한다.
- 같은 시간대의 리포트는 중복 발송하지 않는다.
- 발송 실패가 발생해도 앱은 중단되지 않으며 다음 스케줄을 계속 대기한다.

현재 트레이딩 리포트에는 현재가, 현금/코인 잔고, 실현손익, 매수/매도/손절 횟수, 활성 포지션, SAFE_MODE/HARD_STOP/trading_ready, 최근 학습 이벤트가 포함된다.

전날 트레이딩 결과 리포트에는 매매판단신호 수, 차단 신호 수, 체결 수, 포지션 진입/청산 수, 승격 검토 수, 재기동/복구 이벤트 수, 학습 반영 이벤트 범주가 포함된다.

설정 예:

```bash
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
TELEGRAM_CHAT_ID=텔레그램_채팅_ID
```

---

## 9. 자동 운용과 무거래 진단

demo 모드도 앱 부팅만으로 자동 운용 루프를 시작하지 않는다. 설정 화면에서 필수값을 저장한 뒤 `서버 시작` 버튼을 눌렀을 때 자동 운용 루프가 시작된다.

동작 흐름:
- `AUTO_TRADING_INTERVAL_SEC` 주기마다 업비트 현재가를 수집한다.
- `AUTO_TRADING_MIN_HISTORY`만큼 현재가 히스토리가 쌓이면 신호/국면/사이징 판단을 실행한다.
- 포지션이 없으면 진입 판단 후 demo 체결을 실행한다.
- 포지션이 있으면 손절/기대 불일치 청산 조건을 점검한다.
- 모든 사이클은 `auto_trade_cycle` 학습 이벤트로 `logs/learning/<TRADING_PROFILE>/learning.jsonl`에 기록된다.
- 설정 화면에서 투자성향을 단타, 단기, 중기, 장기 중 선택한다.
- 기본 전략 성향은 `TRADING_PROFILE=scalping`이며, 3초 주기로 단타 신호를 관찰한다.
- 업비트 KRW 마켓 수수료 0.05%를 `TRADING_FEE_RATE=0.0005`로 계산한다.
- 예상 엣지가 왕복 수수료 0.10%와 투자성향별 최소 순엣지를 넘지 못하면 `FEE_ADJUSTED_EDGE_LIMIT`으로 차단된다.
- 업비트 KRW 마켓 최소 주문 가능 금액은 5,000원이며, 이보다 작은 매수/매도 주문은 차단된다.
- 부분 손절 후 남는 잔량 평가액이 5,000원 미만이면 반복 dust 매도를 막기 위해 전량 청산으로 보정한다.
- 수수료를 감안해 보합권에서는 소프트 손절을 보류하고, 실제 불리한 움직임이 확인될 때만 기대 불일치 손절을 실행한다.

무거래 원인 진단:

```bash
curl http://127.0.0.1:8080/learning/diagnostics
```

TensorFlow 등 모델 학습을 시작할 준비가 되었는지 확인:

```bash
curl http://127.0.0.1:8080/learning/model-readiness
```

주요 진단 상태:
- `AUTO_TRADING_NOT_RUNNING`: 자동 운용 루프 로그가 없음
- `WAITING_FOR_SIGNAL`: 루프는 실행 중이나 조건 미충족
- `TRADE_BLOCKED_BY_RULES`: 신호/리스크/사이징 규칙으로 차단
- `TRADES_FOUND`: 최근 로그에서 체결 확인

자동 운용 설정:

```bash
AUTO_TRADING_ENABLED=true
AUTO_TRADING_LIVE_ENABLED=false
AUTO_TRADING_INTERVAL_SEC=3.0
AUTO_TRADING_MIN_HISTORY=6
TRADING_PROFILE=scalping
TRADING_FEE_RATE=0.0005
PROFILE_MIN_NET_EDGE_PCT=0.0008
```

투자성향 기본값:

| 표시 | 값 | 주기 | 히스토리 | 최소 순엣지 | 학습 로그 |
|---|---|---:|---:|---:|---|
| 단타 | `scalping` | 3초 | 6 | 0.08% | `logs/learning/scalping/learning.jsonl` |
| 단기 | `short_term` | 10초 | 12 | 0.20% | `logs/learning/short_term/learning.jsonl` |
| 중기 | `mid_term` | 30초 | 20 | 0.60% | `logs/learning/mid_term/learning.jsonl` |
| 장기 | `long_term` | 60초 | 30 | 1.20% | `logs/learning/long_term/learning.jsonl` |

live 자동 운용은 업비트 API 키가 저장되어 있고 `AUTO_TRADING_LIVE_ENABLED=true`를 명시한 뒤 설정 화면의 `서버 시작` 버튼을 눌러야 시작된다.

ML 학습 패키지는 기본 설치에 포함하지 않는다. 나중에 오프라인 학습을 구현할 때 선택 의존성으로 설치한다.

```bash
pip install -e ".[ml]"
```

---

## 10. live 모드 전환

`live` 모드는 실제 업비트 주문 경로를 사용한다. 전환 전 아래를 확인한다.

- `demo` 모드에서 실주문 0건
- 대시보드 요약 정상
- 손절가 주입 정상
- 가격 손절/기대 불일치 손절 정상
- 재기동 복구 상태 정상
- 텔레그램 알림 정상
- 승격 기준 검토 완료
- 운영자 수동 승인 완료

전환 설정은 `/settings`에서 LIVE 스위치를 선택한 뒤 업비트 API 키를 입력해 저장하는 방식을 권장한다.
또는 `.env`에 아래 값을 직접 설정한다.

```bash
TRADING_MODE=live
LEARNING_ENABLED=true
UPBIT_ACCESS_KEY=발급받은_액세스키
UPBIT_SECRET_KEY=발급받은_시크릿키
PROMOTION_REQUIRE_MANUAL_APPROVAL=true
```

저장 또는 수정 후 앱을 재시작한다.

```bash
uv run uvicorn app.main:app --reload
```

주의:
- `live`는 실제 주문 API를 사용할 수 있으므로 API 키 권한과 주문 금액을 반드시 점검한다.
- `SAFE_MODE`와 `HARD_STOP` 상태에서는 live 주문이 차단된다.
- 운영 전 `RUNBOOK.md`의 live 운영 절차를 확인한다.

---

## 11. 테스트

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
.venv/bin/python -m pytest tests/unit/test_live_executor.py
.venv/bin/python -m pytest tests/unit/test_recovery_orchestrator.py
.venv/bin/python -m pytest tests/unit/test_sizing_engine.py
```

커밋 전 권장 확인:

```bash
.venv/bin/python -m pytest -q
pre-commit run --all-files
```

---

## 12. 운영 체크리스트

demo 시작 전:
- [ ] 앱 실행 후 `/settings` 접속 또는 `.env` 생성
- [ ] DEMO 모드 선택
- [ ] 데모 시작 투자금 `1,000,000 KRW` 확인 또는 변경
- [ ] `LEARNING_ENABLED=true`
- [ ] 마켓/코인 확인
- [ ] 텔레그램 알림을 쓸 경우 토큰/채팅 ID 입력
- [ ] `pytest` 통과

demo 운영 중:
- [ ] `/health` 정상
- [ ] `/dashboard` 정상
- [ ] 현재 가격 1초 갱신 확인
- [ ] AI 상태가 현재 상황에 맞게 표시되는지 확인
- [ ] 학습 로그 생성 확인
- [ ] 손절 라인/마커 확인
- [ ] 재기동 상태 파일 생성 확인
- [ ] 텔레그램 알림 확인

live 전환 전:
- [ ] `/settings`에서 LIVE 모드 선택
- [ ] 업비트 API 키 입력
- [ ] 승격 기준 검토
- [ ] 수동 승인 완료
- [ ] SAFE_MODE/HARD_STOP 상태 확인
- [ ] 주문 금액과 API 키 권한 확인
- [ ] `RUNBOOK.md` 확인

---

## 13. 문제 해결

### 앱 시작 시 설정 오류
`TRADING_MODE`와 `LEARNING_ENABLED`를 확인한다. GUI에서는 `/settings`에서 수정하고 앱을 재시작한다.

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
- `SIGNAL_BLOCKED`
- `SPREAD_OR_SLIPPAGE_LIMIT`
- `INVALID_CURRENT_PRICE`
- `STOP_LOSS_RISK_LIMIT`

신호 차단 상세 reason code 예:
- `LOW_LIQUIDITY_BLOCKED`
- `MICRO_MOMENTUM_REVERSAL_BLOCKED`
- `EXCESSIVE_SHORT_VOLATILITY_BLOCKED`

### live 모드 저장이 거절됨
`/settings`에서 LIVE를 선택했을 때 업비트 API 키가 비어 있으면 저장되지 않는다.

필수 값:
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`

demo 모드로 되돌리면 API 키 없이 저장할 수 있다.

### 장시간 거래가 없음
먼저 자동 운용 루프와 차단 사유를 확인한다.

```bash
curl http://127.0.0.1:8080/learning/diagnostics
```

`AUTO_TRADING_NOT_RUNNING`이면 서버가 새 코드로 재시작되었는지, `AUTO_TRADING_ENABLED=true`인지 확인한다.
`TRADE_BLOCKED_BY_RULES`이면 `auto_cycle_blocked_reasons`, `sizing_blocked_reasons`, `signal_reason_codes`를 확인한다.

---

## 14. 참고 문서
- `README.md`
- `ENV_SPEC.md`
- `RUNBOOK.md`
- `Tasklist.md`
- `PRD.md`
- `STRATEGY_SPEC.md`
- `AI.md`
