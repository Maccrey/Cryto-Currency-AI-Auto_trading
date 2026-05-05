# Tasklist.md

## 현재 진행 상황
  - 완료: 224개
  - 미완료: 0개
  - 전체: 224개
 
## 1. 작업 원칙
- 모든 구현은 TDD 순서를 따른다.
- 실패 테스트 없이 기능 구현 금지
- `demo/live + always-on learning` 구조를 깨는 변경 금지
- Git 커밋 메시지는 반드시 한국어
- 구현 완료 후 테스트 통과를 확인하고 한국어 커밋을 생성해야 한다
- 커밋 전에 테스트 통과 확인 필수
- 룰 변경도 실패 테스트와 replay 테스트를 먼저 통과해야 한다
- 룰 변경안은 demo 선반영 후 승인받아 live에 반영한다
- main 직접 반영 금지, 브랜치 기반 검토 필수

---

## 2. 아키텍처 개요
```text
[Upbit Public WS] -> [market-data] -> [signal-engine] -> [regime-engine] -> [sizing-engine]
                                                               |                |
                                                               v                v
                                                        [learning-log]     [risk-engine]
                                                               |
                                                               v
                                                    [Codex rule review loop]
                                                               |
                                                               v
                                                [replay] -> [demo apply] -> [live approval]
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
- [x] [Fail] 투자성향이 단타/단기/중기/장기 프로필 기본값을 주입해야 한다
- [x] [Code] pydantic settings 구현
- [x] [Code] mode validator 구현
- [x] [Code] trading profile registry 구현
- [x] [Code] 한 줄 시작 스크립트와 설정창 자동 열기 구현
- [x] [Code] macOS launchd KeepAlive 백그라운드 실행 등록 구현
- [x] [Code] 설정 저장 후 준비 조건을 만족할 때만 트레이딩 서버 시작 버튼 표시
- [x] [Code] demo 필수값과 live 업비트 API 키 기준 시작 가능 여부 검증
- [x] [Code] 설정 화면 필수 입력 항목 표시
- [x] [Refactor] settings loader 분리
- [x] [Contract] ENV_SPEC.md와 코드 설정 스키마 일치

### 구조화 로깅
- [x] [Fail] 핵심 이벤트 로그가 JSON 구조로 저장되어야 한다
- [x] [Code] structlog 설정
- [x] [Code] decision log writer 구현
- [x] [Refactor] 공통 로그 필드 주입기 구현
- [x] [Contract] decision log schema 문서화

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
- [x] [Fail] 초단기 역방향 모멘텀에서는 진입 신호가 차단되어야 한다
- [x] [Fail] 과도한 단기 변동성에서는 진입 신호가 차단되어야 한다
- [x] [Code] feature 계산 구현
- [x] [Code] signal engine 구현
- [x] [Refactor] reason code 생성기 분리
- [x] [Contract] signal schema 고정

### 국면 평가
- [x] [Fail] risk_off 국면에서는 size가 줄어야 한다
- [x] [Code] regime engine 구현
- [x] [Refactor] regime score 계산 공통화
- [x] [Contract] regime snapshot schema 고정

### 비중 계산
- [x] [Fail] strong 신호와 충분한 현금이 있으면 설정 비율대로 buy amount가 계산되어야 한다
- [x] [Fail] reserve cash 이하로는 매수 금액이 계산되면 안 된다
- [x] [Fail] spread/slippage 초과 시 주문이 차단되어야 한다
- [x] [Fail] 현재가가 0 이하이면 수량 계산 전에 주문이 차단되어야 한다
- [x] [Fail] 예상 손절 손실이 1회 리스크 예산을 넘으면 매수 금액이 자동 축소되어야 한다
- [x] [Fail] 단타 진입 예상 엣지가 왕복 수수료와 최소 순엣지를 넘지 못하면 차단되어야 한다
- [x] [Fail] 업비트 KRW 마켓 5,000원 미만 주문은 차단되어야 한다
- [x] [Fail] 단타 medium 신호는 완화된 엣지 버퍼로 demo 진입할 수 있어야 한다
- [x] [Code] sizing engine 구현
- [x] [Code] 업비트 KRW 마켓 최소 주문 가능 금액 5,000원 룰 구현
- [x] [Code] 업비트 KRW 수수료 0.05% 기준 단타 순엣지 게이트 구현
- [x] [Code] 최근 학습 로그 점수 분포를 반영한 signal level 기준 완화
- [x] [Code] medium 단타 진입 수수료 보정 엣지 버퍼 완화
- [x] [Refactor] buy/sell sizing policy 분리
- [x] [Contract] 단타 수수료/순엣지 환경 변수와 문서 반영
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
- [x] [Refactor] 일반 매도와 손절 매도 실행기 분리
- [x] [Contract] stop loss event schema 고정

### 기대 불일치 손절
- [x] [Fail] validation window 내 최소 기대 상승률 미달이면 손절 또는 축소 청산이 발생해야 한다
- [x] [Fail] 손절 사유가 DB와 알림에 기록되어야 한다
- [x] [Fail] 5,000원 미만 매도와 dust 잔량을 만드는 반복 부분 손절은 차단/전량청산으로 보정되어야 한다
- [x] [Code] post-entry validator 구현
- [x] [Code] 보합권 소프트 손절 보류와 dust 반복 매도 방지 룰 구현
- [x] [Refactor] expectation failure ruleset 분리
- [x] [Contract] risk event codes 고정

### 재진입 차단
- [x] [Fail] 손절 직후 재진입 block 시간 내에는 같은 종목 재진입이 거절되어야 한다
- [x] [Code] reentry blocker 구현
- [x] [Refactor] cooldown / reentry policy 분리

---

## 7. Phase 5 - 실행기

### demo 실행기
- [x] [Fail] `demo` 모드에서 실주문 API가 호출되면 테스트가 실패해야 한다
- [x] [Fail] demo 서버 기동 후 자동 운용 루프가 현재가 히스토리를 쌓아야 한다
- [x] [Fail] 충분한 히스토리와 진입 신호가 있으면 demo 자동 체결이 실행되어야 한다
- [x] [Fail] demo 체결 후 가상 현금/코인 잔고가 갱신되어야 한다
- [x] [Code] virtual order executor 구현
- [x] [Code] virtual fill simulator 구현
- [x] [Code] auto trading service 구현
- [x] [Code] demo 자동 운용 서비스의 가상 포트폴리오 체결 반영 구현
- [x] [Refactor] execution interface 추상화
- [x] [Contract] order intent schema 고정

### live 실행기
- [x] [Fail] `live` 모드에서만 실주문이 허용되어야 한다
- [x] [Fail] SAFE_MODE 상태에서는 주문이 차단되어야 한다
- [x] [Fail] live 자동 운용은 명시 플래그 없이는 시작되면 안 된다
- [x] [Code] live executor 구현
- [x] [Code] precheck / orders/test 연동 구현
- [x] [Refactor] executor factory 구현
- [x] [Contract] live order state machine 문서화

---

## 8. Phase 6 - 텔레그램

### 체결 알림
- [x] [Fail] 매수/매도/손절 체결 시 텔레그램 메시지가 전송되어야 한다
- [x] [Fail] 텔레그램 등록 시 06:00~24:00 운용 시간대에 현재 트레이딩 리포트가 중복 없이 발송되어야 한다
- [x] [Fail] 06:00에는 전날 트레이딩/학습 결과 리포트가 함께 발송되어야 한다
- [x] [Fail] 매도 알림에는 매수가 대비 손익과 수익률이 포함되어야 한다
- [x] [Fail] 정기 리포트와 체결 알림은 한국어 문장 형태여야 한다
- [x] [Code] notifier 구현
- [x] [Code] Telegram Bot API HTTP gateway 구현
- [x] [Code] 정기 트레이딩 리포트 스케줄러 구현
- [x] [Code] 서버 시작 시 설정/대시보드 접속 주소 텔레그램 알림 구현
- [x] [Refactor] 메시지 템플릿 분리
- [x] [Contract] message payload schema 고정

### 재기동 알림
- [x] [Fail] 재기동 후 복구 완료 시 텔레그램으로 재기동 정보가 전송되어야 한다
- [x] [Code] restart notifier 구현
- [x] [Refactor] restart message builder 분리

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
- [x] [Refactor] tooltip schema 분리
- [x] [Contract] dashboard event payload schema 고정

### 손절 라인
- [x] [Fail] 활성 포지션 동안 stop_loss_price 라인이 표시되어야 한다
- [x] [Fail] 포지션 종료 시 손절 라인이 제거되어야 한다
- [x] [Code] stop loss overlay 구현

### 하단 패널
- [x] [Fail] 보유 코인, 보유 현금, 손익, 카운트, 모드, 학습 상태가 표시되어야 한다
- [x] [Fail] demo 재기동 후 과거 학습 로그의 체결이 현재 투자금/최근 체결에 섞이지 않아야 한다
- [x] [Code] summary panel API 구현
- [x] [Code] demo 체결 원장 기반 대시보드 투자금/현금/코인 수량 표시
- [x] [Code] 학습 로그 fill_result 기반 실행 원장 seed 구현
- [x] [Refactor] chart feed / summary feed 분리

### 외부 접속
- [x] [Fail] 설정과 대시보드는 다른 기기에서 LAN IP 주소로 접속할 수 있어야 한다
- [x] [Code] dashboard host/port를 `0.0.0.0:8080` 기본값으로 launchd에 반영
- [x] [Code] LAN IP 기반 설정/대시보드 URL 생성 유틸 구현
- [x] [Contract] START/RUNBOOK/ENV_SPEC에 외부 접속 절차 반영

---

## 10. Phase 8 - 학습 파이프라인

### 항상 켜진 학습 로그
- [x] [Fail] 어떤 모드에서도 decision log가 저장되어야 한다
- [x] [Fail] fill / stop loss / restart / promotion 이벤트도 저장되어야 한다
- [x] [Fail] 자동 운용 사이클과 무거래 차단 사유가 학습 로그에 저장되어야 한다
- [x] [Fail] 학습 로그에서 무거래 원인을 진단할 수 있어야 한다
- [x] [Fail] 투자성향별 학습 로그가 별도 경로에 저장되어야 한다
- [x] [Fail] 설정 화면에서 현재 투자성향 학습 데이터를 리셋할 수 있어야 한다
- [x] [Code] learning service 구현
- [x] [Code] 학습 로그 archive 후 reset 서비스 구현
- [x] [Code] 설정 화면 학습 데이터 리셋 API/UI 구현
- [x] [Code] learning event에 trading_profile context 주입
- [x] [Code] learning diagnostics 구현
- [x] [Code] JSONL exporter 구현
- [x] [Refactor] event serializer 분리
- [x] [Contract] 투자성향별 학습 로그 경로 문서화
- [x] [Contract] learning event schema 고정

### 데이터셋 변환
- [x] [Fail] 일별 JSONL을 Parquet 데이터셋으로 변환할 수 있어야 한다
- [x] [Code] dataset exporter 구현
- [x] [Refactor] raw log / dataset pipeline 분리

### 모델 학습 준비도
- [x] [Fail] 학습 로그가 모델 학습 기준을 충족하는지 진단할 수 있어야 한다
- [x] [Code] model training readiness service 구현
- [x] [Code] `/learning/model-readiness` API 구현
- [x] [Contract] TensorFlow 계열 학습 패키지는 선택 의존성 `ml`로 분리

### Codex 룰 개선 파이프라인
- [x] [Fail] 룰 리뷰 표본 수가 부족하면 변경안 생성이 차단되어야 한다
- [x] [Fail] 손절 표본 수가 부족하면 손절 파라미터 변경안이 차단되어야 한다
- [x] [Fail] 한 번에 허용 개수보다 많은 파라미터 변경은 거부되어야 한다
- [x] [Fail] replay 결과 없는 룰 변경안은 demo 적용이 거부되어야 한다
- [x] [Fail] demo 적용과 수동 승인 없이 live 적용이 거부되어야 한다
- [x] [Code] 룰 분석 리포트 생성기 구현
- [x] [Code] Codex 룰 변경안 생성기 구현
- [x] [Code] replay 기반 변경 검증기 구현
- [x] [Code] demo 적용 워크플로 구현
- [x] [Code] live 승인 워크플로 구현
- [x] [Code] `/api/v1/rules/review` API 구현
- [x] [Code] `/api/v1/rules/proposals` API 구현
- [x] [Code] `/api/v1/rules/proposals/{id}/apply-demo` API 구현
- [x] [Code] `/api/v1/rules/proposals/{id}/approve-live` API 구현
- [x] [Code] `/api/v1/rules/proposals/{id}` API 구현
- [x] [Code] 설정 화면 룰 개선 버튼과 결과 패널 구현
- [x] [Contract] 룰 변경 허용 파일 목록 문서화
- [x] [Contract] replay/demo/live 승인 기준 문서화
- [x] [Fail] 룰 변경 히스토리가 없으면 live 승인 적용이 거부되어야 한다
- [x] [Fail] 히스토리에는 기존 룰 snapshot, 새 룰 snapshot, 변경 사유, 기대 효과, 알려진 리스크가 저장되어야 한다
- [x] [Fail] 코인/투자성향별 `rule-change-history.jsonl`이 append-only로 누적되어야 한다
- [x] [Fail] 과거 동일 파라미터 변경 실패 이력이 있으면 proposal에 경고가 표시되어야 한다
- [x] [Fail] 룰 변경 커밋 해시는 기존 히스토리 수정 없이 append-only 이벤트로 연결되어야 한다
- [x] [Code] 룰 변경 히스토리 원장 writer 구현
- [x] [Code] proposal 생성/demo 적용/live 승인 시 history event 기록
- [x] [Code] 룰 변경 히스토리 조회 API 구현
- [x] [Code] 설정 화면과 대시보드에 룰 변경 히스토리 패널 구현
- [x] [Code] 룰 변경 proposal 커밋 해시 연결 API 구현
- [x] [Code] 룰 변경 proposal 커밋 해시 연결 CLI 구현
- [x] [Code] 설정 화면과 대시보드 히스토리 패널에 커밋 해시 표시
- [x] [Contract] 룰 변경 히스토리 schema 문서화

### TensorFlow 오프라인 학습 계획
- [x] [Fail] 학습 데이터가 부족하면 TensorFlow 학습 CLI가 실행을 거부해야 한다
- [x] [Fail] train/validation/test 기간 분리가 없으면 학습이 실패해야 한다
- [x] [Fail] baseline보다 손실률이 나쁜 모델은 승격될 수 없어야 한다
- [x] [Code] `ml` extra 설치 환경에서 TensorFlow trainer CLI 구현
- [x] [Code] 진입 품질 모델 학습 파이프라인 구현
- [x] [Code] 손절 위험 모델 학습 파이프라인 구현
- [x] [Code] 모델 평가 리포트 저장 구현
- [x] [Code] shadow mode 예측 로그 구현
- [x] [Refactor] feature schema와 model input schema 분리
- [x] [Contract] 모델 아티팩트 저장 경로와 버전 규칙 문서화
- [x] [Contract] live 적용 전 demo shadow mode 기준 문서화
- [x] [Contract] TensorFlow 모델은 규칙 기반 리스크 게이트를 우회할 수 없도록 명시

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
- [x] [Fail] 일시적인 잔고 sync 실패는 자동 재시도 후 복구되어야 한다
- [x] [Fail] 일시적인 오픈오더 reconcile 실패는 자동 재시도 후 복구되어야 한다
- [x] [Code] recovery orchestrator 구현
- [x] [Code] 단계별 자동 복구 retry policy 구현
- [x] [Code] restart state persistence 구현
- [x] [Refactor] boot sequence 단계 분리
- [x] [Contract] RUNBOOK과 절차 일치

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
- [x] [Refactor] metrics aggregator 분리
- [x] [Contract] promotion_evaluations schema 고정

### 승인 워크플로
- [x] [Fail] 승인 전 live 활성화가 되면 안 된다
- [x] [Code] approval flow 구현
- [x] [Code] SAFE_MODE live entry 구현

---

## 13. 문서 동기화 체크
- [x] PRD 변경 시 Tasklist 업데이트
- [x] 전략 변경 시 STRATEGY_SPEC 업데이트
- [x] .env 변경 시 ENV_SPEC 업데이트
- [x] 운영 절차 변경 시 RUNBOOK 업데이트
- [x] Codex 작업 규칙 변경 시 CODEX_HARNESS 업데이트

---

## 14. Git / 커밋 체크리스트
- [x] 실패 테스트 먼저 작성
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
