# ENV_SPEC.md

## 1. 목적
이 문서는 업비트 자동매매 시스템의 환경 변수 스펙을 정의한다.

---

## 2. 기본 원칙
- 실제 비밀값은 `.env` 또는 Secret Manager에만 저장
- 저장소에는 `.env.example`만 커밋
- 코드에 하드코딩 금지
- 실행 모드는 `demo` 또는 `live`만 허용
- 학습은 항상 활성화되어야 함

---

## 3. 필수 변수

```bash
APP_ENV=production
APP_NAME=upbit-auto-trader
APP_TIMEZONE=Asia/Seoul

TRADING_MODE=demo
LEARNING_ENABLED=true

TRADE_MARKET=KRW-XRP
TRADE_COIN=XRP

UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=
UPBIT_BASE_URL=https://api.upbit.com
UPBIT_WS_PUBLIC_URL=wss://api.upbit.com/websocket/v1
UPBIT_WS_PRIVATE_URL=wss://api.upbit.com/websocket/v1/private

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_NOTIFY_IN_DEMO=true

BUY_RATIO_WEAK=0.08
BUY_RATIO_MEDIUM=0.18
BUY_RATIO_STRONG=0.35
BUY_RATIO_VERY_STRONG=0.55

SELL_RATIO_WEAK=0.12
SELL_RATIO_MEDIUM=0.28
SELL_RATIO_STRONG=0.45
SELL_RATIO_VERY_STRONG=0.70

STOP_LOSS_WEAK=0.008
STOP_LOSS_MEDIUM=0.012
STOP_LOSS_STRONG=0.018
STOP_LOSS_VERY_STRONG=0.022

VALIDATION_WINDOW_SEC=180
MIN_EXPECTED_RETURN_PCT=0.004

MIN_CASH_RESERVE=100000
MAX_DAILY_LOSS=150000
MAX_SLIPPAGE_BPS=20
MAX_SPREAD_BPS=15
COOLDOWN_SECONDS=60
REENTRY_BLOCK_SECONDS=180

SAFE_MODE_ON_RESTART=true
RESTART_NOTIFY=true
RESTART_HARD_STOP_THRESHOLD=3

AUTO_PROMOTE_TO_LIVE=false
PROMOTION_REQUIRE_MANUAL_APPROVAL=true
DEMO_MIN_DAYS=14
DEMO_MIN_TRADES=100
DEMO_MIN_WIN_RATE=0.52
DEMO_MIN_PROFIT_FACTOR=1.20
DEMO_MAX_DRAWDOWN=0.08
DEMO_MAX_STOPLOSS_FAILURES=0

LOG_LEVEL=INFO
LOG_FORMAT=json
LEARNING_LOG_DIR=./logs/learning
LEARNING_DATASET_DIR=./data/learning
MODEL_FEATURE_LOGGING=true
DECISION_TRACE_LOGGING=true

DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080
```

---

## 4. 변수 설명

| 변수명 | 타입 | 필수 | 예시 | 설명 |
|---|---|---:|---|---|
| APP_ENV | str | Y | production | 실행 환경 |
| APP_NAME | str | Y | upbit-auto-trader | 애플리케이션 이름 |
| APP_TIMEZONE | str | Y | Asia/Seoul | 기본 시간대 |
| TRADING_MODE | str | Y | demo | 실행 모드, demo/live만 허용 |
| LEARNING_ENABLED | bool | Y | true | 항상 true여야 함 |
| TRADE_MARKET | str | Y | KRW-XRP | 거래 마켓 |
| TRADE_COIN | str | Y | XRP | 거래 코인 심볼 |
| UPBIT_ACCESS_KEY | str | Y |  | 업비트 액세스 키 |
| UPBIT_SECRET_KEY | str | Y |  | 업비트 시크릿 키 |
| TELEGRAM_BOT_TOKEN | str | Y |  | 텔레그램 봇 토큰 |
| TELEGRAM_CHAT_ID | str | Y |  | 텔레그램 채팅 ID |
| BUY_RATIO_WEAK | float | Y | 0.08 | weak 매수 비율 |
| BUY_RATIO_MEDIUM | float | Y | 0.18 | medium 매수 비율 |
| BUY_RATIO_STRONG | float | Y | 0.35 | strong 매수 비율 |
| BUY_RATIO_VERY_STRONG | float | Y | 0.55 | very strong 매수 비율 |
| SELL_RATIO_WEAK | float | Y | 0.12 | weak 매도 비율 |
| SELL_RATIO_MEDIUM | float | Y | 0.28 | medium 매도 비율 |
| SELL_RATIO_STRONG | float | Y | 0.45 | strong 매도 비율 |
| SELL_RATIO_VERY_STRONG | float | Y | 0.70 | very strong 매도 비율 |
| STOP_LOSS_WEAK | float | Y | 0.008 | weak 손절 비율 |
| STOP_LOSS_MEDIUM | float | Y | 0.012 | medium 손절 비율 |
| STOP_LOSS_STRONG | float | Y | 0.018 | strong 손절 비율 |
| STOP_LOSS_VERY_STRONG | float | Y | 0.022 | very strong 손절 비율 |
| VALIDATION_WINDOW_SEC | int | Y | 180 | 기대 검증 시간 |
| MIN_EXPECTED_RETURN_PCT | float | Y | 0.004 | 최소 기대 수익률 |
| MIN_CASH_RESERVE | int | Y | 100000 | 최소 현금 보유 |
| MAX_DAILY_LOSS | int | Y | 150000 | 일일 손실 한도 |
| MAX_SLIPPAGE_BPS | int | Y | 20 | 허용 슬리피지 상한 |
| MAX_SPREAD_BPS | int | Y | 15 | 허용 spread 상한 |
| COOLDOWN_SECONDS | int | Y | 60 | 신호 cooldown |
| REENTRY_BLOCK_SECONDS | int | Y | 180 | 손절 후 재진입 차단 |
| SAFE_MODE_ON_RESTART | bool | Y | true | 재기동 후 SAFE_MODE 여부 |
| RESTART_NOTIFY | bool | Y | true | 재기동 텔레그램 알림 여부 |
| RESTART_HARD_STOP_THRESHOLD | int | Y | 3 | 연속 재기동 허용 횟수 |
| AUTO_PROMOTE_TO_LIVE | bool | Y | false | 자동 승격 허용 여부 |
| PROMOTION_REQUIRE_MANUAL_APPROVAL | bool | Y | true | 수동 승인 필요 여부 |
| DEMO_MIN_DAYS | int | Y | 14 | 승격 최소 데모 일수 |
| DEMO_MIN_TRADES | int | Y | 100 | 승격 최소 거래 수 |
| DEMO_MIN_WIN_RATE | float | Y | 0.52 | 승격 최소 승률 |
| DEMO_MIN_PROFIT_FACTOR | float | Y | 1.20 | 승격 최소 PF |
| DEMO_MAX_DRAWDOWN | float | Y | 0.08 | 승격 최대 MDD |
| DEMO_MAX_STOPLOSS_FAILURES | int | Y | 0 | 승격 허용 손절 실패 수 |
| LOG_LEVEL | str | Y | INFO | 로그 레벨 |
| LOG_FORMAT | str | Y | json | 구조화 로그 형식, json만 허용 |
| LEARNING_LOG_DIR | str | Y | ./logs/learning | 구조화 로그 디렉터리 |
| LEARNING_DATASET_DIR | str | Y | ./data/learning | 데이터셋 출력 디렉터리 |
| MODEL_FEATURE_LOGGING | bool | Y | true | 모델 입력 feature 로그 저장 여부 |
| DECISION_TRACE_LOGGING | bool | Y | true | 의사결정 trace 로그 저장 여부 |
| DASHBOARD_HOST | str | Y | 0.0.0.0 | 대시보드 바인딩 호스트 |
| DASHBOARD_PORT | int | Y | 8080 | 대시보드 포트 |

---

## 5. 검증 규칙

### TRADING_MODE
허용값:
- `demo`
- `live`

그 외 값은 앱 시작 실패

### LEARNING_ENABLED
허용값:
- `true`만 허용

false면 앱 시작 실패

### TRADE_MARKET / TRADE_COIN
- `TRADE_COIN=XRP`, `TRADE_MARKET=KRW-XRP`
- 코인을 바꾸면 UI 라벨과 메시지도 함께 바뀌어야 한다

### AUTO_PROMOTE_TO_LIVE / 승인 정책
- 기본은 `AUTO_PROMOTE_TO_LIVE=false`
- 권장값은 수동 승인 필요

### 코드 설정 스키마 계약
`app.core.settings.SettingsModel`과 `AppSettings`는 이 문서의 필수 변수 전체를 필드로 가진다.
환경 변수가 추가되면 `tests/unit/test_settings.py`의 스키마 계약 테스트를 먼저 갱신한 뒤 코드와 문서를 함께 수정한다.

---

## 6. 운영 예시

### demo 시작
```bash
TRADING_MODE=demo
LEARNING_ENABLED=true
```

### live 전환
```bash
TRADING_MODE=live
LEARNING_ENABLED=true
PROMOTION_REQUIRE_MANUAL_APPROVAL=true
```

---

## 7. 보안 규칙
- `.env`는 커밋 금지
- `.env.example`만 커밋
- 운영 환경은 Secret Manager 우선
- 텔레그램 토큰과 업비트 키를 로그에 남기지 않음
- 프런트엔드에 노출 금지

---

## 8. .env.example 최소 예시
```bash
APP_ENV=production
APP_NAME=upbit-auto-trader
APP_TIMEZONE=Asia/Seoul

TRADING_MODE=demo
LEARNING_ENABLED=true

TRADE_MARKET=KRW-XRP
TRADE_COIN=XRP

UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 9. Git/TDD 반영 규칙
환경 변수가 추가되거나 변경되면 반드시 아래를 함께 수정한다.
- 코드 settings schema
- `.env.example`
- `ENV_SPEC.md`
- 관련 테스트
- 한국어 Git 커밋 메시지
