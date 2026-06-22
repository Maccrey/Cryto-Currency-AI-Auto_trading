# STRATEGY_SPEC.md

## 1. 문서 목적
이 문서는 전략 로직, 신호 생성, 국면 판정, 장세 전환 감지, 동적 박스권 범위 추적, 자산 기반 비중 계산, 손절, 재진입, 데모 룰 A~F 승격 기준을 정의한다.

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
- **하락장 → 상승장 / 상승장 → 하락장 전환 구간을 복합 기술지표로 정밀 감지해 진입·청산 타이밍 최적화**

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
- **rsi_14** (RSI 14기간)
- **macd_histogram** (MACD 히스토그램, 가격 정규화)
- **bollinger_position** (볼린저 밴드 위치 0~1)
- **ma_trend** (단기·장기 이동평균 차이)
- **stochastic_k** (스토캐스틱 K)
- **price_position_20** (20틱 내 가격 위치)
- **drawdown_from_high_20** (20틱 고점 대비 낙폭)
- **rebound_from_low_20** (20틱 저점 대비 반등폭)
- **trend_efficiency_20** (20틱 추세 효율성)

### 3.2 신호 레벨
- weak
- medium
- strong
- very_strong

신호 점수 레벨 기준:
- `score >= 0.85`: very_strong
- `score >= 0.65`: strong
- `score >= 0.40`: medium
- 그 외: weak

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

### 3.5 시장 기회 부스트 (Market Opportunity Boost)
신호 레벨이 `weak`이어도 아래 조건 충족 시 `score_floor`까지 점수를 끌어올린다.

| 조건 | score_floor | 코드 |
|---|---|---|
| 상승장 + 기술지표 지지 | 0.40 | BULL_MARKET_PARTICIPATION_BOOST |
| 박스권 하단 + 반등 신호 | 0.42 | BOX_RANGE_VALUE_ENTRY_BOOST |
| 하락장 + 반등 확인 (전환 초입) | 0.45 | BEAR_REBOUND_PARTICIPATION |

---

## 4. 국면(regime) 규칙

### 4.1 regime label
- risk_on
- neutral
- risk_off

### 4.2 장세(market_state) 3분류

| 장세 | 판정 기준 |
|---|---|
| **상승장(bull)** | `ret_30s > 0.005` 또는 (`ret_30s > 0.002` AND `orderbook_imbalance > 0.12`) |
| **하락장(bear)** | `ret_30s < -0.006` AND `orderbook_imbalance < -0.15` |
| **박스권(box)** | 상승장·하락장 조건 미충족 |

### 4.3 국면 반영
- risk_on: 진입 허용 폭 확대
- neutral: 기본 규칙
- risk_off: size 축소 또는 진입 차단

### 4.4 강등 규칙
strong 신호라도 아래 조건이면 medium 이하로 강등 가능
- spread 과다
- liquidity 부족
- 최근 연속 손실
- volatility 과열
- restart 이후 SAFE_MODE

---

## 5. 장세 전환 감지 (MarketTransitionDetector)

> **파일:** `app/services/trading/market_transition.py`

장세 전환을 단일 지표가 아니라 복합 지표로 감지해 전환 점수(0.0~1.0)를 산출한다.
점수 **0.60 이상**이면 전환 확정(임계값 설정 가능).

### 5.1 하락 → 상승 전환 점수 (bear_to_bull_score)

| 구성 요소 | 가중치 | 조건 |
|---|---|---|
| RSI 과매도 회복 | 0.25 | 이전 RSI < 35 → 현재 RSI ≥ 35 (크로스) |
| RSI 저점 상승 | 0.12 | RSI < 38 이고 이전 대비 상승 중 |
| MACD 히스토그램 크로스업 | 0.20 | 음수 → 양수 전환 |
| MACD 개선 중 | 0.10 | 여전히 음수이나 이전 대비 상승 |
| MA trend 양전환 | 0.20 | ma_trend ≥ 0 |
| MA trend 회복 중 | 0.10 | -0.001 ≤ ma_trend < 0 |
| 강한 양수 모멘텀 | 0.20 | ret_30s > 0.002 |
| 양수 모멘텀 | 0.10 | ret_30s > 0 |
| 호가 매수 우위 | 0.15 | orderbook_imbalance ≥ 0.05 |
| 호가 중립 | 0.07 | orderbook_imbalance ≥ -0.05 |
| 저점 반등 보너스 | +0.08 | rebound_from_low_20 ≥ 0.005 |

- 하락장에서 bollinger_position ≥ 0.6 → 패널티 × 0.75 (데드캣 반등 위험)

### 5.2 상승 → 하락 전환 점수 (bull_to_bear_score)

| 구성 요소 | 가중치 | 조건 |
|---|---|---|
| RSI 과매수 반전 | 0.25 | 이전 RSI > 65 → 현재 RSI ≤ 65 (크로스) |
| RSI 고점 하락 | 0.12 | RSI > 60 이고 이전 대비 하락 중 |
| MACD 히스토그램 크로스다운 | 0.20 | 양수 → 음수 전환 |
| MACD 악화 중 | 0.10 | 여전히 양수이나 이전 대비 하락 |
| MA trend 음전환 | 0.20 | ma_trend ≤ -0.001 |
| MA trend 약화 중 | 0.10 | -0.001 < ma_trend ≤ 0 |
| 강한 음수 모멘텀 | 0.20 | ret_30s < -0.003 |
| 음수 모멘텀 | 0.10 | ret_30s < 0 |
| 호가 매도 우위 | 0.15 | orderbook_imbalance ≤ -0.10 |
| 호가 중립 약세 | 0.07 | orderbook_imbalance ≤ 0 |
| 고점 낙폭 가속 보너스 | +0.08 | drawdown_from_high_20 ≤ -0.005 |

- 상승장에서 bollinger_position ≤ 0.4 → 패널티 × 0.75 (단순 눌림목 위험)

### 5.3 전환 감지 활용

| 확정 여부 | 적용 내용 |
|---|---|
| 하락→상승 확정 (≥ 0.60) | 매수 배수 ×1.35 부스트, 하락장에서도 진입 허용 |
| 하락→상승 부분 점수 (0.40~0.60) | 선형 보간으로 최대 ×1.60 부스트 |
| 상승→하락 확정 (≥ 0.60) | 매도 배수 ×1.80, 강제 청산 플래그, 신규 진입 금지 |

---

## 6. 동적 박스권 범위 추적 (Dynamic Box Range)

> **파일:** `app/services/regime/engine.py`

### 6.1 기존 방식의 문제점
단일 틱의 현재가 ± 변동성으로 계산하면 박스 범위가 너무 좁아 매 틱마다 상단·하단이 바뀌어 의미 없는 경계가 만들어진다.

### 6.2 개선된 동적 박스 범위

| 항목 | 값 |
|---|---|
| 가격 히스토리 버퍼 | 최대 200틱 (deque) |
| 최소 수집 틱 수 | 20틱 이후부터 산출 |
| 하단 기준 | 5th 백분위 가격 × (1 - 0.1%) |
| 상단 기준 | 95th 백분위 가격 × (1 + 0.1%) |
| 폴백 | 수집 틱 < 20 시 단일 틱 정적 범위 사용 |

- `RegimeSnapshot`에 `dynamic_box_low` / `dynamic_box_high` 필드 추가
- `reason_codes`에 `DYNAMIC_BOX_RANGE_ACTIVE` 코드 포함

### 6.3 동적 박스 포지션 활용
variants가 박스 포지션(0~1)을 계산할 때 동적 범위를 우선 사용하고, 없을 때만 정적 범위로 폴백한다.

---

## 7. 자산 기반 비중 계산

### 7.1 기본 비율
- weak: buy 0.08 / sell 0.12
- medium: buy 0.18 / sell 0.28
- strong: buy 0.35 / sell 0.45
- very_strong: buy 0.55 / sell 0.70

### 7.2 계산 요소
- cash_balance
- asset_balance
- min_cash_reserve
- fee_rate
- slippage_estimate
- regime_multiplier
- liquidity_multiplier
- risk_multiplier

### 7.3 매수 계산 예시
```python
investable_cash = max(cash_balance - min_cash_reserve, 0)
final_buy_ratio = base_buy_ratio * regime_multiplier * liquidity_multiplier * risk_multiplier
buy_amount = investable_cash * final_buy_ratio
buy_qty = buy_amount / current_price
```

### 7.4 매도 계산 예시
```python
final_sell_ratio = base_sell_ratio * exit_urgency_multiplier
sell_qty = asset_balance * final_sell_ratio
sell_amount = sell_qty * current_price
```

### 7.5 진입 차단 조건
- 예상 슬리피지 > 최대 허용치
- spread > 최대 허용치
- liquidity score 부족
- 일일 손실 한도 초과
- reentry block 활성
- SAFE_MODE
- 기대값 음수
- weak 신호에서 예상 엣지가 왕복 수수료와 최소 순엣지를 넘지 못함
- 현재가 카드 또는 최근 가격 흐름이 `하락장`이면 신호 강도나 반등 후보 코드와 무관하게 신규 매수와 추가매수를 차단
  - 단, **하락→상승 전환 확정(bear_to_bull_confirmed=True)** 시 룰별 조건에 따라 진입 허용
- 마지막 매도 체결가와 같은 가격대에서 재매수하려는 경우 가격 이점 또는 확정 상승 돌파가 확인될 때까지 차단

### 7.6 단타 medium 진입 완화
단타 demo 운영에서는 medium 신호의 수수료 보정 엣지 버퍼를 기본 최소 순엣지의 25%로 완화한다.

목적:
- `AUTO_MIN_SIGNAL_LEVEL`과 `FEE_ADJUSTED_EDGE_LIMIT` 차단만 누적되어 체결 데이터가 부족해지는 문제 완화
- demo 체결, 손절, 매도 결과를 더 쌓아 학습 데이터 균형 개선

제한:
- weak 신호는 기존 수수료/순엣지 게이트를 통과해야 한다.
- spread, slippage, 최소 현금, 손절 리스크 예산 차단은 그대로 유지한다.
- live 모드에서는 SAFE_MODE, HARD_STOP, API 키, 실거래 활성화 플래그 조건을 우회할 수 없다.

---

## 8. 손절 전략

### 8.1 매수 시 손절가 주입
모든 매수 체결은 아래 정보를 포지션에 저장해야 한다.
- entry_price
- stop_loss_price
- stop_loss_pct
- validation_window_sec
- min_expected_return_pct
- stop_loss_reason = null

#### 투자성향별 고정 손절 비율
손절률은 신호 강도나 Codex 룰 변경으로 조정하지 않는다. 모든 신호 강도는 현재 투자성향의 고정 손절률을 동일하게 사용한다.

| 투자성향 | 고정 손절 |
|---|---:|
| 단타 | -3% |
| 단기 | -3% |
| 중기 | -5% |
| 장기 | -10% |

`STOP_LOSS_*`, `stop_loss_pct`, `stop_loss_price`, `fixed_stop_loss_pct`는 룰 개선 파이프라인의 변경 대상이 아니다. Codex가 학습 로그를 분석하더라도 손절률 변경안은 생성하지 않고, 손절 관련 개선은 진입 조건, 사이징, 재진입 차단, 기대 검증 기준으로만 제안한다.

#### 계산 예시
```python
stop_loss_price = entry_price * (1 - stop_loss_pct)
```

### 8.2 하드 손절
#### 조건
- `current_price <= stop_loss_price`

#### 조치
- 즉시 손절 매도
- 사유: `STOP_LOSS_PRICE_HIT`

### 8.3 소프트 손절
#### 조건
아래 조건 중 하나라도 만족하면 손절 또는 축소 청산
- validation window 종료 후 최소 기대 수익률 미달
- momentum score 하락
- imbalance 역전
- 거래량 급감
- 추세 지속 실패

#### 예시
```python
if elapsed_sec >= validation_window_sec and unrealized_return_pct < min_expected_return_pct:
    trigger_stop_loss("STOP_LOSS_EXPECTATION_FAILED")
```

#### 주요 사유 코드
- STOP_LOSS_PRICE_HIT
- STOP_LOSS_EXPECTATION_FAILED
- STOP_LOSS_MOMENTUM_REVERSAL
- STOP_LOSS_LIQUIDITY_DROPPED
- STOP_LOSS_RESTART_SAFE_MODE

### 8.4 부분 손절
강한 신호에서 진입했지만 기대와 다르게 흐를 경우
- 1차 50% 축소
- 나머지 포지션은 더 타이트한 손절 적용

### 8.5 손절 후 재진입 차단
- `REENTRY_BLOCK_SECONDS` 동안 동일 종목 재진입 금지
- 쿨다운이 끝나도 마지막 손절 사유와 손절 체결가를 유지해 재진입 확인에 사용
- 손절 후 재진입은 확정 상승장, strong 이상 신호, 손절 체결가 대비 회복 가격을 모두 만족할 때만 허용
- 하락장 또는 박스권에서는 손절 후 재매수를 하지 않고, 상승장 확인 틱이 충분히 누적될 때까지 대기
- 연속 손절 시 block 시간 확대 가능
- 최근 실행 원장에서 약신호 매수가 대부분이고 손절 손실이 익절 수익보다 큰 상태에서는 약신호 재진입과 추가매수를 차단한다.

---

## 9. 일반 청산 전략

### 일반 매도
- 목표 수익 도달
- 국면 악화
- 반대 신호 발생
- **상승 → 하락 전환 확정(bull_to_bear_confirmed=True) 시 즉시 강제 청산 트리거**
- **박스권 상단(동적 box_position ≥ 0.80) 도달 시 자동 익절**
- 기본은 높은 비율 청산이며, 약한 신호 또는 약한 차트 흐름에서는 전량 청산
- 일부 익절은 강한 추세 지속 근거가 있을 때만 잔여 포지션을 남긴다.

### 매도 후 재진입
- 일반 매도 직후 동일 가격대 재매수는 수수료와 슬리피지를 고려하면 기대값이 낮으므로 차단한다.
- 재진입은 매도 체결가보다 왕복 수수료와 최소 버퍼만큼 낮은 가격에 도달하거나, 확정 상승장과 strong 이상 신호가 동반된 돌파 가격을 넘을 때만 허용한다.
- 손절 매도 후 재진입은 일반 매도보다 더 엄격하게 보며, 하락장에서 상승장으로 바뀐 것이 확인되기 전에는 허용하지 않는다.

### 브레이크이븐 스탑
- 일정 수익 도달 후 손절가를 entry_price 이상으로 올려 손실 없는 포지션으로 전환
- 부분 익절 후 잔여 수량이 있으면 손절가를 entry_price + 왕복 수수료 + 보호 버퍼 이상으로 상향한다.

### 트레일링 스탑
- `trailing_stop_enabled=true`일 때 고점 갱신 기준으로 손절가를 이동

---

## 10. 데모 룰 A~O 다중 변형 동시 테스트

> **파일:** `app/services/trading/variants.py`

### 10.1 룰 목록 및 특성

| 룰 | 명칭 | 핵심 특성 | buy_mult | sell_mult | TP% | SL% |
|---|---|---|---|---|---|---|
| A | 안정형 | 기본 신호 + 장세 민감 배수 + 전환 감지 | 1.00 | 1.00 | 0.60% | 0.40% |
| B | 추세형 | 상승장·하락→상승 전환에만 크게 진입 | 1.85 | 0.45 | 1.40% | 0.65% |
| C | 방어형 | 하락장 즉시 청산, 박스 하단(40%↓) + 전환 시 소량 진입 | 0.38 | 2.00 | 0.32% | 0.20% |
| D | 돌파확인형 | 전환 확정 또는 상승장 모멘텀 돌파 확인 후 진입 | 1.25 | 0.70 | 1.00% | 0.45% |
| E | 박스저점형 | 박스 하단(38%↓) 반등 또는 전환 구간 거래 | 0.72 | 1.70 | 0.48% | 0.28% |
| F | 자본보전형 | 강한 신호·전환 구간에서만 소량 진입, 낙폭 억제 최우선 | 0.32 | 2.20 | 0.75% | 0.30% |
| G | 스캘핑형 | 강한 신호에만 소량 진입, 빠른 익절 및 손절 누적 | 0.55 | 1.50 | 0.30% | 0.18% |
| H | 모멘텀형 | 최강 상승 모멘텀과 시장 압력 동반 상승 시 공격 진입 | 2.20 | 0.35 | 1.80% | 0.80% |
| I | 분할매수형 | 하락 지속 시 분할 매수, 반등 전환 시 분할 청산 | 0.65 | 1.35 | 0.55% | 0.32% |
| J | 역추세형 | 과매도 박스 하단 강한 반등 타겟, 타이트한 손절 | 0.90 | 1.80 | 0.65% | 0.22% |
| K | 변동성형 | 변동성 급등 구간 소량 진입, 빠른 손절 보호 | 0.48 | 1.95 | 0.42% | 0.25% |
| L | 하이브리드형 | 추세형(B)과 방어형(C)을 장세별 자동 혼합 운영 | 1.10 | 1.15 | 0.85% | 0.42% |
| M | 돌파추격형 | 상승장 강력 모멘텀 확인 시 빠르게 진입하여 단기 상승 추세 극대화 | 1.50 | 0.80 | 1.20% | 0.50% |
| N | 역변동성형 | 변동성이 높고 가격이 박스권 극단 영역 도달 시 역추세 반등 노림 | 0.60 | 1.50 | 0.50% | 0.30% |
| O | 공격추세형 | 상승 확정 구간 최대 가중치 진입, 하락 전환 시 단호하게 청산 | 2.00 | 0.40 | 2.00% | 0.70% |

### 10.2 장세별 룰 정책 요약

#### 상승장(bull)
- **A**: 매수 배수 × (1 + market_pressure × 0.30), 익절 폭 15% 확대
- **B**: 매수 배수 × (1.30 + pressure × 0.48), 익절 폭 38% 확대
- **C**: 소량 참여 (매수 배수 × 0.45), 방어적 청산
- **D**: 모멘텀 ≥ 0.18 + medium 이상 신호 시 진입 (돌파 확인형)
- **E**: 박스 하단 반등 조건 대기 (상승장 중 조건 불충족 → 대기)
- **F**: market_pressure ≥ 0.08 + strong 이상 신호 시 소량 진입
- **M**: market_pressure >= 0.15 + strong 이상 신호 시 매수 배수 추가 1.25배 부스트, 익절 폭 15% 확대
- **O**: 상승세 확인 시 매수 배수 1.45배 이상 부스트, 익절 폭 30% 확대

#### 하락장(bear) — 기본 진입 차단
- **A**: 하락→상승 전환 확정 시 조건부 진입 허용 (매수 × 0.65)
- **B**: 하락→상승 전환 확정 시 추세형 진입 (점수에 비례)
- **C**: 하락→상승 전환 확정 시 방어형 소량 진입 (매수 × 0.48)
- **D**: 전환 확정 + medium 이상 신호 시 진입
- **E**: 조건 미충족 시 완전 차단
- **F**: 전환 확정 + medium 이상 시 소량 진입
- **O**: 신규 진입 완전 차단, 전환 감지(`forced_sell`) 시 매도 배수 2.5배로 극대화하여 초고속 청산

#### 박스권(box) — 동적 범위 기반 상단/하단 판별
- **A**: ≤ 50% 진입 허용, ≤ 68% 소량 허용
- **B**: 전환 확정 시만 허용
- **C**: ≤ 40% 또는 전환+55% 허용
- **D**: ≤ 35% + 모멘텀 ≥ 0.05 허용
- **E**: ≤ 38% + 반등 확인 시 허용 및 상단 도달 시 자동 익절
- **F**: ≤ 32% + medium 이상 신호 시 허용
- **N**: 변동성이 높고 가격 분포가 양 극단(≤ 18% 또는 ≥ 82%) 도달 시 역방향 반등 진입

### 10.3 전환 구간 공통 적용 규칙

```
하락→상승 전환 확정(bear_to_bull_confirmed=True):
  - 매수 배수 × 1.35 공통 부스트 (전환 buy boost)
  - 부분 점수(0.40~0.60): 선형 보간 최대 × 1.60

상승→하락 전환 확정(bull_to_bear_confirmed=True):
  - 매도 배수 × 1.80 (forced_sell) (Rule O의 경우 × 2.50)
  - 익절 임계 × 0.55 (잔여 수익 빠르게 실현)
  - 강제 청산 비율 최소 80%
  - 신규 진입 금지
```

### 10.4 손절 시 즉시 리더 스위칭 메커니즘
현재 실제 주문에 적용되어 구동 중인 리더 룰(applied_variant_key)에서 손절(Stop Loss)이 발생하는 순간, 최소 15회 거래량 등의 승격 제약 조건(`_promotion_eligible`)을 완전히 **우회(Bypass)**하여 즉시 전체 15개 룰 중 당일 수익률(`profit_rate`)이 가장 높은 룰로 대표 룰을 강제 전환합니다.
이는 하락장 또는 특정 급락 구간에서 잘못된 리더 룰에 의해 발생할 수 있는 연속 손실 노출을 방어하기 위한 긴급 조치입니다.

### 10.5 변동성 패널티 (공통)
```python
volatility_penalty = min(max(short_volatility / 0.02, 0), 1)
if volatility_penalty > 0.5:
    buy_multiplier  *= 1 - (volatility_penalty - 0.5) * 0.35
    sell_multiplier *= 1 + (volatility_penalty - 0.5) * 0.28
    stop_loss_pct   *= 0.88
```

### 10.6 약신호 가드 (공통)
| 룰 | weak 신호 처리 |
|---|---|
| A | 매수 배수 × 0.72 |
| B | 상승장 + pressure ≥ 0.12 아니면 차단 |
| C | 매수 배수 × 0.55 |
| D, E, F | 전환 확정 없으면 완전 차단 |

### 10.7 승격 조건
- 양수 수익률 + 양수 실현손익
- 최소 15회 청산 (`MIN_PROMOTION_TRADES = 15`)
- Profit Factor > 1.0
- 손절 비중 ≤ 40%

---

## 11. 항상 켜진 학습 계층

### 저장 이벤트
- signal_generated
- regime_snapshot
- **transition_state** (전환 점수, 확정 여부, 동적 박스 범위)
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

## 12. 승격 전략

### 12.1 데모 운영 목표
실거래 전 데모에서 충분한 표본과 안정성을 확보한다.

### 12.2 평가 지표
- demo_days
- total_trades
- win_rate
- profit_factor
- max_drawdown
- stoploss_failures
- recovery_success_rate
- telegram_success_rate

### 12.3 기준 예시
- demo_days >= 14
- total_trades >= 100
- win_rate >= 0.52
- profit_factor >= 1.20
- max_drawdown <= 0.08
- stoploss_failures == 0

### 12.4 평가 예시 코드
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

### 12.5 권장 승격 정책
- 기본은 수동 승인
- 자동 승격 허용 시에도 SAFE_MODE로 시작
- 초기 실거래는 size 축소 권장
- 룰 변경이 발생하면 승격 평가를 다시 실행한다.

### 12.6 데모 다중 룰 변경 게이트
- A~F 6개 후보를 같은 틱으로 함께 평가한다.
- 손실 후보는 상대 순위가 1위여도 적용하지 않는다.
- 누적수익과 실현손익이 모두 양수이고, 최소 20회 청산, Profit Factor 1 초과, 손절 비중 40% 이하를 만족한 후보만 demo 룰 리더가 된다.
- replay는 실제 거래가 1건 이상이고 최종 수익률이 0%를 초과해야 통과한다.
- 양수 후보가 없어 변경을 보류한 경우 기존 룰과 후보별 누적 성과를 유지한다.
- 양수 후보가 검증되어 demo 변경을 적용한 경우에만 후보별 내부 포트폴리오를 리셋하고 새 기준으로 다시 평가한다.
- 대시보드에는 A~F 후보를 모두 표시하고, 수익률 최고 후보와 실제 적용 룰을 구분한다.
- 참고 후보는 수익률을 최우선으로 비교하므로 `-0.13% > -0.68%`로 평가한다. 음수 후보는 실제 적용 룰을 변경하지 않는다.
- 적용 가능한 양수 최고 룰이 바뀌면 해당 룰의 장세별 진입 허용 조건과 매수 배수를 다음 demo 진입 판단부터 사용한다.

### 12.7 박스권과 방향성 추세 구분
- 상단·하단 반복 접촉만으로 박스권을 확정하지 않는다.
- 288개 가격 관측의 선형 기울기가 `±0.2%` 이상이고 중기 가격 흐름이 반대 방향으로 급격히 움직이지 않으면 방향성 추세를 우선한다.
- 박스권으로 확정한 경우 관측 가격의 **동적 하단과 상단**(5th/95th 백분위 기반)을 현재가 카드 아래에 함께 표시한다.
- live 운영 중 룰 변경은 즉시 반영하지 않는다.
- 룰 변경안은 먼저 demo에 적용하고 replay + demo 지표 통과 후 승인받는다.

---

## 13. 전략 변경 절차
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
10. 룰 변경 히스토리 원장 기록
11. 문서 갱신
12. 한국어 Git 커밋

한 번에 바꾸는 파라미터 수는 `RULE_CHANGE_MAX_PARAMS_PER_RUN` 이하로 제한한다. `RULE_REVIEW_MIN_TRADES`와 `RULE_REVIEW_MIN_STOPLOSSES` 기준을 충족하지 못하면 해당 변경안은 생성하지 않는다.

### 13.1 룰 변경 히스토리 정책
Codex가 학습 데이터를 바탕으로 매매룰을 새로 업데이트할 때는 기존 룰과 신규 룰의 차이를 장기 보관한다. 목표는 단순 변경 기록이 아니라, 시간이 지나도 변경 이유와 결과를 복기해 실수를 줄이고 더 우수한 트레이딩 의사결정으로 수렴하는 것이다.

히스토리는 코인/투자성향별 `rule-change-history.jsonl`에 append-only로 저장한다. 각 이력은 다음 질문에 답해야 한다.
- 어떤 기존 룰을 바꿨는가?
- 어떤 학습 로그 표본과 손실/차단 원인이 근거였는가?
- 온체인/ETF 컨텍스트는 변경 판단에 어떤 영향을 줬는가?
- 새 룰은 어떤 효과를 기대하는가?
- replay와 demo 검증 결과는 기대와 일치했는가?
- live 승인자는 누구이며 어떤 리스크를 감수했는가?
- 이후 성과가 나쁘면 되돌릴 수 있는 기준은 무엇인가?

룰 변경 히스토리를 남기지 않은 변경안은 demo/live 적용 대상이 될 수 없다.

### 커밋 예시
- `급등 신호 점수 가중치 조정과 replay 테스트 추가`
- `기대 불일치 손절 기준 보강 및 손절 통계 반영`
- `장세 전환 감지 및 동적 박스권 범위 추적으로 룰 A~F 개선`
