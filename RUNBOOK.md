# RUNBOOK.md

## 1. 문서 목적
이 문서는 업비트 자동매매 시스템의 운영 절차, 장애 대응, 재기동 복구, 모드 전환, 승격 점검 절차를 정의한다.

---

## 2. 운영 모드

### demo
- 실제 주문 금지
- 가상 주문/가상 체결
- 전략 검증용
- 학습 로그 ON
- 텔레그램/대시보드/재기동 테스트 포함

### live
- 실주문 허용
- 부팅 직후 기본 SAFE_MODE
- 학습 로그 ON
- 승인 또는 정책 충족 후 활성화

---

## 3. 부팅 절차
1. 프로세스 시작
2. `.env` 및 secret 로드
3. 설정 검증
4. restart event 생성
5. learning service 시작
6. public/private stream 초기화
7. 잔고 및 보유 자산 동기화
8. 오픈오더 reconcile
9. 손절 상태 복원
10. SAFE_MODE 진입
11. 텔레그램으로 앱 서버 시작 안내와 설정/대시보드 접속 주소 전송
12. health check 통과 확인
13. 설정 화면의 `서버 시작` 버튼 대기
14. 버튼 실행 후 demo 또는 live 자동 운용 루프 시작

---

## 4. 재기동 자동 복구

### 트리거
- 프로세스 비정상 종료
- 치명적 예외
- 컨테이너 재시작
- systemd 재기동

### 재기동 순서
```text
프로세스 종료 감지
-> supervisor/systemd/docker restart
-> 앱 재부팅
-> restart event 저장
-> restart state 파일 갱신
-> 포트폴리오 sync
-> 오픈오더 reconcile
-> 손절 상태 복원
-> SAFE_MODE 유지
-> 텔레그램 재기동 알림 전송
-> health 확인
-> 운영 재개
```

### 필수 확인 항목
- 현재 보유 현금
- 현재 보유 코인 수량
- 미체결 주문 존재 여부
- 손절가 복원 여부
- restart state의 마지막 `recovery_completed` 여부
- learning service 작동 여부
- dashboard 연결 상태
- telegram 전송 상태

---

## 5. SAFE_MODE

### SAFE_MODE 진입 조건
- 재기동 직후
- portfolio sync 실패
- 오픈오더 reconcile 실패
- private ws 불안정
- 연속 오류 증가
- 일일 손실 한도 초과
- 수동 운영자 강제 전환

### SAFE_MODE 상태에서 허용되는 것
- 시세 수집
- 대시보드 갱신
- 텔레그램 알림
- 학습 로그 저장
- 상태 동기화
- 수동 점검

### SAFE_MODE 상태에서 금지되는 것
- 신규 live 주문
- 승격 상태 변경
- 자동 재진입

---

## 6. HARD_STOP

### 진입 조건
- 연속 재기동 횟수 초과
- 복구 반복 실패
- 상태 불일치 지속
- 치명적 오류가 반복 발생

### HARD_STOP 상태 조치
- 신규 주문 전면 차단
- 텔레그램 치명적 알림 전송
- 운영자 개입 전까지 유지
- dashboard에 HARD_STOP 배지 표시

---

## 7. 손절 운영 절차

### 하드 손절
조건:
- `current_price <= stop_loss_price`

조치:
- 즉시 손절 실행
- 손절 사유 `STOP_LOSS_PRICE_HIT`
- 텔레그램 손절 알림
- 노란 마커 표시
- reentry block 시작

### 소프트 손절
조건 예:
- validation window 경과
- 최소 기대 상승률 미달
- momentum 약화
- orderbook imbalance 역전

조치:
- 부분 청산 또는 전량 청산
- 손절 사유 기록
- 텔레그램 손절 알림
- 노란 마커 표시

---

## 8. 텔레그램 메시지 운영

### 반드시 테스트해야 하는 메시지
- BUY_EXECUTED
- SELL_EXECUTED
- STOP_LOSS_EXECUTED
- RESTARTED
- PROMOTION_READY
- LIVE_MODE_ENABLED
- ERROR_CRITICAL

### 재기동 메시지 점검 항목
- 서비스명 포함 여부
- 시각 포함 여부
- 원인 포함 여부
- sync 결과 포함 여부
- SAFE_MODE 상태 포함 여부
- 보유 현금/코인 포함 여부
- 설정창/대시보드 접속 주소 포함 여부
- 자동 트레이딩이 아직 시작되지 않았다는 안내 포함 여부

### 정기/체결 메시지 점검 항목
- 1시간 정기 리포트가 한국어 문장 형태인지 확인
- 매수/매도/손절 체결 알림이 한국어 문장 형태인지 확인
- 매도 알림에 매수가 대비 손익 금액과 수익률이 포함되는지 확인

---

## 9. demo 운영 절차
1. `TRADING_MODE=demo`
2. 앱 시작
3. 설정 화면에서 필수값 저장
4. `서버 시작` 버튼 표시 확인
5. `서버 시작` 버튼 실행
6. 가상 체결 경로 확인
7. 텔레그램 메시지 확인
8. 손절 테스트
9. 대시보드 마커 표시 확인
10. 구조화 로그 적재 확인
11. 승격 평가 지표 축적

### demo 점검 체크리스트
- [ ] 실주문 0건
- [ ] decision logs 정상 저장
- [ ] 가상 체결 정상 반영
- [ ] 대시보드 투자금/현금/코인 수량이 가상 체결 후 갱신
- [ ] 재기동 후 최근 체결이 학습 로그 기반으로 복원
- [ ] 손절 알림 정상
- [ ] 재기동 알림 정상
- [ ] 대시보드 정합성 정상

---

## 10. live 운영 절차
1. 승격 기준 충족 확인
2. 승인 상태 확인
3. `TRADING_MODE=live`
4. 업비트 API 키 저장 확인
5. 설정 화면의 `서버 시작` 버튼 표시 확인
6. 부팅 후 SAFE_MODE 진입
7. 상태 복구 확인
8. 소액/제한된 상태로 활성화
9. 실주문 경로 모니터링
10. 텔레그램 및 대시보드 정합성 확인

### live 시작 전 체크리스트
- [ ] demo 최소 기간 충족
- [ ] 최소 거래 수 충족
- [ ] PF 기준 충족
- [ ] MDD 기준 충족
- [ ] 손절 오작동 0건
- [ ] 재기동 복구 성공률 기준 충족
- [ ] 텔레그램 성공률 기준 충족
- [ ] 수동 승인 완료 또는 자동 승격 허용

### live order state machine
```text
order_intent
-> LIVE_MODE_REQUIRED 검사
-> SAFE_MODE_ACTIVE 검사
-> HARD_STOP_ACTIVE 검사
-> /v1/orders/test precheck
-> place_order
-> wait | done | cancel | blocked
```

차단 사유는 `LIVE_MODE_REQUIRED`, `SAFE_MODE_ACTIVE`, `HARD_STOP_ACTIVE`, 또는 `/v1/orders/test` 응답의 `reason` 값을 사용한다.

---

## 11. 승격 평가 운영

### 평가 지표
- demo_days
- total_trades
- win_rate
- profit_factor
- max_drawdown
- stoploss_failures
- recovery_success_rate
- telegram_success_rate

### 평가 결과 상태
- NOT_READY
- READY_FOR_REVIEW
- APPROVED
- REJECTED

### 권장 정책
- 기본은 수동 승인
- 자동 승격을 쓰더라도 SAFE_MODE로 진입 후 활성화
- 룰 변경이 발생하면 승격 평가를 다시 실행한다.
- live 운영 중 룰 변경은 즉시 반영하지 않고 demo 검증으로 되돌린다.
- replay와 demo 지표가 통과한 변경안만 live 승인 대상으로 올린다.

---

## 12. 룰 개선 운영 절차

설정 화면의 룰 변경 관련 버튼은 즉시 반영 버튼이 아니라 **룰 개선 파이프라인 시작 버튼**이다.

### 기본 흐름
```text
룰 개선 분석 실행
-> 룰 변경안 생성
-> replay 검증
-> demo 적용
-> demo 지표 확인
-> live 승인 적용
```

### 버튼별 의미
- `룰 개선 분석 실행`: 최근 `RULE_REVIEW_WINDOW_DAYS` 학습 로그를 집계한다.
- `룰 변경안 생성`: 거래 수와 손절 수 기준 충족 시 Codex 변경안을 만든다.
- `replay 검증`: 변경안을 과거 tick fixture로 재생해 신호 결과와 차단 결과를 확인한다.
- `demo 적용`: replay 결과가 있는 변경안만 demo에 적용한다.
- `live 승인 적용`: demo 검증 통과와 수동 승인 후 live 반영한다.

손절률은 투자성향별 고정값이다. 단타/단기 -3%, 중기 -5%, 장기 -10%를 사용하며, 룰 변경안 생성이나 live 승인 과정에서 `STOP_LOSS_*`, `stop_loss_pct`, `stop_loss_price`, `fixed_stop_loss_pct` 변경은 금지한다.

### 결과 패널 필수 정보
- 분석 대상 기간
- 거래 수
- 손절 수
- 주요 손실 원인
- 온체인/ETF 외부 컨텍스트 요약
- Codex 제안 변경 항목
- replay 결과
- 승인 필요 여부
- 변경 히스토리 기록 여부

룰 개선 review/proposal 상태는 현재 코인/투자성향 학습 로그 디렉터리의 `rule-review-state.json`에 저장한다. 앱 재기동 후에도 proposal 상세 조회, replay 결과, demo 적용 여부, 승인 여부를 이어서 확인할 수 있어야 한다.
대시보드와 설정 화면은 `GET /api/v1/rules/proposals`로 최신 proposal을 불러와 재기동 후에도 마지막 룰 개선 상태를 먼저 표시한다.

### 룰 변경 히스토리 운영
룰 변경은 현재 상태만 저장하면 안 된다. 운영자는 시간이 지난 뒤에도 “왜 그 룰을 바꿨는지”, “그 변경이 replay/demo/live에서 어떤 결과를 냈는지”, “같은 실수를 반복하고 있는지”를 확인할 수 있어야 한다.

필수 히스토리 파일:
- XRP: `LEARNING_LOG_DIR/<TRADING_PROFILE>/rule-change-history.jsonl`
- 그 외 코인: `LEARNING_LOG_DIR/<TRADE_COIN>/<TRADING_PROFILE>/rule-change-history.jsonl`

각 룰 변경 이력에는 아래를 남긴다.
- 기존 룰 snapshot
- 새 룰 proposal snapshot
- 바뀐 파라미터와 변경폭
- 변경 근거가 된 학습 로그 기간, 거래 수, 손절 수, 손실/차단 원인
- 온체인/ETF 상태 분포와 평균 학습 가중치
- 기대 효과와 알려진 리스크
- replay 결과
- demo 적용 결과와 관찰 지표
- 승인자, 승인 시각, 적용 대상
- 한국어 커밋 메시지와 commit hash

이 파일은 append-only 원장이다. 기존 행을 수정하지 않고, 오류가 있으면 correction 이벤트를 추가한다. live 승인 전 운영자는 동일 파라미터의 과거 변경 이력과 실패 이력을 확인한다.

### 운영 금지 사항
- replay 테스트 없는 룰 변경 금지
- demo 적용 없는 live 반영 금지
- 수동 승인 없는 live 반영 금지
- 룰 변경 히스토리 기록 없는 live 반영 금지
- main 직접 반영 금지
- 한국어 커밋 없는 변경 반영 금지

---

## 13. 로그 / 데이터셋 운영

### 항상 저장되는 로그
- market_tick
- signal_generated
- sizing_decision
- order_intent
- fill_result
- stop_loss_triggered
- restart_detected
- recovery_completed
- promotion_evaluated

### decision log schema
```json
{
  "event_name": "signal_generated",
  "market": "KRW-XRP",
  "mode": "demo",
  "learning_enabled": true,
  "app_name": "upbit-auto-trader",
  "trading_mode": "demo",
  "logger": "decision",
  "level": "INFO",
  "timestamp": "2026-04-28T00:00:00+00:00"
}
```

공통 필드 `app_name`, `trading_mode`, `learning_enabled`, `logger`, `level`, `timestamp`는 로그 핸들러가 주입한다. 이벤트 payload가 같은 이름의 값을 제공하면 이벤트 payload 값을 우선한다.

### promotion_evaluations schema
```json
{
  "status": "READY_FOR_REVIEW",
  "approved": false,
  "rejection_reasons": [],
  "metrics": {
    "demo_days": 14,
    "total_trades": 100,
    "win_rate": 0.52,
    "profit_factor": 1.2,
    "max_drawdown": 0.08,
    "stoploss_failures": 0
  }
}
```

### 로그 활용 우선순위
1. 룰 개선 분석 데이터
2. replay 검증 데이터
3. 승격 평가 데이터
4. 향후 모델 학습 데이터

### 운영 점검 항목
- 로그 디렉터리 writable 여부
- JSONL 파일 증가 여부
- 일별 exporter 정상 수행
- decision_logs 테이블 적재 여부

---

## 14. 장애 유형별 대응

### A. 업비트 public ws 끊김
- reconnect manager 작동
- market stream health check
- 3회 이상 실패 시 텔레그램 경고

### B. private ws 끊김
- 잔고/체결 동기화 재시도
- live 상태면 SAFE_MODE 전환
- 복구 완료 전 신규 주문 차단

### C. 잔고 sync 실패
- SAFE_MODE 유지
- 텔레그램 경고
- retry
- 계속 실패 시 HARD_STOP 고려

### D. 텔레그램 실패
- retry queue
- 일정 횟수 실패 시 dashboard 경고
- 치명적 운영 이벤트는 별도 error log 기록

### E. 손절 상태 불일치
- 포지션과 거래소 상태 비교
- live 주문 차단
- 운영자 점검 요청
- 복구 후에만 재개

---

## 15. 운영자 수동 명령
- Start Demo
- Enable Live
- Pause
- Safe Mode
- Hard Stop
- Resync Balances
- Reconcile Orders
- Test Telegram
- Rebuild Learning Dataset
- Run Rule Review
- Generate Rule Proposal
- Apply Rule Proposal To Demo
- Approve Rule Proposal For Live

---

## 15. Git/TDD 운영 규칙
- 모든 기능 변경은 실패 테스트부터 시작
- 테스트 통과 후 커밋
- 커밋 메시지는 반드시 한국어
- 운영 절차 변경 시 RUNBOOK 동시 수정

### 예시
```bash
git add .
git commit -m "재기동 후 SAFE_MODE 복구 절차와 텔레그램 알림 추가"
```
