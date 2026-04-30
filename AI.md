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

---

## 3. 자동 운용 흐름

서버가 시작되면 설정에 따라 자동 운용 루프가 동작한다.

기본 설정:
- `AUTO_TRADING_ENABLED=true`
- `AUTO_TRADING_LIVE_ENABLED=false`
- `AUTO_TRADING_INTERVAL_SEC=10.0`
- `AUTO_TRADING_MIN_HISTORY=6`

demo 모드에서는 자동 운용이 기본 활성화된다. live 모드는 `AUTO_TRADING_LIVE_ENABLED=true`를 명시해야 자동 운용이 시작된다.

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

### Sizing 판단
`SizingEngine`은 신호 세기와 국면을 바탕으로 매수 금액을 계산한다.

안전장치:
- 최소 현금 보유액 유지
- spread/slippage 초과 차단
- 현재가 0 이하 차단
- 1회 예상 손절 손실을 `MAX_DAILY_LOSS`의 25% 이내로 제한

---

## 5. 학습 로그 흐름

학습 로그 경로:

```text
logs/learning/learning.jsonl
```

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

## 8. 다음 개선 방향

- 학습 로그를 일 단위로 요약해 전략 품질 지표 생성
- JSONL을 Parquet 데이터셋으로 변환해 백테스트/모델 학습에 사용
- 무거래 시간이 길어질 때 텔레그램으로 원인 리포트 전송
- live 자동 운용 전 paper/demo 기준을 더 엄격하게 적용
- 실제 orderbook stream 기반 imbalance feature로 교체
- 손절 이후 재진입 차단과 자동 운용 루프를 더 강하게 연동
