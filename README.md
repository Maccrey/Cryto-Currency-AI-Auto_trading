# README.md

## 1. 프로젝트 소개

### 제품명
**Upbit Momentum Auto Trader**

### 슬로건
**데모로 검증하고, 실거래로 확장하며, 모든 모드에서 계속 학습하는 업비트 자동매매 시스템**

### 핵심 소개
이 프로젝트는 업비트의 급등·급락 신호를 실시간으로 감지하고, 현재 보유 자산을 기준으로 자동 비중을 계산해 `demo` 또는 `live` 모드로 거래를 수행한다.  
매수 시 손절가를 함께 주입하고, 가격 기반 손절과 기대 불일치 손절을 모두 지원한다.  
모든 모드에서 학습 로그를 항상 기록한다. 초기 개선은 TensorFlow 직접 학습보다 Codex가 학습 로그를 분석해 룰 변경안을 제안하고, replay와 demo 검증 후 승인받아 live에 반영하는 흐름을 우선한다.

설정 화면에서 투자성향을 단타, 단기, 중기, 장기 중 선택할 수 있다. 현재가는 선택한 성향의 주기로 관찰하고, 업비트 KRW 마켓 수수료 0.05%의 왕복 비용과 성향별 최소 순엣지를 넘지 못하는 진입은 차단한다. 손절률은 단타/단기 -3%, 중기 -5%, 장기 -10% 고정값으로 적용하며 Codex 룰 변경 대상에서 제외한다. 학습 로그도 코인과 성향별 디렉터리에 분리 저장한다.

---

## 2. 실행 모드 정책

### 허용 모드
- `demo`
- `live`

### 공통 규칙
- 학습 로깅은 항상 ON
- 구조화 로그는 항상 저장
- 대시보드/텔레그램/재기동 기록 모두 유지

### demo 모드
- 실제 주문 API 호출 금지
- 가상 체결 사용
- 기본 가상 투자금 `1,000,000 KRW`
- 운영 흐름 전체 검증
- 실거래 승격 전 기본 운용 모드

### live 모드
- 실제 주문 허용
- 부팅 후 기본 SAFE_MODE
- 잔고 sync / 오픈오더 reconcile / health check 이후 활성화

---

## 3. 초기 운영 권장 방식
1. 기본값은 `demo`
2. 일정 기간 데모 운영
3. 승격 기준 평가
4. 운영자 승인 또는 자동 정책으로 `live` 전환
5. `live`에서도 계속 학습 로그 축적

---

## 4. 개발 환경

### 런타임 / 프레임워크
- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic v2

### 패키지 / 빌드
- uv 또는 pip
- pre-commit

### 타입 / 포맷 / 린트
- pre-commit

### 관찰성
- structlog

---

## 5. 권장 디렉터리 구조
```text
app/
  main.py
  api/
  core/
  domain/
  integrations/
    upbit/
    telegram/
  services/
  workers/
  dashboard/
strategy/
tests/
fixtures/
docs/
ops/
.codex/
```

---

## 6. 로컬 실행

### 가장 쉬운 실행
```bash
./start.sh
```

`start.sh`는 서버가 이미 실행 중이면 그대로 두고 크롬에서 설정 화면만 연다. 서버가 없으면 macOS `launchd` KeepAlive로 백그라운드 등록해 `0.0.0.0:8080`에 바인딩한다. 같은 네트워크의 다른 기기는 `http://<내 컴퓨터 LAN IP>:8080/settings`와 `http://<내 컴퓨터 LAN IP>:8080/dashboard`로 접속한다.

### uv 사용
```bash
uv sync
uv run uvicorn app.main:app --reload
uv run pytest -q
uv run pre-commit run --all-files
```

### pip 사용
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
pytest -q
pre-commit run --all-files
```

---

## 7. 환경 변수
실제 값은 `.env`에 두고, 저장소에는 `.env.example`만 둔다.
앱 실행 후 `/settings` 화면에서도 `.env` 값을 저장할 수 있다.
`demo` 모드는 업비트 API 키 없이 실행할 수 있고, `live` 모드 저장 시에는 API 키가 필요하다.

주요 변수:
- `TRADING_MODE=demo|live`
- `LEARNING_ENABLED=true`
- `RULE_REVIEW_ENABLED=true`
- `RULE_REVIEW_WINDOW_DAYS=14`
- `RULE_REVIEW_MIN_TRADES=100`
- `RULE_REVIEW_MIN_STOPLOSSES=20`
- `RULE_CHANGE_MAX_PARAMS_PER_RUN=3`
- `RULE_CHANGE_APPLY_TARGET=demo`
- `RULE_CHANGE_REQUIRE_MANUAL_APPROVAL=true`
- `EXTERNAL_CONTEXT_ENABLED=true`
- `EXTERNAL_CONTEXT_CACHE_TTL_SEC=30`
- `ONCHAIN_CONTEXT_URL=`
- `ONCHAIN_STATE=neutral`
- `ONCHAIN_ACTIVE_ADDRESSES_CHANGE_PCT=0.0`
- `ONCHAIN_EXCHANGE_NETFLOW_STATE=neutral`
- `ETF_CONTEXT_URL=`
- `ETF_STATE=neutral`
- `ETF_FLOW_USD=0.0`
- `NO_TRADE_ADAPTIVE_ENABLED=true`
- `STORAGE_DIR=./storage`
- `AUTO_RULE_UPDATE_ENABLED=false`
- `AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE=1.0`
- `AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD=0.80`
- `TRADE_MARKET=KRW-XRP`
- `TRADE_COIN=XRP`

`ONCHAIN_CONTEXT_URL`과 `ETF_CONTEXT_URL`을 비워두면 기본 웹 공개 데이터 소스를 사용한다. BTC 온체인은 Blockchain.com Charts, XRP 온체인은 XRPSCAN ledger activity, BTC ETF 흐름은 Farside ETF flow 표를 조회한다.
- `DEMO_INITIAL_CAPITAL=1000000`
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DASHBOARD_HOST=0.0.0.0`
- `DASHBOARD_PORT=8080`

자세한 스펙은 `ENV_SPEC.md`를 따른다.

BTC로 바꾸려면 설정 화면에서 코인을 `BTC`로 저장한다. 기본 XRP 상태에서 코인만 바꾸면 `TRADE_MARKET=KRW-BTC`로 보정된다. ETH, SOL 등도 같은 방식으로 `KRW-<코인>` 마켓을 사용한다. `TRADE_MARKET`과 `TRADE_COIN`이 불일치하면 시작을 차단한다. XRP는 기본 학습 로그 경로를 유지하고, 다른 코인은 `storage/logs/learning/<COIN>/<투자성향>/learning.jsonl`로 분리한다.

코드와 데이터는 기본적으로 `./storage` 아래에 분리된다. 기존 `logs/`와 `data/`를 보존한 채 업데이트하려면 앱을 중지한 뒤 `mkdir -p storage && mv logs storage/logs && mv data storage/data`를 실행하거나, `.env`에 기존 `LEARNING_LOG_DIR`/`LEARNING_DATASET_DIR` 값을 그대로 남긴다. Docker 실행은 `docker compose up -d --build`를 사용하며 `./storage:/app/storage` 볼륨이 학습데이터, 런타임 상태, 룰 변경 이력을 유지한다.

---

## 8. 핵심 기능 요약
- 실시간 급등·급락 신호 탐지
- demo 모드 자동 운용 루프
- 설정 저장 후 조건이 충족될 때만 노출되는 트레이딩 서버 시작 버튼
- 자산 기반 자동 비중 계산
- demo 체결 후 가상 현금/코인 잔고와 대시보드 투자금 동기화
- 매수 시 손절가 자동 주입
- 초단기 역방향 모멘텀과 과도한 단기 변동성 진입 차단
- 투자성향별 자동 운용 프로필과 학습 로그 분리
- 업비트 KRW 수수료 0.05% 기준 순엣지 게이트
- 업비트 KRW 마켓 최소 주문 가능 금액 5,000원 미만 주문 차단
- 1회 진입 예상 손절 손실을 `MAX_DAILY_LOSS`의 25% 이내로 자동 제한
- 가격 손절 + 기대 불일치 손절
- 텔레그램 거래/재기동 알림
- 텔레그램 등록 시 06:00~24:00 현재 트레이딩 정기 리포트, 매수/매도/손절 문장형 한국어 알림
- 서버 시작 시 설정/대시보드 접속 주소 텔레그램 알림
- 매일 06:00 전날 트레이딩 결과와 학습 반영 이벤트 리포트
- 현재가, AI 운용 상태, 데모 투자금, 학습 상태를 보여주는 대시보드
- 현재가/투자금/손익은 변경 시 플립시계형 숫자판으로 표시하고, 긴 금액은 카드 폭에 맞춰 자동 축소
- 24시간 수익률 차트의 매수/매도/손절 마커와 마우스 오버 체결 사유·강도 표시
- 24시간 수익률 차트에 실제 업비트 가격 흐름을 주황색 점선으로 중첩 표시하고 가격 범위 라벨 제공
- 장애 자동 복구 및 SAFE_MODE
- 잔고 동기화/오픈오더 정리 일시 실패 시 단계별 자동 재시도
- demo→live 승격 평가
- 항상 켜진 학습 로그 계층
- `/learning/diagnostics` 기반 무거래/차단 사유 진단
- `/learning/model-readiness` 기반 TensorFlow 학습 준비도 진단
- 온체인/ETF 외부 컨텍스트를 HTTP JSON 또는 수동 설정으로 학습 로그와 대시보드에 반영
- ETF 순유입/순유출은 실제 값이 있는 방향만 표시하고, 공개 데이터 캐시는 기본 30초 단위로 갱신
- 룰 개선 분석에 온체인/ETF 상태 분포와 평균 학습 가중치 요약 반영
- 무거래가 지속될 때 demo 기준 완화 후보를 진단하고 제한적으로 완화
- 현재가 카드의 상승장/박스권/하락장 판정을 자동매매 진입 가드에 반영
- 하락장 약한 진입 차단과 하락장·박스권→상승장 전환 확인 후 진입 완화
- `/api/v1/rules/review` 기반 룰 개선 분석 실행
- `/api/v1/rules/proposals` 기반 룰 변경안 생성
- `/api/v1/rules/proposals/{id}/replay` 기반 replay 검증
- replay 검증 후 demo 적용, 승인 후 live 반영

---

## 최근 업데이트

- 설정과 대시보드는 기본 `0.0.0.0:8080`으로 바인딩되어 같은 네트워크의 다른 기기에서 LAN IP 주소로 접속할 수 있다.
- 앱 서버 시작 시에는 텔레그램으로 설정/대시보드 주소와 “아직 자동 트레이딩은 시작되지 않았다”는 안내만 보낸다.
- 설정 화면의 트레이딩 시작 버튼 실행 시에만 텔레그램으로 트레이딩 서버 시작 메시지를 보낸다.
- 트레이딩은 앱 부팅만으로 자동 시작하지 않고, 설정 저장 후 조건을 만족할 때 표시되는 `서버 시작` 버튼으로 시작한다. `live`는 업비트 API 키가 있을 때만, `demo`는 필수값이 저장되어 있을 때만 시작 버튼이 보인다.
- 텔레그램 1시간 리포트와 매수/매도/손절 알림은 영어 key/value 형식이 아니라 한국어 문장으로 발송한다. 매도 알림에는 매수가 대비 손익과 수익률을 포함한다.
- 학습 완료율의 `체결` 숫자는 학습 로그에 누적된 과거 체결 수이고, 대시보드 `최근 체결`은 현재 실행 원장 기준이다. demo 모드는 과거 학습 로그의 테스트성 체결이 투자금에 섞이지 않도록 재기동 시 실행 원장을 자동 복원하지 않는다.
- demo 모드의 가상 현금/코인 잔고는 체결 결과를 반영해 갱신하며, 대시보드 투자금도 초기값이 아니라 현재 가상 포트폴리오 기준으로 표시한다.
- 최근 학습 로그에서 대부분의 신호가 0.18~0.20 점수대에 머물러 `AUTO_MIN_SIGNAL_LEVEL`과 `FEE_ADJUSTED_EDGE_LIMIT`에 막히는 문제가 확인되어, demo no-trade 완화 기준과 수수료 보정 엣지 재평가 경로를 보강했다.
- 24시간 수익률 차트는 수익률선 위에 매수/매도/손절 마커를 표시하며, 마커에 마우스를 올리면 체결 사유와 신호 강도, 점수, 체결가를 확인할 수 있다.
- 같은 차트에 실제 업비트 가격 흐름을 주황색 점선으로 중첩하고, 초기 데이터가 부족한 상태에서도 가격선 또는 현재가 점과 가격 범위 라벨을 표시한다.
- 현재가 카드의 장세 판정은 최근 가격 변화율 `±0.1%` 안쪽만 박스권으로 보고, 그 이상은 상승장/하락장으로 더 민감하게 전환한다. 박스권 범위는 실제 관측 고저가가 너무 좁으면 현재가 기준 최소 `0.1%` 폭으로 보정하며, 데이터가 누적되어 실제 고저폭이 커지면 관측 범위로 갱신된다.
- 현재가 카드 장세는 과거 학습 이벤트가 아니라 현재 가격 로그와 ticker 변화율로만 판단한다. ticker 변화율이 0에 가까운데 가격 로그가 `±0.1%` 이상 움직이면 가격 로그 기준 상승장/하락장을 우선 표시한다.
- 익절 매도는 포지션의 기본 최소 기대 수익률을 그대로 고정 적용하지 않고, 모멘텀/호가 불균형/장세 강도로 목표 수익률을 조정한다. 매도 전에는 왕복 거래수수료와 최소 순수익 기준을 넘는지 확인해 수수료를 제외하면 손해인 익절 매도를 차단한다.
- 최근 학습 로그에서 50% 손절이 극소 잔량까지 반복되는 문제가 확인되어, 5,000원 미만 매도 차단과 dust 잔량 전량청산 보정, 보합권 소프트 손절 보류 룰을 추가했다.
- 최근 실행 원장에서 약신호 매수가 대부분이고 손절 손실이 익절 수익을 초과하면 손익 가드가 켜진다. 이 상태에서는 약신호 추가매수와 낮은 점수의 약신호 신규 진입을 차단하고, 약신호 포지션의 기대 불일치 손절은 반복 부분청산 대신 전량 청산한다.
- 실행 원장이 비어 있어도 최근 학습 로그에서 약신호 손절이 2회 이상 확인되면 같은 손익 가드를 켜서 약신호 신규/추가 매수를 차단한다. 최근 원본 가격 흐름이 하락장이면 현재가 카드가 일시적으로 상승장으로 흔들려도 하락장 진입 가드를 우선 적용한다.
- 익절 후 잔여 포지션이 남으면 손절선을 매수가와 왕복 수수료를 넘는 수준으로 올려, 확보한 수익이 다음 반전에서 다시 큰 손실로 바뀌지 않게 한다.
- 룰 변경은 즉시 반영 버튼이 아니라 `룰 개선 분석 실행 → 룰 변경안 생성 → replay 검증 → demo 적용 → live 승인 적용` 파이프라인으로 처리한다.
- `Codex 자동 룰 개선 시작`은 누적 학습 로그의 마지막 체결 시각, 24시간 무거래 여부, 차단 사유, A/B/C 섀도우 결과를 함께 검토한다. 자동매매 루프도 `AUTO_RULE_UPDATE_NO_TRADE_HOURS` 기본 24시간 동안 체결이 없고 차단 로그가 계속 쌓이면 같은 파이프라인을 자동 시작한다.
- 매매 로직 업데이트가 적용된 자동매매 사이클은 `trade_logic_update_trace`에 로직 버전, 적용 여부, 기존 차단 사유, 룰 variant 리더, 비교할 최적화 지표를 남긴다. 룰 변경 히스토리도 `optimization_tracking`에 변경 전 기준과 다음 리뷰에서 비교할 지표를 보관한다.
- 현재 누적 로그에서는 2026-05-27 23:12:19+09:00 이후 2026-05-30 10:40:15+09:00까지 체결이 없고, 주요 차단은 `WEAK_ENTRY_HISTORICAL_LOSS_BLOCK`, `MARKET_STATE_BEAR_ENTRY_BLOCK`, `SIDEWAYS_WEAK_SCALE_IN_BLOCK`이었다. 단, A/B/C 섀도우에서 상승장 룰 B가 장기간 우세하므로 demo 상승장, 룰 B 우세, 약신호 점수 0.24 이상, 수수료 엣지 재평가 조건이 모두 맞을 때만 회복 진입을 허용한다.
- 현재까지 누적된 학습 로그/매매 데이터를 분석해 가격 카드 장세 판정을 매매 로직에 도입했다. 최근 체결은 하락장 진입 비중이 높고 A/B/C 섀도우에서는 방어형 C가 손실을 가장 작게 유지했기 때문에, 하락장 약한 진입은 차단하고 하락장·박스권에서 상승장으로 2틱 이상 확인된 전환만 제한적으로 진입 완화에 사용한다.
- 트레이딩 운영시간은 로컬 런타임 상태로 누적 저장되어 서버 재시작 후에도 이어진다. 설정 화면에서 데모 트레이딩 데이터 리셋 또는 완전 데이터 삭제를 실행할 때만 운영시간도 함께 초기화된다.
- 하락장으로 판단되면 보유 포지션의 추가매수는 신호 강도와 무관하게 차단한다. 충분히 넓은 박스권에서는 하단 구간 매수와 상단 구간 일반 매도를 허용해 박스권 왕복 수익을 노린다.
- 코인거래소 시뮬레이션의 운용상태, 차단 사유, A/B/C 최근 액션은 내부 코드값 대신 한국어 라벨로 표시한다.
- 대시보드의 현재가/투자금/손익은 숫자 자릿수별 플립 애니메이션으로 갱신한다. 투자금처럼 금액이 길어지는 항목은 컨테이너 폭을 측정해 폰트 크기를 자동 조정하고 `KRW` 단위가 숫자와 겹치지 않도록 축소 표시한다.
- ETF 상태는 `순유입 +금액`과 `순유출 0 USD`를 동시에 표시하지 않고, 실제 값이 있는 순유입 또는 순유출 방향만 표시한다. Coinglass 응답에 `change=0`과 `outFlowUsd`가 함께 들어오는 경우에도 순유출로 해석한다.
- 로컬 런타임 로그, 학습 로그, 매매 원장, reset archive, 데이터셋은 `logs/`, `storage/`, `data/` 아래에 두며 Git 추적 대상에서 제외한다.

### ML 선택 의존성
TensorFlow 기반 모델 학습은 기본 서버 의존성에 포함하지 않고 선택 의존성으로 분리한다.

```bash
pip install -e ".[ml]"
```

`ml` extra에는 `tensorflow`, `scikit-learn`, `pandas`, `pyarrow`를 포함한다. 실시간 서버에서 바로 학습하지 않고, 충분한 demo 학습 로그가 쌓인 뒤 오프라인 학습 파이프라인으로 구현한다.

오프라인 학습 CLI는 먼저 학습 로그 표본, train/validation/test 기간 분리, baseline 대비 성능을 검사한다. 통과해도 결과는 `model-training-report.json`과 `shadow-predictions.jsonl`로만 저장되며 live 룰이나 주문 게이트를 직접 바꾸지 않는다.

```bash
upbit-train-model --log-dir ./storage/logs/learning/scalping --report-dir ./storage/data/learning/model-reports
```

---

## 9. 대시보드 표시 요구사항

### 상단 지표 카드
- 실행 모드
- 현재 가격
- 가격 변동률
- 현재 시장 상태 `상승장`, `하락장`, `박스권`
- 박스권 상단/하단 가격 range
- 데모 투자금 또는 실계좌 사용 가능 현금
- 학습 완료율
- 수익 성공률
- 실현/미실현 손익

현재 가격 카드는 다음 형식을 사용한다.

```text
XRP-KRW
2,085 KRW
(+1%)
거래량 UP(15)
```

색상 규칙:
- `+` 가격 변동률과 `UP(n)`은 빨강
- `-` 가격 변동률과 `DOWN(n)`은 파랑
- `FLAT(n)`은 흰색

### AI 운용 모드
- AI 상태
- 자동매매 상태
- 리스크 등급
- 마지막 분석 시각
- 상태 설명 표 접기/펼치기

### 차트 상단
- 파란색 매수 마커 + 툴팁
- 빨간색 일반 매도 마커 + 툴팁
- 노란색 손절 매도 마커 + 툴팁
- 손절가 라인

### 하단 패널
- 보유 코인 수량
- 보유 현금
- 누적 실현손익
- 평가손익
- 매수 횟수
- 매도 횟수
- 손절 횟수
- 최근 손절 사유
- 현재 모드
- LEARNING ON
- 최근 재기동 시각
- 승격 가능 여부

### 룰 개선 패널
- `룰 개선 분석 실행`
- `룰 변경안 생성`
- `replay 검증`
- `demo 적용`
- `live 승인 적용`
- `커밋 해시 연결`
- `히스토리 보정`
- `룰 변경 롤백`

버튼 결과에는 분석 대상 기간, 거래 수, 손절 수, 가격/거래량 데이터 품질, 주요 손실 원인, 온체인/ETF 외부 컨텍스트 요약, Codex 제안 변경 항목, replay 수익률/낙폭 결과, 승인 필요 여부, 변경 히스토리 기록 여부를 표시한다.

룰 변경 이력은 코인/투자성향별 `rule-change-history.jsonl`에 append-only로 보관한다. 각 이력에는 기존 룰, 새 룰, 변경 사유, 기대 효과, 알려진 리스크, replay/demo/live 결과, 승인자, 한국어 커밋 메시지와 commit hash를 남긴다. 이 히스토리는 왜 현재 매매룰이 되었는지 추적하고 반복 실수를 줄이기 위한 전략 지식 원장이다.

손절 파라미터(`STOP_LOSS_*`, `stop_loss_pct`, `stop_loss_price`, `fixed_stop_loss_pct`)는 룰 개선 제안에서 잠금 처리한다. 손절 관련 문제가 발견되더라도 손절률 자체가 아니라 진입 조건, 사이징, 재진입 차단, 기대 검증 기준만 개선 대상으로 삼는다.

### 횡보장 리스크 가드
자동매매 루프는 주문 실행 직전에 가격 범위, 거래대금 범위, 평균 절대 가격 변화율을 함께 확인해 가격과 거래량이 모두 정체된 횡보장을 감지한다.

- `NO_TRADE_RELAX_AFTER_CYCLES` 이후 약한 신호가 완화되더라도 횡보장에서는 신규 매수를 차단한다.
- 포지션 보유 중 횡보장으로 판단되면 기존 진입가 대비 `SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT` 이상 할인된 가격이 아니면 추가매수를 차단한다.
- 차단 사유는 `SIDEWAYS_WEAK_RELAXED_ENTRY_BLOCK`, `SIDEWAYS_SCALE_IN_PRICE_UNCHANGED`로 남기고, 횡보 판단 지표를 학습 로그와 마지막 자동매매 사이클에 기록한다.

---

## 10. 학습 로그 정책
이 프로젝트는 실행 모드와 무관하게 항상 학습 로그를 저장한다.
기본 XRP는 `storage/logs/learning/<투자성향>/learning.jsonl`, 다른 코인은 `storage/logs/learning/<COIN>/<투자성향>/learning.jsonl`을 사용해 코인별 룰 개선 데이터가 섞이지 않게 한다.

### 저장 대상
- 시세 feature
- 가격/거래대금 원시 관측값(`market-observations.jsonl`)
- signal score
- sizing decision
- order intent
- fill result
- stop loss trigger
- market_state, 박스권 range, 재진입 차단 사유, 분할 매도 비율
- restart / recovery
- promotion evaluation

### 활용
1. 룰 개선 분석 데이터
2. replay 검증 데이터. `market-observations.jsonl` 표본이 충분하면 고정 fixture보다 실제 관측 데이터를 우선 사용하고, signal 통과 여부뿐 아니라 최종 수익률과 최대 낙폭도 함께 검증한다.
3. demo→live 승격 평가 데이터
4. 전략 회귀 검증과 feature 개선
5. 룰 변경 히스토리와 변경 근거 보존
6. 향후 모델 학습 데이터셋 생성

---

## 11. TDD + Git 커밋 규칙

### 개발 절차
1. 실패 테스트 작성
2. 최소 구현
3. 리팩터링
4. 통합/계약 테스트
5. 문서 업데이트
6. Git 커밋

### Git 보조 설정
```bash
git config commit.template .gitmessage.ko.txt
pre-commit install
```

- 커밋 메시지는 반드시 한국어로 작성
- 커밋 전에 `pytest -q`와 `pre-commit run --all-files` 통과 확인
- 룰 변경도 실패 테스트 먼저 작성
- replay 테스트 없는 룰 변경 금지
- 변경안 생성 후 한국어 커밋
- 커밋 후 `upbit-link-rule-commit --proposal-id <id> --learning-log-dir <룰 로그 경로>`로 현재 Git 커밋 해시를 룰 변경 히스토리에 연결
- main 직접 반영 금지, 브랜치 기반 검토 필수
- demo 검증과 승인 없는 live 반영 금지

### 커밋 규칙
- 모든 커밋 메시지는 **반드시 한국어**
- 구현 단위별 커밋
- 테스트 없는 커밋 금지
- 문서 변경과 계약 변경은 함께 커밋

### 커밋 예시
```bash
git add .
git commit -m "손절가 주입 로직과 매수 알림 테스트 추가"
```

```bash
git add .
git commit -m "재기동 복구 오케스트레이터와 SAFE_MODE 전환 구현"
```

---

## 12. 품질 기준
- 테스트 커버리지 80% 이상
- 핵심 거래/손절 경로 커버리지 95% 목표
- `demo`에서 실주문 0건
- 손절 주입 성공률 100%
- 텔레그램 알림 성공률 99% 이상
- 재기동 후 복구 성공률 99% 이상

---

## 13. 운영 체크리스트
- [ ] `.env` 누락 없이 설정
- [ ] `TRADING_MODE=demo`로 시작
- [ ] 텔레그램 봇 테스트
- [ ] 잔고 sync 정상 확인
- [ ] 대시보드 마커 표시 확인
- [ ] 손절 라인 표시 확인
- [ ] 재기동 알림 테스트
- [ ] 승격 평가기 기준 확인
- [ ] `live` 전환 전 승인 절차 완료

---

## 14. 관련 문서
- `PRD.md`
- `Tasklist.md`
- `RUNBOOK.md`
- `STRATEGY_SPEC.md`
- `ENV_SPEC.md`
- `CODEX_HARNESS.md`
