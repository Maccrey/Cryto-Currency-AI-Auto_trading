# Tasklist.md

## 현재 진행 상황
  - ㅅ완료: 107개
  - 미완료: 30개
  - 전체: 137개
 
## 1. 작업 원칙
- 모든 구현은 TDD 순서를 따른다.
- 실패 테스트 없이 기능 구현 금지
- `demo/live + always-on learning` 구조를 깨는 변경 금지
- Git 커밋 메시지는 반드시 한국어
- 커밋 전에 테스트 통과 확인 필수

---

## 2. 아키텍처 개요
```text
[Upbit Public WS] -> [market-data] -> [signal-engine] -> [regime-engine] -> [sizing-engine]
                                                               |                |
                                                               v                v
                                                        [learning-log]     [risk-engine]
                                                                                 |
                                                                                 v
                                                           [demo/live executor] -> [portfolio]
                                                                                 |
                                                                                 v
                                                                           [dashboard]
                                                                                 |
                                                                                 v
                                                                          [telegram]
                                                                                 |
                                                                                 v
                                                                       [recovery orchestrator]
```

---

## 3. Phase 1 - 프로젝트 기반

### 설정 및 모드
- [x] [Fail] `TRADING_MODE`가 `demo` 또는 `live` 외의 값이면 앱이 실패해야 한다
- [x] [Fail] `LEARNING_ENABLED`가 false이면 앱이 시작되지 않아야 한다
- [x] [Code] pydantic settings 구현
- [x] [Code] mode validator 구현
- [x] [Refactor] settings loader 분리
- [ ] [Contract] ENV_SPEC.md와 코드 설정 스키마 일치

### 구조화 로깅
- [x] [Fail] 핵심 이벤트 로그가 JSON 구조로 저장되어야 한다
- [ ] [Code] structlog 설정
- [x] [Code] decision log writer 구현
- [ ] [Refactor] 공통 로그 필드 주입기 구현
- [ ] [Contract] decision log schema 문서화

### Git / TDD 규칙
- [x] [Code] pre-commit에 테스트/린트 훅 추가
- [x] [Code] 커밋 템플릿에 한국어 메시지 규칙 명시
- [x] [Contract] README와 CODEX_HARNESS에 커밋 정책 반영

---

## 4. Phase 2 - 업비트 연동

### 인증 / REST
- [x] [Fail] query가 있는 요청에 query_hash가 누락되면 테스트가 실패해야 한다
- [x] [Code] JWT 인증 모듈 구현
- [x] [Code] REST client 구현
- [x] [Refactor] 인증/전송 레이어 분리
- [x] [Contract] Upbit client interface 고정

### WebSocket
- [x] [Fail] public ws 재연결 후 구독이 복원되어야 한다
- [x] [Fail] private ws 재연결 후 상태 동기화가 가능해야 한다
- [x] [Code] public ws client 구현
- [x] [Code] private ws client 구현
- [x] [Refactor] reconnect manager 분리
- [x] [Contract] market snapshot event schema 고정

### 포트폴리오 초기화
- [x] [Fail] 시작 시 현금/보유 코인 동기화 실패하면 거래를 시작하면 안 된다
- [x] [Code] portfolio sync 구현
- [x] [Refactor] sync service 분리
- [x] [Contract] portfolio_state schema 고정

---

## 5. Phase 3 - 전략 엔진

### 신호 생성
- [x] [Fail] 급등 조건 충족 시 strong 이상 신호가 생성되어야 한다
- [x] [Fail] 저유동성 구간에서는 신호가 차단되어야 한다
- [x] [Code] feature 계산 구현
- [x] [Code] signal engine 구현
- [ ] [Refactor] reason code 생성기 분리
- [x] [Contract] signal schema 고정

### 국면 평가
- [x] [Fail] risk_off 국면에서는 size가 줄어야 한다
- [x] [Code] regime engine 구현
- [ ] [Refactor] regime score 계산 공통화
- [x] [Contract] regime snapshot schema 고정

### 비중 계산
- [x] [Fail] strong 신호와 충분한 현금이 있으면 설정 비율대로 buy amount가 계산되어야 한다
- [x] [Fail] reserve cash 이하로는 매수 금액이 계산되면 안 된다
- [x] [Fail] spread/slippage 초과 시 주문이 차단되어야 한다
- [x] [Code] sizing engine 구현
- [ ] [Refactor] buy/sell sizing policy 분리
- [x] [Contract] sizing result schema 고정

---

## 6. Phase 4 - 손절 / 리스크

### 손절가 주입
- [x] [Fail] 매수 체결 시 entry_price와 stop_loss_price가 저장되어야 한다
- [x] [Fail] 매수 알림에 손절가가 포함되어야 한다
- [x] [Code] stop loss injector 구현
- [x] [Refactor] signal strength별 손절 비율 정책 분리
- [x] [Contract] positions schema 반영

### 가격 손절
- [x] [Fail] 현재가가 stop_loss_price 이하가 되면 손절 주문이 생성되어야 한다
- [x] [Code] hard stop monitor 구현
- [ ] [Refactor] 일반 매도와 손절 매도 실행기 분리
- [x] [Contract] stop loss event schema 고정

### 기대 불일치 손절
- [x] [Fail] validation window 내 최소 기대 상승률 미달이면 손절 또는 축소 청산이 발생해야 한다
- [ ] [Fail] 손절 사유가 DB와 알림에 기록되어야 한다
- [x] [Code] post-entry validator 구현
- [ ] [Refactor] expectation failure ruleset 분리
- [x] [Contract] risk event codes 고정

### 재진입 차단
- [x] [Fail] 손절 직후 재진입 block 시간 내에는 같은 종목 재진입이 거절되어야 한다
- [x] [Code] reentry blocker 구현
- [ ] [Refactor] cooldown / reentry policy 분리

---

## 7. Phase 5 - 실행기

### demo 실행기
- [x] [Fail] `demo` 모드에서 실주문 API가 호출되면 테스트가 실패해야 한다
- [x] [Code] virtual order executor 구현
- [x] [Code] virtual fill simulator 구현
- [ ] [Refactor] execution interface 추상화
- [x] [Contract] order intent schema 고정

### live 실행기
- [x] [Fail] `live` 모드에서만 실주문이 허용되어야 한다
- [x] [Fail] SAFE_MODE 상태에서는 주문이 차단되어야 한다
- [x] [Code] live executor 구현
- [ ] [Code] precheck / orders/test 연동 구현
- [x] [Refactor] executor factory 구현
- [ ] [Contract] live order state machine 문서화

---

## 8. Phase 6 - 텔레그램

### 체결 알림
- [x] [Fail] 매수/매도/손절 체결 시 텔레그램 메시지가 전송되어야 한다
- [x] [Code] notifier 구현
- [ ] [Refactor] 메시지 템플릿 분리
- [x] [Contract] message payload schema 고정

### 재기동 알림
- [x] [Fail] 재기동 후 복구 완료 시 텔레그램으로 재기동 정보가 전송되어야 한다
- [x] [Code] restart notifier 구현
- [ ] [Refactor] restart message builder 분리

### 승격 알림
- [x] [Fail] 승격 가능 상태가 되면 PROMOTION READY 메시지가 전송되어야 한다
- [x] [Fail] 실거래 활성화 시 LIVE MODE ENABLED 메시지가 전송되어야 한다
- [x] [Code] promotion notifier 구현

---

## 9. Phase 7 - 대시보드

### 차트 마커
- [x] [Fail] 매수 마커는 파란색이어야 한다
- [x] [Fail] 일반 매도 마커는 빨간색이어야 한다
- [x] [Fail] 손절 매도 마커는 노란색이어야 한다
- [x] [Fail] 각 마커 툴팁이 요구 필드를 모두 포함해야 한다
- [x] [Code] marker renderer 구현
- [ ] [Refactor] tooltip schema 분리
- [x] [Contract] dashboard event payload schema 고정

### 손절 라인
- [x] [Fail] 활성 포지션 동안 stop_loss_price 라인이 표시되어야 한다
- [x] [Fail] 포지션 종료 시 손절 라인이 제거되어야 한다
- [x] [Code] stop loss overlay 구현

### 하단 패널
- [x] [Fail] 보유 코인, 보유 현금, 손익, 카운트, 모드, 학습 상태가 표시되어야 한다
- [x] [Code] summary panel API 구현
- [ ] [Refactor] chart feed / summary feed 분리

---

## 10. Phase 8 - 학습 파이프라인

### 항상 켜진 학습 로그
- [x] [Fail] 어떤 모드에서도 decision log가 저장되어야 한다
- [x] [Fail] fill / stop loss / restart / promotion 이벤트도 저장되어야 한다
- [x] [Code] learning service 구현
- [x] [Code] JSONL exporter 구현
- [ ] [Refactor] event serializer 분리
- [x] [Contract] learning event schema 고정

### 데이터셋 변환
- [x] [Fail] 일별 JSONL을 Parquet 데이터셋으로 변환할 수 있어야 한다
- [x] [Code] dataset exporter 구현
- [ ] [Refactor] raw log / dataset pipeline 분리

### replay 테스트
- [x] [Fail] 과거 tick fixture 재생으로 전략 결과를 검증할 수 있어야 한다
- [x] [Code] replay harness 구현
- [x] [Refactor] fixture loader 분리

---

## 11. Phase 9 - 재기동 복구

### recovery orchestrator
- [x] [Fail] 재기동 시 restart event가 저장되어야 한다
- [x] [Fail] 잔고 sync 전에 거래가 시작되면 안 된다
- [x] [Fail] 오픈오더 reconcile 실패 시 SAFE_MODE 유지해야 한다
- [x] [Code] recovery orchestrator 구현
- [ ] [Code] restart state persistence 구현
- [x] [Refactor] boot sequence 단계 분리
- [ ] [Contract] RUNBOOK과 절차 일치

### HARD_STOP
- [x] [Fail] 연속 재기동 횟수가 기준을 넘으면 HARD_STOP 상태여야 한다
- [x] [Code] restart counter 구현
- [x] [Code] HARD_STOP alert 구현

---

## 12. Phase 10 - 데모 승격

### 승격 평가기
- [x] [Fail] 데모 운영 최소 기간 미달이면 승격이 거부되어야 한다
- [x] [Fail] PF 또는 MDD 기준 미달이면 거부되어야 한다
- [x] [Fail] 손절 오작동이 있으면 거부되어야 한다
- [x] [Code] promotion evaluator 구현
- [ ] [Refactor] metrics aggregator 분리
- [ ] [Contract] promotion_evaluations schema 고정

### 승인 워크플로
- [x] [Fail] 승인 전 live 활성화가 되면 안 된다
- [x] [Code] approval flow 구현
- [x] [Code] SAFE_MODE live entry 구현

---

## 13. 문서 동기화 체크
- [ ] PRD 변경 시 Tasklist 업데이트
- [ ] 전략 변경 시 STRATEGY_SPEC 업데이트
- [ ] .env 변경 시 ENV_SPEC 업데이트
- [ ] 운영 절차 변경 시 RUNBOOK 업데이트
- [ ] Codex 작업 규칙 변경 시 CODEX_HARNESS 업데이트

---

## 14. Git / 커밋 체크리스트
- [ ] 실패 테스트 먼저 작성
- [x] 테스트 통과 확인
- [x] 문서 업데이트 반영
- [x] 한국어 커밋 메시지 작성
- [x] 한 기능 단위로 커밋 분리

### 권장 커밋 예시
- `초기 자산 동기화와 포트폴리오 스키마 추가`
- `매수 체결 시 손절가 주입 로직 구현`
- `기대 불일치 손절 판정과 텔레그램 알림 추가`
- `차트 마커 색상 및 툴팁 렌더링 구현`
- `데모 승격 평가기와 승인 워크플로 추가`
