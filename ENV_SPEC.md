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
SERVER_NAME=서울-데모-1
APP_TIMEZONE=Asia/Seoul
ENV_FILE_PATH=.env

TRADING_MODE=demo
LEARNING_ENABLED=true

RULE_REVIEW_ENABLED=true
RULE_REVIEW_WINDOW_DAYS=14
RULE_REVIEW_MIN_TRADES=100
RULE_REVIEW_MIN_STOPLOSSES=20
RULE_CHANGE_MAX_PARAMS_PER_RUN=3
RULE_CHANGE_APPLY_TARGET=demo
RULE_CHANGE_REQUIRE_MANUAL_APPROVAL=false

EXTERNAL_CONTEXT_ENABLED=true
EXTERNAL_CONTEXT_CACHE_TTL_SEC=30
ONCHAIN_CONTEXT_SOURCE=manual
ONCHAIN_CONTEXT_URL=
ONCHAIN_STATE=neutral
ONCHAIN_ACTIVE_ADDRESSES_CHANGE_PCT=0.0
ONCHAIN_EXCHANGE_NETFLOW_STATE=neutral
ETF_CONTEXT_SOURCE=web
ETF_CONTEXT_URL=
ETF_STATE=neutral
ETF_FLOW_USD=0.0
NO_TRADE_ADAPTIVE_ENABLED=true
NO_TRADE_RELAX_AFTER_CYCLES=100
NO_TRADE_RELAX_MIN_SCORE=0.18

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

BUY_RATIO_WEAK=0.10
BUY_RATIO_MEDIUM=0.24
BUY_RATIO_STRONG=0.48
BUY_RATIO_VERY_STRONG=0.72

SELL_RATIO_WEAK=0.35
SELL_RATIO_MEDIUM=0.55
SELL_RATIO_STRONG=0.75
SELL_RATIO_VERY_STRONG=0.90

STOP_LOSS_WEAK=0.030
STOP_LOSS_MEDIUM=0.030
STOP_LOSS_STRONG=0.030
STOP_LOSS_VERY_STRONG=0.030

VALIDATION_WINDOW_SEC=180
MIN_EXPECTED_RETURN_PCT=0.004
TRADING_PROFILE=scalping
TRADING_FEE_RATE=0.0005
MIN_ORDER_AMOUNT_KRW=5000
PROFILE_MIN_NET_EDGE_PCT=0.0008

MIN_CASH_RESERVE=100000
CAPITAL_RISK_PCT=0.018
MAX_DAILY_LOSS=150000
MAX_SLIPPAGE_BPS=20
MAX_SPREAD_BPS=15
COOLDOWN_SECONDS=60
REENTRY_BLOCK_SECONDS=180
SIDEWAYS_RISK_GUARD_ENABLED=true
SIDEWAYS_PRICE_RANGE_PCT=0.002
SIDEWAYS_TRADED_VALUE_RANGE_PCT=0.003
SIDEWAYS_MAX_AVG_ABS_RETURN_PCT=0.001
SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT=0.003

STORAGE_DIR=./storage
SAFE_MODE_ON_RESTART=true
RESTART_NOTIFY=true
RESTART_HARD_STOP_THRESHOLD=3
RESTART_STATE_PATH=./storage/runtime/recovery/restart-state.json

AUTO_PROMOTE_TO_LIVE=false
PROMOTION_REQUIRE_MANUAL_APPROVAL=true
DEMO_MIN_DAYS=14
DEMO_MIN_TRADES=100
DEMO_MIN_WIN_RATE=0.52
DEMO_MIN_PROFIT_FACTOR=1.20
DEMO_MAX_DRAWDOWN=0.08
DEMO_MAX_STOPLOSS_FAILURES=0
DEMO_INITIAL_CAPITAL=1000000
AUTO_TRADING_ENABLED=true
AUTO_TRADING_LIVE_ENABLED=false
AUTO_TRADING_INTERVAL_SEC=3.0
AUTO_TRADING_MIN_HISTORY=6

LOG_LEVEL=INFO
LOG_FORMAT=json
LEARNING_LOG_DIR=./storage/logs/learning
LEARNING_DATASET_DIR=./storage/data/learning
MODEL_FEATURE_LOGGING=true
DECISION_TRACE_LOGGING=true
AUTO_RULE_UPDATE_ENABLED=false
AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE=1.0
AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD=0.80

DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080
```

---

## 4. 변수 설명

| 변수명 | 타입 | 필수 | 예시 | 설명 |
|---|---|---:|---|---|
| APP_ENV | str | Y | production | 실행 환경 |
| APP_NAME | str | Y | upbit-auto-trader | 애플리케이션 이름 |
| SERVER_NAME | str | Y | 서울-데모-1 | 텔레그램 알림 첫 줄에 `[SERVER_NAME]` 형식으로 표시되는 서버 구분 이름 |
| APP_TIMEZONE | str | Y | Asia/Seoul | 기본 시간대 |
| ENV_FILE_PATH | str | N | .env | GUI 설정 화면이 읽고 쓰는 환경 파일 경로 |
| TRADING_MODE | str | Y | demo | 실행 모드, demo/live만 허용 |
| LEARNING_ENABLED | bool | Y | true | 항상 true여야 함 |
| RULE_REVIEW_ENABLED | bool | Y | true | 학습 로그 기반 룰 개선 분석 기능 활성화 여부 |
| RULE_REVIEW_WINDOW_DAYS | int | Y | 14 | 룰 개선 분석 대상 최근 기간 |
| RULE_REVIEW_MIN_TRADES | int | Y | 100 | 룰 변경안 생성을 허용하는 최소 거래 수 |
| RULE_REVIEW_MIN_STOPLOSSES | int | Y | 20 | 손절 관련 룰 변경안 생성을 허용하는 최소 손절 수 |
| RULE_CHANGE_MAX_PARAMS_PER_RUN | int | Y | 3 | 한 번의 룰 개선 실행에서 바꿀 수 있는 최대 파라미터 수 |
| AUTO_RULE_UPDATE_NO_TRADE_HOURS | float | Y | 24 | 마지막 체결 이후 이 시간 이상 거래가 없고 차단 로그가 있으면 자동 룰 개선을 시작하는 기준 |
| RULE_CHANGE_APPLY_TARGET | str | Y | demo | 룰 변경안 기본 적용 대상, demo만 허용 |
| RULE_CHANGE_REQUIRE_MANUAL_APPROVAL | bool | Y | false | demo 룰 개선 자동 적용 여부와 별개인 live 반영 전 수동 승인 필수 여부 |
| EXTERNAL_CONTEXT_ENABLED | bool | Y | true | 온체인/ETF 외부 컨텍스트 학습 로그 및 대시보드 표시 활성화 |
| EXTERNAL_CONTEXT_CACHE_TTL_SEC | int | Y | 30 | HTTP 온체인/ETF 컨텍스트 성공 응답 캐시 시간 |
| ONCHAIN_CONTEXT_SOURCE | str | Y | manual | 온체인 데이터 출처, 초기값은 수동/운영 입력 |
| ONCHAIN_CONTEXT_URL | str | N |  | 선택 HTTP 온체인 컨텍스트 JSON endpoint |
| ONCHAIN_STATE | str | Y | neutral | 온체인 상태, bullish/neutral/bearish |
| ONCHAIN_ACTIVE_ADDRESSES_CHANGE_PCT | float | Y | 0.0 | 활성 주소 변화율 |
| ONCHAIN_EXCHANGE_NETFLOW_STATE | str | Y | neutral | 거래소 순유입 상태, inflow/neutral/outflow |
| ETF_CONTEXT_SOURCE | str | Y | web | ETF 데이터 출처, URL이 비어 있으면 공개 웹 데이터 provider 사용 |
| ETF_CONTEXT_URL | str | N |  | 선택 HTTP ETF 컨텍스트 JSON endpoint |
| ETF_STATE | str | Y | neutral | ETF 자금 흐름 상태, inflow/neutral/outflow/not_applicable |
| ETF_FLOW_USD | float | Y | 0.0 | ETF 순유입/순유출 금액 USD |

`ONCHAIN_CONTEXT_URL`과 `ETF_CONTEXT_URL`이 비어 있으면 앱은 기본 웹 공개 데이터 provider를 사용한다. BTC 온체인은 Blockchain.com Charts, XRP 온체인은 XRPSCAN ledger activity, ETF/ETP 흐름은 거래 코인별 Coinglass 공개 ETF 자료를 우선 조회하고 BTC는 Farside ETF flow 표, XRP는 XRP Insights를 보조 조회한다. 조회 실패 시 기존 수동 설정값으로 fallback한다.
| NO_TRADE_ADAPTIVE_ENABLED | bool | Y | true | 무거래 누적 시 demo 진입 기준 완화 정책 활성화 |
| NO_TRADE_RELAX_AFTER_CYCLES | int | Y | 100 | 완화 판단 전 연속 진입 차단 사이클 수 |
| NO_TRADE_RELAX_MIN_SCORE | float | Y | 0.18 | 완화 시 허용할 최소 weak signal score |
| TRADE_MARKET | str | Y | KRW-XRP | 거래 마켓 |
| TRADE_COIN | str | Y | XRP | 거래 코인 심볼 |
| UPBIT_ACCESS_KEY | str | Y |  | 업비트 액세스 키 |
| UPBIT_SECRET_KEY | str | Y |  | 업비트 시크릿 키 |
| TELEGRAM_BOT_TOKEN | str | Y |  | 텔레그램 봇 토큰 |
| TELEGRAM_CHAT_ID | str | Y |  | 텔레그램 채팅 ID |
| BUY_RATIO_WEAK | float | Y | 0.10 | weak 매수 비율 |
| BUY_RATIO_MEDIUM | float | Y | 0.24 | medium 매수 비율 |
| BUY_RATIO_STRONG | float | Y | 0.48 | strong 매수 비율 |
| BUY_RATIO_VERY_STRONG | float | Y | 0.72 | very strong 매수 비율 |
| SELL_RATIO_WEAK | float | Y | 0.35 | weak 매도 비율 |
| SELL_RATIO_MEDIUM | float | Y | 0.55 | medium 매도 비율 |
| SELL_RATIO_STRONG | float | Y | 0.75 | strong 매도 비율 |
| SELL_RATIO_VERY_STRONG | float | Y | 0.90 | very strong 매도 비율 |
| STOP_LOSS_WEAK | float | Y | 프로필 고정값 | 룰 변경 대상이 아닌 고정 손절 비율 |
| STOP_LOSS_MEDIUM | float | Y | 프로필 고정값 | 룰 변경 대상이 아닌 고정 손절 비율 |
| STOP_LOSS_STRONG | float | Y | 프로필 고정값 | 룰 변경 대상이 아닌 고정 손절 비율 |
| STOP_LOSS_VERY_STRONG | float | Y | 프로필 고정값 | 룰 변경 대상이 아닌 고정 손절 비율 |
| VALIDATION_WINDOW_SEC | int | Y | 180 | 기대 검증 시간 |
| MIN_EXPECTED_RETURN_PCT | float | Y | 0.004 | 최소 기대 수익률 |
| TRADING_PROFILE | str | Y | scalping | 투자성향/전략 프로필, scalping/short_term/mid_term/long_term |
| TRADING_FEE_RATE | float | Y | 0.0005 | 업비트 KRW 마켓 거래 수수료율 0.05%를 소수로 저장 |
| MIN_ORDER_AMOUNT_KRW | float | Y | 5000 | 업비트 KRW 마켓 최소 주문 가능 금액 |
| PROFILE_MIN_NET_EDGE_PCT | float | Y | 0.0008 | 왕복 수수료를 제외하고 현재 투자성향 진입에 요구하는 최소 순엣지 |
| MIN_CASH_RESERVE | int | Y | 100000 | 최소 현금 보유 |
| CAPITAL_RISK_PCT | float | Y | 0.018 | 투자 가능 현금 대비 1회 진입 손절 리스크 예산 비율 |
| MAX_DAILY_LOSS | int | Y | 150000 | 일일 손실 한도 |
| MAX_SLIPPAGE_BPS | int | Y | 20 | 허용 슬리피지 상한 |
| MAX_SPREAD_BPS | int | Y | 15 | 허용 spread 상한 |
| COOLDOWN_SECONDS | int | Y | 60 | 신호 cooldown |
| REENTRY_BLOCK_SECONDS | int | Y | 180 | 손절 후 재진입 차단 |
| SIDEWAYS_RISK_GUARD_ENABLED | bool | Y | true | 가격/거래대금 횡보 구간의 약신호 완화 매수와 평단 근처 추가매수 차단 |
| SIDEWAYS_PRICE_RANGE_PCT | float | Y | 0.002 | 횡보장 판단에 사용하는 최근 가격 범위 상한 |
| SIDEWAYS_TRADED_VALUE_RANGE_PCT | float | Y | 0.003 | 횡보장 판단에 사용하는 최근 거래대금 범위 상한 |
| SIDEWAYS_MAX_AVG_ABS_RETURN_PCT | float | Y | 0.001 | 횡보장 판단에 사용하는 평균 절대 가격 변화율 상한 |
| SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT | float | Y | 0.003 | 횡보장 추가매수를 허용하기 위한 기존 진입가 대비 최소 할인율 |
| MARKET_SHOCK_GUARD_ENABLED | bool | Y | true | 급락 구간 신규 매수/추가매수 관망 가드와 급락/급등 텔레그램 알림 활성화 |
| MARKET_CRASH_CHANGE_PCT | float | Y | -0.015 | 최근 판단 창 기준 급락 감지 변화율 |
| MARKET_SURGE_CHANGE_PCT | float | Y | 0.020 | 최근 판단 창 기준 급등 감지 변화율 |
| MARKET_RECOVERY_CHANGE_PCT | float | Y | 0.003 | 급락 후 매수 재개에 필요한 회복 변화율 |
| MARKET_RECOVERY_CONFIRMATION_TICKS | int | Y | 3 | 급락 후 매수 재개 전 확인할 연속 회복 tick 수 |
| MARKET_SHOCK_ALERT_COOLDOWN_SEC | int | Y | 300 | 급락/급등 텔레그램 알림 중복 방지 시간 |
| STORAGE_DIR | str | Y | ./storage | 코드와 분리해 보존하는 데이터 루트 |
| SAFE_MODE_ON_RESTART | bool | Y | true | 재기동 후 SAFE_MODE 여부 |
| RESTART_NOTIFY | bool | Y | true | 재기동 텔레그램 알림 여부 |
| RESTART_HARD_STOP_THRESHOLD | int | Y | 3 | 연속 재기동 허용 횟수 |
| RESTART_STATE_PATH | str | Y | ./storage/runtime/recovery/restart-state.json | 재기동 복구 상태 파일 경로 |
| AUTO_PROMOTE_TO_LIVE | bool | Y | false | 자동 승격 허용 여부 |
| PROMOTION_REQUIRE_MANUAL_APPROVAL | bool | Y | true | 수동 승인 필요 여부 |
| DEMO_MIN_DAYS | int | Y | 14 | 승격 최소 데모 일수 |
| DEMO_MIN_TRADES | int | Y | 100 | 승격 최소 거래 수 |
| DEMO_MIN_WIN_RATE | float | Y | 0.52 | 승격 최소 승률 |
| DEMO_MIN_PROFIT_FACTOR | float | Y | 1.20 | 승격 최소 PF |
| DEMO_MAX_DRAWDOWN | float | Y | 0.08 | 승격 최대 MDD |
| DEMO_MAX_STOPLOSS_FAILURES | int | Y | 0 | 승격 허용 손절 실패 수 |
| DEMO_INITIAL_CAPITAL | int | Y | 1000000 | demo 모드 가상 시작 투자금 |
| AUTO_TRADING_ENABLED | bool | Y | true | 설정 화면 시작 버튼 노출/자동 운용 허용 여부 |
| AUTO_TRADING_LIVE_ENABLED | bool | Y | false | live 모드 시작 버튼 노출/자동 운용 명시 허용 여부 |
| AUTO_TRADING_INTERVAL_SEC | float | Y | 3.0 | 자동 운용 현재가 수집/판단 주기 |
| AUTO_TRADING_MIN_HISTORY | int | Y | 6 | 자동 판단 전 필요한 최소 현재가 히스토리 수 |
| LOG_LEVEL | str | Y | INFO | 로그 레벨 |
| LOG_FORMAT | str | Y | json | 구조화 로그 형식, json만 허용 |
| LEARNING_LOG_DIR | str | Y | ./storage/logs/learning | 구조화 로그 디렉터리 |
| LEARNING_DATASET_DIR | str | Y | ./storage/data/learning | 데이터셋 출력 디렉터리 |
| MODEL_FEATURE_LOGGING | bool | Y | true | 모델 입력 feature 로그 저장 여부 |
| DECISION_TRACE_LOGGING | bool | Y | true | 의사결정 trace 로그 저장 여부 |
| AUTO_RULE_UPDATE_ENABLED | bool | Y | false | 자동 룰 업데이트 모드 |
| AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE | float | Y | 1.0 | 자동 룰 업데이트에 필요한 학습데이터 충족률 |
| AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD | float | Y | 0.80 | 이 승률 이상이면 자동 룰 업데이트 중단 |
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

### RULE_REVIEW / RULE_CHANGE
- 룰 개선은 `RULE_REVIEW_ENABLED=true`일 때만 실행한다.
- 자동 룰 개선은 학습데이터 충족률 기준 외에도 `AUTO_RULE_UPDATE_NO_TRADE_HOURS` 기본 24시간 동안 체결이 없고 자동매매 차단 로그가 누적되면 실행된다.
- `RULE_REVIEW_WINDOW_DAYS` 최근 로그를 기본 분석 대상으로 한다.
- `RULE_REVIEW_MIN_TRADES` 미만이면 변경안 생성은 `insufficient_sample` 상태로 차단한다.
- 손절 수가 `RULE_REVIEW_MIN_STOPLOSSES` 미만이면 손절 파라미터 변경안은 만들지 않는다.
- `RULE_CHANGE_MAX_PARAMS_PER_RUN`을 초과하는 파라미터 변경은 거부한다.
- `RULE_CHANGE_APPLY_TARGET=demo`만 허용한다. live 직접 적용은 금지한다.
- `RULE_CHANGE_REQUIRE_MANUAL_APPROVAL=false`가 기본이며, 대시보드 룰 개선은 replay 통과 시 demo에 자동 적용된다. live 반영 API는 별도의 승인 상태와 demo/replay 결과를 요구한다.
- 룰 변경 히스토리는 코인/투자성향별 `rule-change-history.jsonl`에 append-only로 저장한다.
- 히스토리에는 기존 룰 snapshot, 신규 룰 snapshot, 변경 사유, 기대 효과, 알려진 리스크, replay/demo/live 결과, 승인자, 한국어 커밋 메시지와 commit hash가 포함되어야 한다.
- live 승인 전 동일 파라미터의 과거 실패/rollback 이력을 확인해야 한다.

### RULE_CHANGE_HISTORY schema
`rule-change-history.jsonl`은 JSON Lines 파일이며 각 줄은 하나의 append-only 이벤트다.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| history_id | str | Y | 히스토리 이벤트 ID |
| event_type | str | Y | proposal_created/replay_verified/demo_applied/demo_apply_rejected/live_approved/live_approval_rejected/commit_linked/rollback/correction |
| review_id | str | Y | 리뷰 ID |
| proposal_id | str | Y | proposal ID |
| market | str | Y | 대상 마켓 |
| trade_coin | str | Y | 대상 코인 |
| trading_profile | str | Y | 투자성향 |
| mode | str | Y | 실행 모드 |
| learning_log_dir | str | Y | 학습 로그 디렉터리 |
| analysis_window_days | int | Y | 분석 기간 |
| trade_count | int | Y | 거래 표본 수 |
| stop_loss_count | int | Y | 손절 표본 수 |
| major_loss_causes | array | Y | 주요 손실 원인 |
| blocked_reason_summary | array | Y | 차단/거절 사유 |
| external_context_summary | object | Y | 온체인/ETF 컨텍스트 요약 |
| previous_rule_snapshot | object | Y | 변경 전 파라미터 |
| proposed_rule_snapshot | object | Y | 변경 후 후보 파라미터 |
| changed_parameters | array | Y | 변경 파라미터 목록 |
| optimization_tracking | object | Y | 변경 전 기준값과 다음 리뷰에서 비교할 최적화 지표 목록 |
| change_reason | str | Y | 변경 사유 |
| expected_effect | str | Y | 기대 효과 |
| known_risks | str | Y | 알려진 리스크 |
| replay_result | object/null | Y | replay 결과 |
| demo_result | object | Y | demo 적용 결과 |
| approval_status | str | Y | pending/passed/failed/applied/approved/rejected/linked 등 |
| approved_by | str | Y | 승인자, 없으면 빈 문자열 |
| applied_target | str | Y | 적용 대상 |
| created_at | str | Y | ISO-8601 시각 |
| commit_hash | str | Y | 커밋 hash, 커밋 전 이벤트는 빈 문자열 허용 |

`event_type=correction` 행은 선택 필드 `correction_detail`을 포함할 수 있다. 이 객체에는 `reason`, `corrected_fields`, `corrected_by`를 저장해 기존 행을 수정하지 않고 보정 근거를 남긴다.

`event_type=rollback` 행은 선택 필드 `rollback_detail`을 포함할 수 있다. 이 객체에는 `reason`, `target`, `rolled_back_by`를 저장해 문제가 생긴 룰 변경안을 어느 대상에서 되돌렸는지 남긴다.

### TRADE_MARKET / TRADE_COIN
- 기본값은 `TRADE_COIN=XRP`, `TRADE_MARKET=KRW-XRP`이다.
- 코인은 XRP에 고정하지 않는다. 예를 들어 BTC로 운용하려면 `TRADE_COIN=BTC`, `TRADE_MARKET=KRW-BTC`를 저장한다.
- `TRADE_MARKET`의 코인 suffix는 반드시 `TRADE_COIN`과 일치해야 한다. 설정 저장 시 KRW 마켓은 코인에 맞춰 자동 보정하고, 런타임 로딩/시작 readiness에서는 불일치를 차단한다.
- XRP는 기존 호환을 위해 `LEARNING_LOG_DIR/<TRADING_PROFILE>/learning.jsonl`을 사용하고, BTC/ETH/SOL 등 다른 코인은 `LEARNING_LOG_DIR/<TRADE_COIN>/<TRADING_PROFILE>/learning.jsonl`에 학습 로그를 분리 저장한다.
- 설정 화면에서 기본 XRP 상태에서 코인만 BTC로 바꾸면 저장 시 `TRADE_MARKET=KRW-BTC`로 보정한다.
- 코인을 바꾸면 UI 라벨, 대시보드, 텔레그램 메시지, 학습 로그 market도 함께 바뀌어야 한다.

### EXTERNAL_CONTEXT / ONCHAIN / ETF
- 온체인/ETF 컨텍스트는 학습 로그의 `external_market_context_snapshot`과 `auto_trade_cycle.external_context`에 기록한다.
- BTC/ETH는 ETF 컨텍스트를 표시하고, 그 외 코인은 ETF 상태를 `not_applicable`로 기록한다.
- `ONCHAIN_CONTEXT_URL` 또는 `ETF_CONTEXT_URL`이 있으면 시스템이 `market`, `coin` 쿼리 파라미터로 JSON을 조회하고, 실패하면 manual 설정값으로 fallback한다.
- 성공 응답은 `EXTERNAL_CONTEXT_CACHE_TTL_SEC` 동안 재사용해 대시보드 새로고침과 자동매매 루프의 외부 API 호출을 제한한다.
- endpoint 응답은 직접 `{state, active_addresses_change_pct, exchange_netflow_state}` 또는 `{context: {...}}` 형식을 허용한다. ETF endpoint는 `{state, flow_usd}` 또는 `{context: {...}}`를 허용한다.
- ETF 공개 데이터는 순유입과 순유출을 분리해 보관하되, 대시보드에는 0이 아닌 방향만 표시한다. API 응답에 별도 `inFlowUsd`/`outFlowUsd`가 있으면 `change` 값보다 우선해 순유출 0 고정 표시를 방지한다.
- bullish/onchain outflow/ETF inflow는 학습 가중치를 높이고, bearish/onchain inflow/ETF outflow는 낮춘다.
- 룰 개선 분석은 학습 로그의 외부 컨텍스트 표본 수, 온체인/ETF 상태 분포, 평균 학습 가중치를 함께 집계한다.
- 가격/거래량 원시 관측값은 `LEARNING_LOG_DIR/<코인>/<투자성향>/market-observations.jsonl` 또는 기본 XRP의 `LEARNING_LOG_DIR/<투자성향>/market-observations.jsonl`에 append-only로 저장한다.
- 룰 개선 replay는 원시 관측값이 충분하면 이를 우선 사용하고, replay 결과에는 signal count, blocked count, trade count, final profit rate, max drawdown을 함께 남긴다.

### NO_TRADE_ADAPTIVE
- demo에서 `AUTO_MIN_SIGNAL_LEVEL` 또는 `FEE_ADJUSTED_EDGE_LIMIT` 차단만 반복되면 완화 후보로 진단한다.
- `NO_TRADE_RELAX_AFTER_CYCLES` 이상 연속 차단되고 signal score가 `NO_TRADE_RELAX_MIN_SCORE` 이상이면 demo에서 weak 신호도 실행 후보로 허용하며, 수수료 보정 엣지 차단은 완화 재평가를 수행한다.
- live에서는 이 완화 정책이 SAFE_MODE/HARD_STOP/API 키/리스크 게이트를 우회할 수 없다.

### AUTO_PROMOTE_TO_LIVE / 승인 정책
- 기본은 `AUTO_PROMOTE_TO_LIVE=false`
- 권장값은 수동 승인 필요

### STORAGE_DIR / 데이터 보존 정책
- 코드 디렉터리와 학습데이터/DB/로그/데이터셋/룰 변경 이력은 `STORAGE_DIR`로 분리한다.
- 기본값은 `./storage`이며 Docker는 `./storage:/app/storage` 볼륨으로 영속화한다.
- 기존 `logs/`와 `data/`를 유지하려면 업데이트 전에 `mkdir -p storage && mv logs storage/logs && mv data storage/data`를 실행하거나, `.env`에 기존 `LEARNING_LOG_DIR`/`LEARNING_DATASET_DIR` 경로를 그대로 남긴다.
- 룰 변경 이력은 `LEARNING_LOG_DIR/<코인>/<투자성향>/rule-change-history.jsonl` 또는 기본 XRP의 `LEARNING_LOG_DIR/<투자성향>/rule-change-history.jsonl`에 append-only로 유지된다.
- 시장 원시 관측 이력은 같은 디렉터리의 `market-observations.jsonl`에 append-only로 유지되어 룰 개선과 replay 재현에 사용된다.

### AUTO_RULE_UPDATE_* / 자동 룰 업데이트 정책
- `AUTO_RULE_UPDATE_ENABLED=true`일 때만 자동 룰 재평가 게이트가 활성화된다.
- 학습데이터 충족률이 `AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE` 미만이면 자동 변경을 차단한다.
- 승률이 `AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD` 이상이면 자동 변경을 차단한다. 기본 0.80은 승률 80% 이상 유지 구간에서 룰을 흔들지 않기 위한 안전장치다.
- 자동 변경은 review, proposal, replay, demo 적용 결과를 `rule-change-history.jsonl`에 기록한다. replay 실패 또는 게이트 미달이면 live 적용을 진행하지 않는다.
- 매매 로직 변경이 적용된 자동매매 사이클은 `auto_trade_cycle.payload.trade_logic_update_trace`에 로직 버전, 적용 여부, 기존 차단 사유, 비교 지표 키를 남겨 다음 룰 개선에서 최적화 효과를 비교한다.

### AUTO_TRADING_ENABLED / live 안전 정책
- 앱 부팅만으로 자동 운용 루프를 시작하지 않는다.
- 설정 화면에서 필수값을 저장한 뒤 `서버 시작` 버튼을 눌렀을 때 자동 운용 루프를 시작한다.
- demo 모드는 필수값이 저장되어 있어야 `서버 시작` 버튼이 보인다.
- live 모드는 업비트 API 키가 저장되어 있고 `AUTO_TRADING_ENABLED=true`, `AUTO_TRADING_LIVE_ENABLED=true`가 모두 설정되어야 `서버 시작` 버튼이 보인다.
- live에서 API 키, SAFE_MODE, HARD_STOP, trading_ready 상태가 조건을 만족하지 않으면 주문은 차단된다.

### DASHBOARD_HOST / DASHBOARD_PORT
- 기본 바인딩은 `DASHBOARD_HOST=0.0.0.0`, `DASHBOARD_PORT=8080`이다.
- 로컬 브라우저는 `http://127.0.0.1:8080/settings`와 `http://127.0.0.1:8080/dashboard`를 사용한다.
- 같은 네트워크의 다른 기기는 `http://<내 컴퓨터 LAN IP>:8080/settings`와 `http://<내 컴퓨터 LAN IP>:8080/dashboard`를 사용한다.
- 앱 서버 시작 텔레그램 알림에는 로컬 주소와 LAN 주소가 함께 포함되고, 자동 트레이딩은 아직 시작되지 않았다는 안내를 포함한다.

### TRADING_PROFILE / 투자성향 정책
- 허용값은 `scalping`, `short_term`, `mid_term`, `long_term`이다.
- 설정 화면에서는 각각 단타, 단기, 중기, 장기로 표시한다.
- 투자성향을 저장하면 해당 성향의 기본 `AUTO_TRADING_INTERVAL_SEC`, `AUTO_TRADING_MIN_HISTORY`, `PROFILE_MIN_NET_EDGE_PCT`, `VALIDATION_WINDOW_SEC`, `MIN_EXPECTED_RETURN_PCT`가 함께 `.env`에 저장된다.
- 업비트 고객센터 기준 일반 KRW 마켓 수수료 0.05%를 `TRADING_FEE_RATE=0.0005`로 사용한다.
- 업비트 공식 KRW 마켓 최소 주문 가능 금액 5,000원을 `MIN_ORDER_AMOUNT_KRW=5000`으로 사용한다.
- 진입은 예상 엣지가 왕복 수수료 `TRADING_FEE_RATE * 2`와 `PROFILE_MIN_NET_EDGE_PCT`를 합친 값보다 클 때만 허용한다.
- 위 조건을 넘기지 못하면 `FEE_ADJUSTED_EDGE_LIMIT`으로 차단되어 학습 로그에 남는다.
- 학습 로그는 기본 XRP에서는 `LEARNING_LOG_DIR/<TRADING_PROFILE>/learning.jsonl`, 다른 코인에서는 `LEARNING_LOG_DIR/<TRADE_COIN>/<TRADING_PROFILE>/learning.jsonl`에 분리 저장한다.

기본 프로필:

| 값 | 표시 | 주기 | 히스토리 | 최소 순엣지 | 검증 창 | 최소 기대수익 | 고정 손절 |
|---|---|---:|---:|---:|---:|---:|---:|
| scalping | 단타 | 3초 | 6 | 0.08% | 180초 | 0.40% | -3.00% |
| short_term | 단기 | 10초 | 12 | 0.20% | 900초 | 0.80% | -3.00% |
| mid_term | 중기 | 30초 | 20 | 0.60% | 3600초 | 1.50% | -5.00% |
| long_term | 장기 | 60초 | 30 | 1.20% | 14400초 | 3.00% | -10.00% |

손절률은 투자성향의 고정값으로만 적용한다. `.env`에 `STOP_LOSS_*` 값이 남아 있어도 런타임은 프로필 고정 손절률로 덮어쓰며, Codex 룰 개선 제안은 손절 파라미터를 변경할 수 없다.

### 코드 설정 스키마 계약
`app.core.settings.SettingsModel`과 `AppSettings`는 이 문서의 필수 변수 전체를 필드로 가진다.
환경 변수가 추가되면 `tests/unit/test_settings.py`의 스키마 계약 테스트를 먼저 갱신한 뒤 코드와 문서를 함께 수정한다.

---

## 6. 운영 예시

### demo 시작
```bash
TRADING_MODE=demo
LEARNING_ENABLED=true
RULE_REVIEW_ENABLED=true
RULE_REVIEW_WINDOW_DAYS=14
RULE_REVIEW_MIN_TRADES=100
RULE_REVIEW_MIN_STOPLOSSES=20
RULE_CHANGE_MAX_PARAMS_PER_RUN=3
RULE_CHANGE_APPLY_TARGET=demo
RULE_CHANGE_REQUIRE_MANUAL_APPROVAL=false
DEMO_INITIAL_CAPITAL=1000000
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
SERVER_NAME=서울-데모-1
APP_TIMEZONE=Asia/Seoul

TRADING_MODE=demo
LEARNING_ENABLED=true

TRADE_MARKET=KRW-XRP
TRADE_COIN=XRP

UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

DEMO_INITIAL_CAPITAL=1000000
```

---

## 9. Git/TDD 반영 규칙
환경 변수가 추가되거나 변경되면 반드시 아래를 함께 수정한다.
- 코드 settings schema
- `.env.example`
- `ENV_SPEC.md`
- 관련 테스트
- 한국어 Git 커밋 메시지
