# PRD.md

## 1. 제품 개요

### 1.1 제품명
**Upbit Momentum Auto Trader**

### 1.2 문제 정의
업비트에서 급등·급락 구간을 수동으로 대응하면 반응 지연, 감정 개입, 규칙 일탈, 복수 종목 동시 감시 한계가 발생한다.  
또한 자동매매를 구현하더라도 다음 요소가 빠지면 실전 운영이 어렵다.

- 현재 보유 코인 수량과 현금 잔고를 반영한 비중 계산
- 매수 시점 손절가 자동 주입
- 기대 불일치 시 손절
- 재기동 후 상태 복구
- 텔레그램 체결/장애 알림
- 차트와 운영 지표 시각화
- 데모 운영 후 실거래 승격
- 모든 모드에서 지속 학습 로그 축적

### 1.3 목표
본 시스템은 업비트의 실시간 시세를 감시해 급등·급락 신호를 포착하고, 현재 보유 자산을 기준으로 자동 비중을 계산하여 `demo` 또는 `live` 모드로 거래를 수행한다.  
모든 실행 모드에서 학습 로그를 항상 축적한다. 초기 개선 방향은 TensorFlow 직접 학습이 아니라, 학습 로그를 Codex가 분석해 룰 변경안을 만들고 replay와 demo 검증 후 승인받아 live에 반영하는 구조다.

자동화 성향은 설정 화면에서 단타, 단기, 중기, 장기 중 선택한다. 거래 횟수를 늘리는 것이 목적이 아니라 선택한 성향에 맞는 관찰 주기, 히스토리 길이, 최소 순엣지, 기대 검증 시간을 주입하고, 업비트 KRW 마켓 거래 수수료 0.05%와 추가 순엣지를 넘는 신호만 실행하는 것을 목표로 한다.

### 1.4 타깃 사용자
- Python 기반 개발 및 운영이 가능한 개인 트레이더
- 업비트 KRW 마켓 중심 자동매매 운영자
- 데모 검증 후 실거래 전환을 원하는 사용자
- 거래/장애/학습 상태를 GUI와 텔레그램으로 동시에 확인하고 싶은 사용자

### 1.5 핵심 가치 제안
- **자산 기반 자동 비중 계산**
- **손절 내장 포지션 관리**
- **장애 자동 복구와 재기동 알림**
- **데모 선행 후 실거래 승격**
- **실행 모드와 무관한 지속 학습**
- **차트 중심 운영 가시성**

---

## 2. 제품 운영 원칙

### 2.1 실행 모드
허용 모드는 아래 두 가지뿐이다.

- `demo`
- `live`

### 2.2 학습 계층
학습은 실행 모드가 아니라 **항상 켜진 공통 계층**이다.

- `demo`에서도 구조화 로그 저장
- `live`에서도 구조화 로그 저장
- 의사결정, 손절, 체결, 재기동, 승격 평가를 모두 기록
- 이 로그를 룰 개선 분석, replay 검증, 승격 평가, 향후 모델 학습에 활용
- TensorFlow 등 ML 모델 학습은 기본 런타임이 아니라 오프라인 학습 파이프라인으로 분리
- 모델 학습 전 `/learning/model-readiness` 기준을 통과해야 함

### 2.3 초기 운영 정책
초기에는 `demo` 모드로 일정 기간 운영한다.

- 최소 운영 기간 충족
- 최소 거래 수 충족
- 손절 정상 작동
- 재기동 복구 성공
- 승률, Profit Factor, Max Drawdown 기준 충족

이후 운영자 승인 또는 자동 정책에 따라 `live` 모드로 전환한다.

### 2.4 ML 모델 도입 원칙
- 기본 자동매매 서버는 규칙 기반 안전장치를 유지한다.
- TensorFlow 모델은 선택 의존성 `ml`로만 설치한다.
- 모델 학습은 demo/learning 로그를 이용한 오프라인 배치로 수행한다.
- 학습된 모델은 먼저 shadow mode에서 규칙 기반 판단과 비교한다.
- live 주문 최종 게이트는 손절/사이징/SAFE_MODE/HARD_STOP 규칙이 우선한다.

### 2.5 룰 개선 원칙
- 룰 변경은 자동 반영하지 않는다.
- 분석, 변경안 생성, replay 테스트, demo 반영, 승인, live 반영 순서를 고정한다.
- live 운영 중 룰 변경은 즉시 반영하지 않고 demo 재검증을 거친다.
- 변경 후 demo→live 승격 평가를 다시 실행한다.

---

## 3. 핵심 기능

## 3.1 급등·급락 신호 탐지
### 문제
단순 등락률 기반 탐지는 노이즈가 많고, 유동성 부족 구간에서 오탐이 발생할 수 있다.

### 해결
실시간 시세 스트림을 기준으로 아래 지표를 계산한다.

- 1초/5초/30초 수익률
- 체결량 증가율
- 거래대금 증가율
- spread
- orderbook imbalance
- 단기 변동성
- 국면 점수(regime score)

### 출력
- `weak`
- `medium`
- `strong`
- `very_strong`

신호와 함께 signal score, reason code, feature snapshot을 저장한다.

### 안정성 차단 조건
강한 상승 신호가 일부 존재하더라도 아래 조건에서는 실수 진입을 줄이기 위해 신호를 차단한다.

- 저유동성 구간
- 1초 수익률이 급격히 음수로 돌아선 초단기 역방향 모멘텀
- 단기 변동성이 과도하게 확대된 구간

---

## 3.2 자산 기반 비중 계산
### 문제
신호가 같아도 보유 현금과 코인 수량이 다르면 동일한 매수/매도 비율을 쓰면 안 된다.

### 해결
시스템 시작 시 현재 보유 코인 수량과 현금 잔고를 동기화하고, 신호 세기와 국면 점수를 기준으로 비중을 계산한다.

### 입력
- 현금 잔고
- 보유 코인 수량
- 평균 매수가
- 현재가
- 신호 세기
- regime
- 유동성 점수
- spread / 슬리피지 추정
- 일일 손실 상태
- cooldown 상태

### 출력
- 매수 금액
- 매수 수량
- 매수 비율
- 매도 금액
- 매도 수량
- 매도 비율
- 손절가
- 주문 허용 여부
- 차단 사유

### 비중 계산 예시
- weak: buy 8%, sell 12%
- medium: buy 18%, sell 28%
- strong: buy 35%, sell 45%
- very_strong: buy 55%, sell 70%

단, 아래 조건이면 자동 축소 또는 차단한다.
- spread 과다
- 슬리피지 추정 초과
- 현재가 비정상
- 저유동성
- 연속 손실
- 일일 손실 한도 근접
- 예상 손절 손실이 1회 리스크 예산을 초과
- 재진입 금지 시간 내
- 재기동 직후 SAFE_MODE
- 단타 예상 엣지가 왕복 수수료와 최소 순엣지를 넘지 못함

기본 앱 구성에서는 1회 진입의 예상 손절 손실을 `MAX_DAILY_LOSS`의 25% 이내로 제한한다. 신호가 강해도 손절선 기준 손실 예산을 넘으면 매수 금액을 자동 축소한다.

### 투자성향 프로필과 수수료 게이트
업비트 고객센터 기준 거래 수수료는 체결금액에 마켓별 수수료율을 곱해 계산한다. KRW 마켓 자동주문은 일반 KRW 마켓 수수료와 동일한 0.05%를 기준으로 한다.

프로필:

| 값 | 표시 | 성향 |
|---|---|---|
| `scalping` | 단타 | 가장 빠른 관찰과 낮은 순엣지 기준 |
| `short_term` | 단기 | 수분 단위 흐름 확인 후 진입 |
| `mid_term` | 중기 | 추세 지속성과 리스크 여유를 더 크게 반영 |
| `long_term` | 장기 | 가장 느리게 관찰하고 높은 기대값만 진입 |

진입 조건:
- 예상 엣지 > 왕복 수수료 `TRADING_FEE_RATE * 2` + 투자성향별 `PROFILE_MIN_NET_EDGE_PCT`
- 단타 기본값 기준 최소 요구 엣지: 0.10% + 0.08% = 0.18%
- 업비트 공식 KRW 마켓 최소 주문 가능 금액 `5,000 KRW` 미만 주문 차단
- 조건 미충족 시 `FEE_ADJUSTED_EDGE_LIMIT`으로 차단하고 학습 로그에 남긴다.
- 학습 로그는 `logs/learning/<TRADING_PROFILE>/learning.jsonl`에 분리 저장한다.
- 성향을 변경하면 새 성향 로그를 기준으로 모델 준비도와 진단을 다시 쌓아, 이후 오프라인 학습이 성향별로 분리되도록 한다.

---

## 3.3 손절 내장 포지션 관리
### 문제
매수 이후 가격이 예상대로 가지 않으면 손실이 커질 수 있다.

### 해결
매수 체결 시 포지션에 손절가를 반드시 주입한다.

### 손절 종류
#### A. 하드 손절
현재가가 `stop_loss_price` 이하가 되면 즉시 손절 매도

#### B. 소프트 손절
매수 후 일정 시간 내 기대한 상승이 나오지 않으면 손절 또는 축소 청산

최근 학습 데이터에서 반복적인 50% 축소 청산이 극소 잔량을 만들고 손절 이벤트를 과도하게 늘리는 문제가 확인되었으므로, 보합권에서는 수수료를 감안해 소프트 손절을 보류한다. 또한 5,000원 미만 매도 주문은 실행하지 않고, 부분 청산 후 남는 잔량 평가액이 5,000원 미만이면 부분 청산 대신 전량 청산한다.

판정 예:
- validation window 내 최소 기대 수익률 미달
- momentum 약화
- imbalance 역전
- 거래량 급감

### 저장 필드
- entry_price
- stop_loss_price
- stop_loss_pct
- validation_window_sec
- min_expected_return_pct
- stop_loss_reason

---

## 3.4 텔레그램 알림
### 전송 대상 이벤트
- 매수 체결
- 일반 매도 체결
- 손절 매도 체결
- 재기동 완료
- 승격 가능 상태
- 실거래 활성화
- 06:00~24:00 현재 트레이딩 정기 리포트
- 06:00 전날 트레이딩 결과 및 학습 반영 리포트
- 치명적 오류

### 매수 알림 포함 정보
- 거래 코인
- 신호 세기
- 매수 금액
- 매수 수량
- 매수 비율
- 체결가
- 손절가
- 시간

### 일반 매도 알림 포함 정보
- 거래 코인
- 매도 금액
- 매도 수량
- 매도 비율
- 체결가
- 수수료
- 실현손익
- 시간

### 손절 알림 포함 정보
- 거래 코인
- 손절 사유
- 손해 금액
- 체결가
- 손절 기준가
- 시간

### 정기 트레이딩 리포트 포함 정보
- 현재가
- 보유 현금
- 보유 코인 수량
- 실현손익
- 매수/매도/손절 횟수
- 활성 포지션
- SAFE_MODE / HARD_STOP / trading_ready 상태
- 최근 학습 이벤트

### 전날 트레이딩 결과 리포트 포함 정보
- 대상 일자
- 매매판단신호 수
- 차단 신호 수
- 체결 수
- 포지션 진입/청산 수
- 승격 검토 수
- 재기동/복구 이벤트 수
- 학습 반영 이벤트 범주

### 재기동 알림 포함 정보
- 서비스명
- 재기동 시각
- 원인
- 종료 코드
- 포트폴리오 sync 결과
- SAFE_MODE 상태
- 보유 현금
- 보유 코인 수량

---

## 3.5 GUI 대시보드
### 차트 상단
- 가격 차트
- 파란색 매수 마커 + 툴팁
- 빨간색 일반 매도 마커 + 툴팁
- 노란색 손절 매도 마커 + 툴팁
- 활성 포지션 손절 라인

### 하단 요약 패널
- 현재 보유 코인 수량
- 보유 현금
- 누적 실현손익
- 평가손익
- 매수 횟수
- 매도 횟수
- 손절 횟수
- 최근 손절 사유
- 현재 실행 모드
- LEARNING ON 상태
- 최근 재기동 시각
- 승격 가능 여부

---

## 3.6 장애 자동 복구
### 문제
자동매매 프로세스가 중단되면 대응 지연이 치명적일 수 있다.

### 해결
프로세스 관리자를 통해 자동 재기동하고, 복구 절차를 강제한다. 잔고 동기화나 오픈오더 정리처럼 네트워크 영향을 받는 단계는 일시 장애로 판단될 수 있으므로 단계별 자동 재시도를 수행한다. 모든 재시도 후에도 실패하면 `SAFE_MODE`를 유지하고 거래를 차단한다.

---

## 3.7 룰 개선 파이프라인

### 문제
학습 로그를 바로 모델 학습에 넣으면 표본 부족, 과최적화, live 안전성 문제가 생길 수 있다.

### 해결
Codex가 최근 학습 로그를 읽어 손실 원인과 차단 원인을 분석하고, 제한된 수의 룰 변경안을 생성한다. 변경안은 replay 테스트를 통과한 뒤 demo에만 먼저 반영한다. live 반영은 demo 지표 재검증과 운영자 승인이 있어야 가능하다.

### 설정 화면 UI
- `룰 개선 분석 실행`
- `룰 변경안 생성`
- `demo 적용`
- `live 승인 적용`

### 결과 표시
- 분석 대상 기간
- 거래 수
- 손절 수
- 주요 손실 원인
- Codex 제안 변경 항목
- replay 결과
- 승인 필요 여부

### API
- `POST /api/v1/rules/review`
- `POST /api/v1/rules/proposals`
- `POST /api/v1/rules/proposals/{id}/apply-demo`
- `POST /api/v1/rules/proposals/{id}/approve-live`
- `GET /api/v1/rules/proposals/{id}`

### 재기동 순서
1. restart event 기록
2. .env / secret 로드
3. 텔레그램 재기동 알림 준비
4. 잔고 및 보유 코인 sync 자동 재시도
5. 오픈오더 reconcile 자동 재시도
6. 손절 상태 복원
7. SAFE_MODE 진입
8. 상태 정상 확인 후 운영 재개

### 자동 복구 원칙
- 각 복구 단계는 기본 3회까지 재시도한다.
- 재시도 실패와 복구 성공은 `recovery_attempt` 학습 이벤트로 기록한다.
- 일시 장애가 복구되면 `trading_ready=True`로 정상 기동한다.
- 모든 재시도 실패 시 `failure_stage`를 기록하고 `SAFE_MODE`로 주문을 차단한다.

---

## 3.7 데모 → 실거래 승격
### 목적
실거래 전 데모 운영으로 전략과 운영 안정성을 검증한다.

### 승격 기준 예시
- 데모 운영 14일 이상
- 누적 거래 100회 이상
- 승률 52% 이상
- Profit Factor 1.20 이상
- Max Drawdown 8% 이하
- 손절 오작동 0건
- 재기동 복구 성공률 99% 이상
- 텔레그램 알림 성공률 99% 이상

### 결과 상태
- `NOT_READY`
- `READY_FOR_REVIEW`
- `APPROVED`
- `REJECTED`

---

## 4. 유저 스토리

### 스토리 1: 시작 시 자산 동기화
**역할:** 운영자  
**목표:** 시스템이 시작될 때 실제 보유 상태를 정확히 반영하고 싶다.

```gherkin
Feature: 초기 자산 동기화
  Scenario: 시스템 시작 시 잔고 조회
    Given 시스템이 시작되었고
    When 업비트 잔고와 보유 코인 수량을 조회하면
    Then 내부 portfolio_state를 최신 값으로 초기화한다
    And 이후 비중 계산의 기준값으로 사용한다
```

### 스토리 2: 손절 내장 매수
**역할:** 운영자  
**목표:** 매수 체결과 동시에 손절 기준이 저장되길 원한다.

```gherkin
Feature: 손절 주입
  Scenario: 매수 체결 시 손절가 저장
    Given 매수 주문이 체결되었고
    When 포지션을 생성하면
    Then entry_price와 stop_loss_price를 함께 저장한다
    And 매수 알림에 손절가가 포함된다
```

### 스토리 3: 기대 불일치 손절
**역할:** 운영자  
**목표:** 매수 후 예상대로 오르지 않으면 자동으로 손절되길 원한다.

```gherkin
Feature: 기대 불일치 손절
  Scenario: 상승 실패 시 손절
    Given 매수 후 validation window가 지났고
    And 최소 기대 상승률에 도달하지 못했을 때
    When 포스트 엔트리 검증이 실행되면
    Then 손절 또는 축소 청산을 수행한다
    And 손절 사유를 기록한다
```

### 스토리 4: 재기동 알림
**역할:** 운영자  
**목표:** 장애로 재기동되어도 텔레그램으로 즉시 알림을 받고 싶다.

```gherkin
Feature: 재기동 운영 알림
  Scenario: 자동 복구 후 텔레그램 전송
    Given 프로세스가 비정상 종료되었고
    When 자동 재기동과 상태 복구가 완료되면
    Then 텔레그램으로 재기동 정보와 복구 결과를 전송한다
```

### 스토리 5: 데모 선행 후 실거래
**역할:** 운영자  
**목표:** 충분히 검증된 뒤에만 실제 거래를 시작하고 싶다.

```gherkin
Feature: 데모 승격 평가
  Scenario: 실거래 승격 조건 충족
    Given 데모 운영 결과가 누적되어 있고
    When 승격 평가기를 실행하면
    Then 최소 기간, 거래 수, PF, MDD, 손절 정상 여부를 평가한다
    And 조건 충족 시 READY_FOR_REVIEW 상태로 기록한다
```

---

## 5. 성공 지표

| 지표 | 목표 | 기간 | 이벤트·메트릭 | 계산식 |
|---|---:|---|---|---|
| 초기 자산 동기화 성공률 | ≥ 99% | 상시 | portfolio_sync_success / portfolio_sync_attempt | success / attempt |
| 신호 생성 성공률 | ≥ 99% | 상시 | signal_generated / signal_eval_attempt | signal_generated / signal_eval_attempt |
| 비중 계산 성공률 | ≥ 99.5% | 상시 | sizing_success / sizing_attempt | sizing_success / sizing_attempt |
| 손절 주입 성공률 | = 100% | 상시 | stoploss_injected / buy_fill_total | stoploss_injected / buy_fill_total |
| 손절 실행 성공률 | ≥ 99% | 상시 | stoploss_exec_success / stoploss_trigger_total | success / trigger |
| 재기동 후 복구 성공률 | ≥ 99% | 상시 | recovery_success / restart_total | recovery_success / restart_total |
| 재기동 텔레그램 알림 성공률 | ≥ 99% | 상시 | restart_telegram_success / restart_total | success / total |
| 신호→주문→알림 p95 | ≤ 2.5s | 상시 | signal_to_notification_ms | p95(signal_to_notification_ms) |
| GUI 반영 지연 p95 | ≤ 1s | 상시 | dashboard_render_lag_ms | p95(dashboard_render_lag_ms) |
| 데모 Profit Factor | ≥ 1.20 | 승격 평가 시 | gross_profit / gross_loss | gross_profit / gross_loss |
| 데모 Max Drawdown | ≤ 8% | 승격 평가 시 | equity_curve | max_drawdown(equity_curve) |
| 텔레그램 체결 알림 성공률 | ≥ 99% | 상시 | telegram_send_success / telegram_send_attempt | success / attempt |

---

## 6. 비기능 요구사항

### 성능
- WebSocket 기반 저지연 시세 처리
- 시그널 평가 p95 150ms 이하
- 주문 경로 p95 400ms 이하
- 대시보드 반영 p95 1초 이하

### 안정성
- 자동 재기동
- SAFE_MODE
- HARD_STOP
- 오픈오더 reconcile
- 손절 상태 복원

### 보안
- API 키/토큰 하드코딩 금지
- `.env` 또는 Secret Manager 사용
- 대시보드에 민감값 노출 금지

### 운영성
- 텔레그램 알림
- 구조화 로그
- 일별 데이터셋 생성
- 재기동 이력 및 승격 이력 추적

---

## 7. 데이터 모델

### 핵심 엔티티
- users
- api_credentials
- markets
- market_snapshots
- strategies
- trading_signals
- orders
- order_fills
- positions
- portfolio_state
- risk_events
- telegram_notifications
- service_restarts
- regime_snapshots
- learning_runs
- decision_logs
- promotion_evaluations
- audit_logs

### 텍스트 ERD
```text
users
  └─< api_credentials
  └─< strategies
        └─< trading_signals
              └─< orders
                    └─< order_fills
        └─< positions
        └─< risk_events
        └─< promotion_evaluations

markets
  └─< market_snapshots
  └─< regime_snapshots

portfolio_state
service_restarts
telegram_notifications
learning_runs
  └─< decision_logs
audit_logs
```

### positions 핵심 필드
| 필드 | Python | 저장타입 | 제약 | 인덱스 | 설명 |
|---|---|---|---|---|---|
| id | UUID | UUID | PK | PK(id) | 포지션 ID |
| strategy_id | UUID | UUID | FK, NOT NULL | idx_positions_strategy_market | 전략 |
| market | str | TEXT | NOT NULL | idx_positions_strategy_market | 마켓 |
| qty | Decimal | NUMERIC(24,8) | NOT NULL |  | 수량 |
| avg_entry_price | Decimal | NUMERIC(24,8) | NOT NULL |  | 평균 진입가 |
| entry_price | Decimal | NUMERIC(24,8) | NOT NULL |  | 최근 진입가 |
| stop_loss_price | Decimal | NUMERIC(24,8) | NOT NULL | idx_positions_stop_loss_price | 손절가 |
| stop_loss_pct | Decimal | NUMERIC(8,4) | NOT NULL |  | 손절 비율 |
| validation_window_sec | int | INTEGER | NOT NULL |  | 기대 검증 시간 |
| min_expected_return_pct | Decimal | NUMERIC(8,4) | NOT NULL |  | 최소 기대 수익률 |
| stop_loss_reason | str \| None | TEXT | NULL | idx_positions_stop_loss_reason | 손절 사유 |
| trailing_stop_enabled | bool | BOOLEAN | NOT NULL, DEFAULT false |  | 트레일링 여부 |
| realized_pnl | Decimal | NUMERIC(24,8) | NOT NULL, DEFAULT 0 |  | 실현손익 |
| unrealized_pnl | Decimal | NUMERIC(24,8) | NOT NULL, DEFAULT 0 |  | 평가손익 |
| updated_at | datetime | TIMESTAMPTZ | NOT NULL | idx_positions_updated_at | 갱신 시각 |

예시:
```python
{
  "market": "KRW-XRP",
  "qty": "820.50",
  "entry_price": "600.60",
  "stop_loss_price": "589.79",
  "stop_loss_pct": "0.0180",
  "validation_window_sec": 180,
  "min_expected_return_pct": "0.0040"
}
```

---

## 8. 저장소 선택 이유
- **Postgres**: 주문, 체결, 포지션, 승격 이력 등 트랜잭션·조인·리포팅이 중요
- **Redis**: 최근 tick 윈도우, cooldown, dedupe, SAFE_MODE 상태, rate limiter
- **JSONL/Parquet 파일 저장소**: 학습 로그 및 데이터셋 축적
- 선택 사유:
  - Postgres는 정합성과 이력 추적에 적합
  - Redis는 짧은 TTL과 고속 상태 관리에 적합
  - JSONL/Parquet는 학습 파이프라인과 분석에 적합

### 캐시 전략
- `ticks:{market}` TTL 120s
- `signal_cooldown:{market}` TTL 60s~600s
- `reentry_block:{market}` TTL 설정값 기반
- `kill_switch:{strategy_id}` 명시 해제까지 유지

---

## 9. 마이그레이션 / 버전 전략
- Alembic 사용
- 원칙:
  1. 신규 컬럼 추가는 기본적으로 nullable 또는 default로 도입
  2. 애플리케이션 배포 후 backfill
  3. 마지막에 constraint 강화
- 이벤트 로그는 `schema_version` 포함

---

## 10. 런칭 플랜

### MVP
- 업비트 시세 수집
- demo 실행기
- 신호 생성
- 자산 기반 비중 계산
- 손절 주입
- 텔레그램 알림
- 대시보드 기본 화면

### MLP
- 재기동 자동 복구
- 승격 평가기
- replay 테스트
- promotion panel
- structured learning dataset export

### GA
- live 모드 운영
- 수동 승인 또는 자동 승격
- 다중 전략 버전 관리
- 리포팅 고도화
- 장기 학습 파이프라인 자동화
