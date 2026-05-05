# STRATEGY_SPEC.md

## 1. 문서 목적
이 문서는 전략 로직, 신호 생성, 국면 판정, 자산 기반 비중 계산, 손절, 재진입, 데모 승격 기준을 정의한다.

---

## 2. 전략 목표
- 급등·급락 초기에 반응
- 노이즈 진입 최소화
- 손절을 내장한 포지션 운영
- 현재 보유 자산을 기준으로 비중 계산
- 재기동/운영 이상 시 보수적으로 방어
- 실거래 이전에 데모 기간을 충분히 확보
- 모든 거래와 결정에서 학습 데이터 축적
- 학습 로그를 중심으로 Codex가 룰을 분석·제안·테스트하고 demo 검증 후 승인받아 live에 반영

---

## 3. 신호 생성 규칙

### 3.1 입력 feature
- ret_1s
- ret_5s
- ret_30s
- volume_multiple
- traded_value_multiple
- spread_bps
- orderbook_imbalance
- short_volatility
- regime_score

### 3.2 신호 레벨
- weak
- medium
- strong
- very_strong

신호 점수 레벨 기준:
- `score >= 0.70`: very_strong
- `score >= 0.45`: strong
- `score >= 0.18`: medium
- 그 외: weak

최근 단타 학습 로그에서 대부분의 자동 운용 신호가 0.18~0.20 점수대에 머물러 `AUTO_MIN_SIGNAL_LEVEL`로 차단되는 문제가 확인되었다. 단타 demo 검증에서는 이 구간을 medium으로 인정해 실제 체결 데이터를 더 축적한다.

### 3.3 예시 룰
#### 급등 신호
- ret_30s >= threshold
- volume_multiple 증가
- imbalance > 0
- spread 허용 범위 내
- liquidity 충분

#### 급락 신호
- ret_10s 하락 임계값 초과
- volume 급증
- imbalance < 0
- 보유 포지션 존재 시 매도/손절 우선

### 3.4 signal score
signal score는 단순 가격 변화가 아니라 아래 가중 조합으로 계산한다.
- price momentum
- traded value acceleration
- imbalance
- volatility normalization
- liquidity quality

---

## 4. 국면(regime) 규칙

### 4.1 regime label
- risk_on
- neutral
- risk_off

### 4.2 국면 반영
- risk_on: 진입 허용 폭 확대
- neutral: 기본 규칙
- risk_off: size 축소 또는 진입 차단

### 4.3 강등 규칙
strong 신호라도 아래 조건이면 medium 이하로 강등 가능
- spread 과다
- liquidity 부족
- 최근 연속 손실
- volatility 과열
- restart 이후 SAFE_MODE

---

## 5. 자산 기반 비중 계산

### 5.1 기본 비율
- weak: buy 0.08 / sell 0.12
- medium: buy 0.18 / sell 0.28
- strong: buy 0.35 / sell 0.45
- very_strong: buy 0.55 / sell 0.70

### 5.2 계산 요소
- cash_balance
- asset_balance
- min_cash_reserve
- fee_rate
- slippage_estimate
- regime_multiplier
- liquidity_multiplier
- risk_multiplier

### 5.3 매수 계산 예시
```python
investable_cash = max(cash_balance - min_cash_reserve, 0)
final_buy_ratio = base_buy_ratio * regime_multiplier * liquidity_multiplier * risk_multiplier
buy_amount = investable_cash * final_buy_ratio
buy_qty = buy_amount / current_price
```

### 5.4 매도 계산 예시
```python
final_sell_ratio = base_sell_ratio * exit_urgency_multiplier
sell_qty = asset_balance * final_sell_ratio
sell_amount = sell_qty * current_price
```

### 5.5 진입 차단 조건
- 예상 슬리피지 > 최대 허용치
- spread > 최대 허용치
- liquidity score 부족
- 일일 손실 한도 초과
- reentry block 활성
- SAFE_MODE
- 기대값 음수
- weak 신호에서 예상 엣지가 왕복 수수료와 최소 순엣지를 넘지 못함

### 5.6 단타 medium 진입 완화
단타 demo 운영에서는 medium 신호의 수수료 보정 엣지 버퍼를 기본 최소 순엣지의 25%로 완화한다.

목적:
- `AUTO_MIN_SIGNAL_LEVEL`과 `FEE_ADJUSTED_EDGE_LIMIT` 차단만 누적되어 체결 데이터가 부족해지는 문제 완화
- demo 체결, 손절, 매도 결과를 더 쌓아 학습 데이터 균형 개선

제한:
- weak 신호는 기존 수수료/순엣지 게이트를 통과해야 한다.
- spread, slippage, 최소 현금, 손절 리스크 예산 차단은 그대로 유지한다.
- live 모드에서는 SAFE_MODE, HARD_STOP, API 키, 실거래 활성화 플래그 조건을 우회할 수 없다.

---

## 6. 손절 전략

## 6.1 매수 시 손절가 주입
모든 매수 체결은 아래 정보를 포지션에 저장해야 한다.
- entry_price
- stop_loss_price
- stop_loss_pct
- validation_window_sec
- min_expected_return_pct
- stop_loss_reason = null

### 신호별 손절 비율 예시
- weak: 0.008
- medium: 0.012
- strong: 0.018
- very_strong: 0.022

### 계산 예시
```python
stop_loss_price = entry_price * (1 - stop_loss_pct)
```

---

## 6.2 하드 손절
### 조건
- `current_price <= stop_loss_price`

### 조치
- 즉시 손절 매도
- 사유: `STOP_LOSS_PRICE_HIT`

---

## 6.3 소프트 손절
### 조건
아래 조건 중 하나라도 만족하면 손절 또는 축소 청산
- validation window 종료 후 최소 기대 수익률 미달
- momentum score 하락
- imbalance 역전
- 거래량 급감
- 추세 지속 실패

### 예시
```python
if elapsed_sec >= validation_window_sec and unrealized_return_pct < min_expected_return_pct:
    trigger_stop_loss("STOP_LOSS_EXPECTATION_FAILED")
```

### 주요 사유 코드
- STOP_LOSS_PRICE_HIT
- STOP_LOSS_EXPECTATION_FAILED
- STOP_LOSS_MOMENTUM_REVERSAL
- STOP_LOSS_LIQUIDITY_DROPPED
- STOP_LOSS_RESTART_SAFE_MODE

---

## 6.4 부분 손절
강한 신호에서 진입했지만 기대와 다르게 흐를 경우
- 1차 50% 축소
- 나머지 포지션은 더 타이트한 손절 적용

---

## 6.5 손절 후 재진입 차단
- `REENTRY_BLOCK_SECONDS` 동안 동일 종목 재진입 금지
- 연속 손절 시 block 시간 확대 가능

---

## 7. 일반 청산 전략

### 일반 매도
- 목표 수익 도달
- 국면 악화
- 반대 신호 발생
- 부분 익절 / 전량 청산

### 브레이크이븐 스탑
- 일정 수익 도달 후 손절가를 entry_price 이상으로 올려 손실 없는 포지션으로 전환

### 트레일링 스탑
- `trailing_stop_enabled=true`일 때 고점 갱신 기준으로 손절가를 이동

---

## 8. 실행 모드별 전략 적용

### demo
- 실주문 금지
- 가상 체결
- 실제와 동일한 전략 로직
- 승격용 성과 측정

### live
- 실주문 허용
- SAFE_MODE 해제 후에만 신규 주문
- 항상 학습 로그 저장

---

## 9. 항상 켜진 학습 계층

### 저장 이벤트
- signal_generated
- regime_snapshot
- sizing_decision
- order_intent
- fill_result
- stop_loss_triggered
- position_closed
- restart_detected
- recovery_completed
- promotion_evaluated

### 기록 목적
우선순위는 아래 순서로 고정한다.

1. 룰 개선 분석 데이터
2. replay 검증 데이터
3. demo→live 승격 평가 데이터
4. 전략 회귀 검증과 feature 품질 분석
5. 향후 모델 학습 데이터

---

## 10. 승격 전략

### 10.1 데모 운영 목표
실거래 전 데모에서 충분한 표본과 안정성을 확보한다.

### 10.2 평가 지표
- demo_days
- total_trades
- win_rate
- profit_factor
- max_drawdown
- stoploss_failures
- recovery_success_rate
- telegram_success_rate

### 10.3 기준 예시
- demo_days >= 14
- total_trades >= 100
- win_rate >= 0.52
- profit_factor >= 1.20
- max_drawdown <= 0.08
- stoploss_failures == 0

### 10.4 평가 예시 코드
```python
eligible_for_live = (
    demo_days >= DEMO_MIN_DAYS
    and total_trades >= DEMO_MIN_TRADES
    and win_rate >= DEMO_MIN_WIN_RATE
    and profit_factor >= DEMO_MIN_PROFIT_FACTOR
    and max_drawdown <= DEMO_MAX_DRAWDOWN
    and stoploss_failures <= DEMO_MAX_STOPLOSS_FAILURES
)
```

### 10.5 권장 승격 정책
- 기본은 수동 승인
- 자동 승격 허용 시에도 SAFE_MODE로 시작
- 초기 실거래는 size 축소 권장
- 룰 변경이 발생하면 승격 평가를 다시 실행한다.
- live 운영 중 룰 변경은 즉시 반영하지 않는다.
- 룰 변경안은 먼저 demo에 적용하고 replay + demo 지표 통과 후 승인받는다.

---

## 11. 전략 변경 절차
초기 전략 개선은 TensorFlow 직접 학습보다 **학습 로그 기반 Codex 룰 개선 루프**를 우선한다. TensorFlow 모델은 선택 의존성 `ml`의 오프라인 학습 파이프라인으로 후순위 처리하며, 규칙 기반 리스크 게이트를 우회할 수 없다. 오프라인 학습은 표본 수, train/validation/test 기간 분리, baseline 대비 성능을 통과해야 하며 결과는 먼저 shadow mode 리포트로만 저장한다.

전략 변경 시 반드시 아래를 따른다.
1. 최근 `RULE_REVIEW_WINDOW_DAYS` 학습 로그 집계
2. 거래 수, 손절 수, 주요 손실 원인 분석
3. 룰 변경안 생성
4. 실패 테스트 추가
5. replay fixture 업데이트 및 replay 테스트
6. demo 적용
7. demo 지표 재검증
8. 운영자 승인
9. live 반영
10. 문서 갱신
11. 한국어 Git 커밋

한 번에 바꾸는 파라미터 수는 `RULE_CHANGE_MAX_PARAMS_PER_RUN` 이하로 제한한다. `RULE_REVIEW_MIN_TRADES`와 `RULE_REVIEW_MIN_STOPLOSSES` 기준을 충족하지 못하면 해당 변경안은 생성하지 않는다.

### 커밋 예시
- `급등 신호 점수 가중치 조정과 replay 테스트 추가`
- `기대 불일치 손절 기준 보강 및 손절 통계 반영`
