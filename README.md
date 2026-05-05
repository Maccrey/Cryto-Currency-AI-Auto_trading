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

설정 화면에서 투자성향을 단타, 단기, 중기, 장기 중 선택할 수 있다. 현재가는 선택한 성향의 주기로 관찰하고, 업비트 KRW 마켓 수수료 0.05%의 왕복 비용과 성향별 최소 순엣지를 넘지 못하는 진입은 차단한다. 학습 로그도 성향별 디렉터리에 분리 저장한다.

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
- `TRADE_MARKET=KRW-XRP`
- `TRADE_COIN=XRP`
- `DEMO_INITIAL_CAPITAL=1000000`
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DASHBOARD_HOST=0.0.0.0`
- `DASHBOARD_PORT=8080`

자세한 스펙은 `ENV_SPEC.md`를 따른다.

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
- 장애 자동 복구 및 SAFE_MODE
- 잔고 동기화/오픈오더 정리 일시 실패 시 단계별 자동 재시도
- demo→live 승격 평가
- 항상 켜진 학습 로그 계층
- `/learning/diagnostics` 기반 무거래/차단 사유 진단
- `/learning/model-readiness` 기반 TensorFlow 학습 준비도 진단
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
- 최근 학습 로그에서 대부분의 신호가 0.18~0.20 점수대에 머물러 `AUTO_MIN_SIGNAL_LEVEL`과 `FEE_ADJUSTED_EDGE_LIMIT`에 막히는 문제가 확인되어, 단타 medium 진입 기준과 수수료 보정 엣지 버퍼를 완화했다.
- 최근 학습 로그에서 50% 손절이 극소 잔량까지 반복되는 문제가 확인되어, 5,000원 미만 매도 차단과 dust 잔량 전량청산 보정, 보합권 소프트 손절 보류 룰을 추가했다.
- 룰 변경은 즉시 반영 버튼이 아니라 `룰 개선 분석 실행 → 룰 변경안 생성 → replay 검증 → demo 적용 → live 승인 적용` 파이프라인으로 처리한다.

### ML 선택 의존성
TensorFlow 기반 모델 학습은 기본 서버 의존성에 포함하지 않고 선택 의존성으로 분리한다.

```bash
pip install -e ".[ml]"
```

`ml` extra에는 `tensorflow`, `scikit-learn`, `pandas`, `pyarrow`를 포함한다. 실시간 서버에서 바로 학습하지 않고, 충분한 demo 학습 로그가 쌓인 뒤 오프라인 학습 파이프라인으로 구현한다.

오프라인 학습 CLI는 먼저 학습 로그 표본, train/validation/test 기간 분리, baseline 대비 성능을 검사한다. 통과해도 결과는 `model-training-report.json`과 `shadow-predictions.jsonl`로만 저장되며 live 룰이나 주문 게이트를 직접 바꾸지 않는다.

```bash
upbit-train-model --log-dir ./logs/learning/scalping --report-dir ./data/learning/model-reports
```

---

## 9. 대시보드 표시 요구사항

### 상단 지표 카드
- 실행 모드
- 현재 가격
- 가격 변동률
- 연속 가격 추세 `UP(n)`, `DOWN(n)`, `FLAT(n)`
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

버튼 결과에는 분석 대상 기간, 거래 수, 손절 수, 주요 손실 원인, Codex 제안 변경 항목, replay 결과, 승인 필요 여부를 표시한다.

---

## 10. 학습 로그 정책
이 프로젝트는 실행 모드와 무관하게 항상 학습 로그를 저장한다.

### 저장 대상
- 시세 feature
- signal score
- sizing decision
- order intent
- fill result
- stop loss trigger
- restart / recovery
- promotion evaluation

### 활용
1. 룰 개선 분석 데이터
2. replay 검증 데이터
3. demo→live 승격 평가 데이터
4. 전략 회귀 검증과 feature 개선
5. 향후 모델 학습 데이터셋 생성

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
