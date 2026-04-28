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
11. 텔레그램으로 재기동 또는 시작 메시지 전송
12. health check 통과 확인
13. demo 또는 live 준비 상태 진입

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

---

## 9. demo 운영 절차
1. `TRADING_MODE=demo`
2. 앱 시작
3. 가상 체결 경로 확인
4. 텔레그램 메시지 확인
5. 손절 테스트
6. 대시보드 마커 표시 확인
7. 구조화 로그 적재 확인
8. 승격 평가 지표 축적

### demo 점검 체크리스트
- [ ] 실주문 0건
- [ ] decision logs 정상 저장
- [ ] 가상 체결 정상 반영
- [ ] 손절 알림 정상
- [ ] 재기동 알림 정상
- [ ] 대시보드 정합성 정상

---

## 10. live 운영 절차
1. 승격 기준 충족 확인
2. 승인 상태 확인
3. `TRADING_MODE=live`
4. 부팅 후 SAFE_MODE 진입
5. 상태 복구 확인
6. 소액/제한된 상태로 활성화
7. 실주문 경로 모니터링
8. 텔레그램 및 대시보드 정합성 확인

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

---

## 12. 로그 / 데이터셋 운영

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

### 운영 점검 항목
- 로그 디렉터리 writable 여부
- JSONL 파일 증가 여부
- 일별 exporter 정상 수행
- decision_logs 테이블 적재 여부

---

## 13. 장애 유형별 대응

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

## 14. 운영자 수동 명령
- Start Demo
- Enable Live
- Pause
- Safe Mode
- Hard Stop
- Resync Balances
- Reconcile Orders
- Test Telegram
- Rebuild Learning Dataset

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
