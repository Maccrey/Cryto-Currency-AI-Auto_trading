# AI.md

## 1. 목적

이 문서는 현재 자동매매 AI가 어떻게 판단하고, 어떤 데이터를 학습 로그로 남기며, 어떤 패키지 위에서 동작하는지 설명한다.

현재 구현은 외부 ML 모델을 직접 학습시키는 구조가 아니라, 규칙 기반 의사결정 엔진과 항상 켜진 학습 로그를 결합한 구조다. 즉, 서버는 매 판단/체결/차단/손절/복구 이벤트를 JSONL로 저장하고, 이 데이터가 이후 모델 학습과 전략 개선의 원천 데이터가 된다.

---

## 2. 사용 패키지

런타임 핵심 패키지:
- `FastAPI`: API 서버와 대시보드 라우팅
- `Uvicorn`: ASGI 서버 실행
- `Pydantic v2`: 환경 변수와 API payload 검증
- `structlog`: 구조화 로그 기반 관찰성
- Python 표준 라이브러리: `asyncio`, `dataclasses`, `json`, `datetime`, `pathlib`, `collections`

현재 프로젝트에는 scikit-learn, PyTorch, TensorFlow 같은 모델 학습 패키지가 기본 의존성으로 포함되어 있지 않다. 모델 파일을 직접 업데이트하는 학습이 아니라, 운영 데이터를 축적하고 진단하는 “학습 데이터 파이프라인” 단계다.

향후 모델 학습 구현을 위해 선택 의존성 `ml`을 정의한다.

```bash
pip install -e ".[ml]"
```

`ml` extra에 포함할 계획 패키지:
- `tensorflow`: 신호 품질/진입 확률/청산 위험 예측 모델 후보
- `scikit-learn`: baseline 모델, feature importance, 검증용 lightweight 모델
- `pandas`: JSONL/Parquet 데이터 가공
- `pyarrow`: Parquet dataset 저장과 로딩

중요: TensorFlow는 기본 실행 의존성에 넣지 않는다. 실시간 자동매매 서버가 무거운 학습 패키지에 묶이면 설치, 메모리, 장애 범위가 커지기 때문이다. 학습은 오프라인 배치 작업으로 분리하고, 검증된 모델만 런타임 추론 단계에 승격한다.

---

## 3. 자동 운용 흐름

서버가 시작되면 설정에 따라 자동 운용 루프가 동작한다.

기본 설정:
- `AUTO_TRADING_ENABLED=true`
- `AUTO_TRADING_LIVE_ENABLED=false`
- `AUTO_TRADING_INTERVAL_SEC=3.0`
- `AUTO_TRADING_MIN_HISTORY=6`
- `TRADING_PROFILE=scalping`
- `TRADING_FEE_RATE=0.0005`
- `PROFILE_MIN_NET_EDGE_PCT=0.0008`

demo 모드에서는 자동 운용이 기본 활성화된다. live 모드는 `AUTO_TRADING_LIVE_ENABLED=true`를 명시해야 자동 운용이 시작된다. 설정 화면에서 투자성향을 단타, 단기, 중기, 장기 중 하나로 고르면 해당 성향의 관찰 주기, 히스토리 길이, 최소 순엣지, 기대 검증 시간이 자동으로 주입된다.

투자성향 프로필:

| 값 | 표시 | 주기 | 히스토리 | 최소 순엣지 | 검증 창 |
|---|---|---:|---:|---:|---:|
| `scalping` | 단타 | 3초 | 6 | 0.08% | 180초 |
| `short_term` | 단기 | 10초 | 12 | 0.20% | 900초 |
| `mid_term` | 중기 | 30초 | 20 | 0.60% | 3600초 |
| `long_term` | 장기 | 60초 | 30 | 1.20% | 14400초 |

자동 운용 루프:
1. 업비트 현재가 ticker를 가져온다.
2. 현재가와 거래대금 히스토리를 메모리에 누적한다.
3. 히스토리가 부족하면 `MARKET_HISTORY_WARMING_UP`으로 대기한다.
4. 포지션이 없으면 feature 계산, signal 평가, regime 평가, sizing 계산을 수행한다.
5. 사이징이 허용되면 demo/live executor에 주문 intent를 전달한다.
6. 체결되면 포지션에 손절가를 주입한다.
7. 포지션이 있으면 하드 손절과 기대 불일치 손절을 점검한다.
8. 모든 사이클은 `auto_trade_cycle` 이벤트로 학습 로그에 저장된다.

---

## 4. 판단 엔진

### Feature 계산
`MarketFeatureCalculator`가 최근 가격/거래대금으로 아래 값을 계산한다.

- `ret_1s`
- `ret_5s`
- `ret_30s`
- `volume_multiple`
- `traded_value_multiple`
- `spread_bps`
- `orderbook_imbalance`
- `short_volatility`
- `regime_score`
- `liquidity_score`

### Signal 판단
`SignalEngine`은 feature를 점수화해 아래 신호를 만든다.

- `weak`
- `medium`
- `strong`
- `very_strong`

진입 차단 조건:
- 저유동성: `LOW_LIQUIDITY_BLOCKED`
- 초단기 역방향 모멘텀: `MICRO_MOMENTUM_REVERSAL_BLOCKED`
- 과도한 단기 변동성: `EXCESSIVE_SHORT_VOLATILITY_BLOCKED`

### Regime 판단
`RegimeEngine`은 시장 국면과 안전 상태를 반영한다.

- `safe_mode=True`이면 진입 차단
- 연속 손실이 많으면 risk-off 처리
- spread, 변동성, momentum으로 size multiplier 조정

### 대시보드 장세 판단
대시보드 가격 카드의 장세 표시는 `MarketTrendClassifier`가 계산한다.

- 업비트 ticker의 `signed_change_rate`가 있으면 대시보드 히스토리 변화율보다 우선해서 상승장/하락장/박스권을 판정한다.
- 변화율 절대값이 `0.2%` 이하면 박스권으로 보고, 이보다 크면 상승장 또는 하락장으로 표시한다.
- 박스권 가격 범위는 최근 가격 히스토리의 최저/최고를 쓰되, 폭이 너무 좁으면 현재가 기준 최소 `0.2%` 폭으로 보정한다.
- 대시보드 조회로 같은 현재가가 반복 수집될 때는 히스토리에 중복 저장하지 않아 1~2원 폭 박스권이 계속 표시되는 현상을 줄인다.

### Sizing 판단
`SizingEngine`은 신호 세기, 차트 강도 점수, 국면을 바탕으로 매수/매도 수량을 계산한다.

동적 수량 산정:
- 매수 비율은 `signal.score`를 약/중/강/매우강 비율 사이에서 선형 보간해 계산한다.
- 상승 확률이 높다고 판단될수록 남은 현금에서 더 큰 비율을 매수 금액으로 사용한다.
- 상승 확률이 낮다고 판단될수록 매수 금액을 줄이고, 최소 주문 금액/수수료/손절 리스크 조건을 통과하지 못하면 진입을 차단한다.
- 매도 비율은 매수와 반대로 계산해 상승 지속 강도가 높으면 적게 팔고, 약하면 더 많이 판다.
- 실제 포지션 청산은 모멘텀과 호가 불균형을 결합한 차트 지속 강도 점수로 동적 매도 비율을 보정한다.

안전장치:
- 최소 현금 보유액 유지
- spread/slippage 초과 차단
- 현재가 0 이하 차단
- 업비트 공식 KRW 마켓 최소 주문 가능 금액 `5,000 KRW` 미만 진입 차단
- 업비트 KRW 마켓 수수료 0.05% 기준 왕복 수수료와 투자성향별 최소 순엣지를 넘지 못하는 진입 차단
- 1회 예상 손절 손실을 `MAX_DAILY_LOSS`의 25% 이내로 제한

프로필 수수료 게이트:
- `TRADING_FEE_RATE=0.0005`는 거래 1회당 0.05%다.
- 매수 후 매도까지 왕복하면 기본 수수료 부담은 `0.0005 * 2 = 0.001`, 즉 0.10%다.
- 단타 기본값은 추가 순엣지 `PROFILE_MIN_NET_EDGE_PCT=0.0008`, 즉 0.08%를 더 요구한다.
- 따라서 단타는 예상 엣지가 최소 0.18%를 넘지 못하면 `FEE_ADJUSTED_EDGE_LIMIT`으로 차단한다.
- 단기, 중기, 장기는 더 긴 관찰 주기와 더 높은 최소 순엣지를 사용해 성향별로 다른 진입 성격을 만든다.
- 차단 결과는 `auto_trade_cycle.sizing_blocked_reason`에 기록되어 이후 학습 데이터로 사용된다.

청산 보정 룰:
- 최근 학습 로그에서 `STOP_LOSS_MOMENTUM_REVERSAL`이 0.5 비율로 반복 실행되며 잔량이 극소량으로 남는 문제가 확인되었다.
- KRW 마켓 매도 주문도 5,000원 미만이면 차단한다.
- 부분 청산 주문 금액이 5,000원 미만이거나 부분 청산 후 잔량 평가액이 5,000원 미만이면 전량 청산으로 전환해 dust 반복 매도를 막는다.
- 수수료를 감안해 보합권에서는 소프트 손절을 실행하지 않고, 최소 불리한 움직임이 확인된 뒤에만 기대 불일치 손절을 실행한다.

---

## 5. 학습 로그 흐름

학습 로그 경로:

```text
logs/learning/<TRADING_PROFILE>/learning.jsonl
```

예:
- 단타: `logs/learning/scalping/learning.jsonl`
- 단기: `logs/learning/short_term/learning.jsonl`
- 중기: `logs/learning/mid_term/learning.jsonl`
- 장기: `logs/learning/long_term/learning.jsonl`

주요 이벤트:
- `auto_trade_cycle`: 자동 운용 사이클 결과와 차단 사유
- `signal_generated`: 신호 점수와 reason code
- `fill_result`: 체결 결과
- `position_opened`: 포지션 생성과 손절가
- `position_exit_completed`: 손절/청산 결과
- `position_lifecycle_updated`: 포지션 상태 변화
- `recovery_attempt`: 자동 복구 시도
- `restart_detected`: 재기동 감지
- `recovery_completed`: 복구 완료
- `promotion_review_completed`: demo에서 live 승격 검토 결과

이 로그가 AI 성장의 원천 데이터다. 현재 코드가 즉시 모델 파라미터를 변경하지는 않지만, 어떤 조건에서 신호가 났고, 왜 차단됐고, 체결 후 결과가 어땠는지를 누적한다.

---

## 6. 무거래 진단

장시간 거래가 없을 때는 아래 API를 확인한다.

```bash
curl http://127.0.0.1:8000/learning/diagnostics
```

진단 상태:
- `NO_LEARNING_LOG`: 학습 로그가 없음
- `AUTO_TRADING_NOT_RUNNING`: 자동 운용 루프 기록이 없음
- `WAITING_FOR_SIGNAL`: 자동 운용 중이나 진입 조건 미충족
- `TRADE_BLOCKED_BY_RULES`: 신호/리스크/사이징 규칙이 진입 차단
- `FEE_ADJUSTED_EDGE_LIMIT`: 단타 예상 엣지가 왕복 수수료와 최소 순엣지를 넘지 못함
- `TRADES_FOUND`: 최근 로그에서 체결 확인

함께 확인할 필드:
- `last_auto_cycle`
- `last_signal`
- `last_fill`
- `auto_cycle_status_counts`
- `auto_cycle_blocked_reasons`
- `sizing_blocked_reasons`
- `signal_reason_codes`

---

## 7. 현재 한계

- 현재는 규칙 기반 AI이며, 별도 ML 모델을 온라인으로 재학습하지 않는다.
- 학습 로그는 쌓이지만 모델 가중치가 자동 변경되지는 않는다.
- demo 자동 운용은 서버 프로세스 메모리의 현재가 히스토리에 의존한다.
- live 자동 운용은 안전을 위해 별도 플래그 없이는 시작하지 않는다.
- 업비트 ticker만으로는 orderbook 상세 imbalance를 정확히 알 수 없어 자동 루프에서는 보수적 추정값을 사용한다.

---

## 8. 모델 학습 도입 계획

### 8.1 지금 당장 TensorFlow 학습을 켜지 않는 이유

현재는 체결/청산/차단 로그의 양과 라벨 품질을 먼저 안정화해야 한다. 충분한 결과 라벨 없이 TensorFlow 모델을 붙이면 과적합된 신호가 실거래에 들어갈 수 있다. 따라서 현재 단계에서는 데이터 준비도 진단만 구현한다.

준비도 API:

```bash
curl http://127.0.0.1:8000/learning/model-readiness
```

준비도 기본 기준:
- 전체 학습 이벤트 10,000개 이상
- 매매판단신호 이벤트 2,000개 이상
- 체결 이벤트 300개 이상
- 청산 결과 이벤트 100개 이상
- 차단된 자동 운용 사이클 300개 이상

### 8.2 학습 대상 후보

1. 진입 품질 모델
   - 입력: signal feature, regime, liquidity, spread, volatility
   - 라벨: 진입 후 validation window 내 기대 수익률 충족 여부

2. 손절 위험 모델
   - 입력: entry feature, stop_loss_pct, short volatility, orderbook imbalance
   - 라벨: stop loss 발생 여부와 발생 시간

3. 사이징 보정 모델
   - 입력: signal score, regime score, 최근 승률, drawdown
   - 라벨: 같은 조건의 기대 손익과 변동성

### 8.3 승격 게이트

모델이 자동매매 판단에 쓰이려면 아래 조건을 통과해야 한다.

- demo 데이터만 사용해 오프라인 학습
- train/validation/test 날짜 분리
- 규칙 기반 baseline보다 손실률이 낮아야 함
- max drawdown 악화 금지
- stop loss 실패 증가 금지
- 최소 14일 demo shadow mode 통과
- live 적용 시 첫 단계는 추천 점수 보조 역할만 수행

### 8.4 런타임 적용 원칙

- TensorFlow 학습은 서버 프로세스 안에서 실행하지 않는다.
- 모델 파일은 별도 산출물로 저장한다.
- live 자동매매는 규칙 기반 안전장치를 최종 게이트로 유지한다.
- 모델 예측값은 신호 강화/약화 보조 정보로만 먼저 사용한다.

---

## 9. 다음 개선 방향

- 학습 로그를 일 단위로 요약해 전략 품질 지표 생성
- JSONL을 Parquet 데이터셋으로 변환해 백테스트/모델 학습에 사용
- `ml` extra 기반 오프라인 학습 CLI 추가
- TensorFlow 모델 학습/평가 리포트 저장
- 무거래 시간이 길어질 때 텔레그램으로 원인 리포트 전송
- live 자동 운용 전 paper/demo 기준을 더 엄격하게 적용
- 실제 orderbook stream 기반 imbalance feature로 교체
- 손절 이후 재진입 차단과 자동 운용 루프를 더 강하게 연동
