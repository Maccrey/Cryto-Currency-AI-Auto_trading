# CODEX_HARNESS.md

## 1. 문서 목적

이 문서는 **업비트 급등·급락 기반 자동매매 시스템**을 Codex로 일관되게 개발하기 위한 단일 기준 문서다.

목표는 세 가지다.

1. Codex가 저장소를 읽고 수정할 때 **기획 의도와 구현 범위를 정확히 이해**하게 만든다.
2. 각 작업이 문서, 테스트, 코드, 운영 기준까지 **같은 계약 아래**에서 움직이게 만든다.
3. 데모 운영 → 학습 축적 → 실거래 승격까지의 전 과정을 **누락 없이 구현**하게 만든다.

---

## 2. 제품 한 줄 정의

**업비트 시세를 실시간 감시해 급등·급락 신호를 포착하고, 현재 보유 코인 수량과 현금 잔고를 기반으로 자동 비중을 계산하여 데모/실거래를 수행하며, 모든 모드에서 항상 학습 로그를 축적하는 자동매매 시스템**

---

## 3. 시스템 범위 계약

### 3.1 반드시 구현할 기능
- 업비트 public WebSocket 시세 수집
- 업비트 REST/private WebSocket 기반 잔고, 주문, 체결, 자산 동기화
- 시작 시 현재 보유 코인 수량 + 현금 잔고 조회
- 신호 세기 기반 매수/매도 비율 계산
- 매수 시 손절 가격 자동 주입
- 가격 손절 + 기대 불일치 손절
- 텔레그램 체결/손절/재기동 알림
- GUI 대시보드
- 차트 위 매수/매도/손절 마커 + 툴팁 + 손절 라인
- 장애 자동 복구 후 재기동
- 재기동 시 SAFE_MODE 및 텔레그램 알림
- `.env` 기반 비밀 및 모드 관리
- `demo` / `live` 실행 모드
- **모든 모드에서 항상 학습 로그 활성화**
- 초기에는 `demo` 모드로 일정 기간 운영 후 기준 충족 시 `live` 전환
- 구조화 로그 기반 데이터셋 생성 및 전략 고도화

### 3.2 금지 사항
- `demo` 모드에서 실주문 호출 금지
- `.env` 값을 코드에 하드코딩 금지
- 손절 없는 포지션 생성 금지
- 재기동 직후 바로 live 거래 활성화 금지
- 테스트 없는 전략 규칙 변경 금지
- 텔레그램 알림 실패 무시 금지
- structured logging 비활성화 금지
- 영어 커밋 메시지 금지

---

## 4. Codex 기본 철학

### 4.1 구현 순서
Codex는 아래 순서를 절대 깨면 안 된다.

1. 문서 계약 이해
2. 실패 테스트 작성
3. 최소 구현
4. 리팩터링
5. 통합/계약 테스트
6. 문서 반영
7. Git 커밋

### 4.2 작업 단위
작업은 반드시 작게 쪼갠다.

예:
- “매수 체결 시 손절가 주입 구현”
- “노란 손절 마커 툴팁 렌더링 구현”
- “재기동 후 SAFE_MODE 진입 구현”
- “승격 평가기 PF/MDD 기준 구현”

### 4.3 TDD 고정 규칙
항상 아래 순서를 따른다.

- [Fail] 실패 테스트 먼저 작성
- [Code] 최소 구현
- [Refactor] 구조 정리
- [Contract] 통합/계약 테스트
- [Docs] 관련 문서 반영
- [Git] 한국어 커밋

---

## 5. Git 커밋 규칙

### 5.1 커밋 언어
모든 커밋 메시지는 **반드시 한국어**로 작성한다.

### 5.2 커밋 기준
- 기능 단위 커밋
- 테스트 없는 커밋 금지
- 문서 계약 변경 시 관련 문서와 함께 커밋
- 큰 기능은 여러 개의 작은 커밋으로 분리

### 5.3 허용 예시
- `초기 자산 동기화와 포트폴리오 상태 저장 구현`
- `매수 체결 시 손절가 주입과 알림 테스트 추가`
- `재기동 복구 절차와 SAFE_MODE 전환 구현`
- `차트 손절 마커 툴팁과 손절 라인 렌더링 구현`
- `데모 승격 평가기와 승인 워크플로 추가`

### 5.4 금지 예시
- `fix bug`
- `update`
- `WIP`
- `stoploss`
- `dashboard changes`

### 5.5 권장 Git 절차
```bash
git checkout -b feature/stoploss-injection
git config commit.template .gitmessage.ko.txt
pre-commit install
pytest -q
git add .
git commit -m "매수 체결 시 손절가 주입과 손절 알림 테스트 추가"
```

---

## 6. 실행 모드 정책

### 6.1 허용 모드
- `demo`
- `live`

### 6.2 학습 계층
학습은 실행 모드가 아니라 **항상 켜진 계층**이다.
- `demo`에서 ON
- `live`에서 ON
- 꺼지면 안 됨

### 6.3 demo 모드
- 실주문 API 호출 금지
- 가상 주문/가상 체결
- 텔레그램, 대시보드, 손절, 재기동, 로그 전체 검증

### 6.4 live 모드
- 실주문 허용
- 부팅 후 기본 SAFE_MODE
- sync / reconcile / health check 이후 활성화

---

## 7. 초기 운영 정책

### 7.1 기본 흐름
```text
부팅
-> SAFE_MODE
-> demo 모드 시작
-> 일정 기간 학습/검증
-> 승격 평가
-> 운영자 승인 또는 자동 규칙 충족
-> live 전환
-> 실거래 중에도 학습 계속
```

### 7.2 승격 기준 예시
- 데모 운영 일수 ≥ 14일
- 누적 거래 수 ≥ 100
- 승률 ≥ 52%
- Profit Factor ≥ 1.20
- Max Drawdown ≤ 8%
- 손절 오작동 0건
- 재기동 후 복구 성공률 ≥ 99%
- 텔레그램 성공률 ≥ 99%

---

## 8. 저장소 구조 표준

```text
repo/
  app/
    main.py
    api/
    core/
      settings.py
      logging.py
      modes.py
      safety.py
    domain/
      entities/
      value_objects/
      enums/
    integrations/
      upbit/
      telegram/
    services/
      market_data/
      signals/
      regime/
      sizing/
      execution/
      risk/
      portfolio/
      recovery/
      promotion/
      learning/
      dashboard/
    workers/
    dashboard/
  strategy/
    entry/
    exit/
    stoploss/
    regime/
    features/
    promotion/
  tests/
    unit/
    integration/
    contract/
    replay/
    restart/
    dashboard/
    load/
  fixtures/
  docs/
    PRD.md
    README.md
    Tasklist.md
    RUNBOOK.md
    STRATEGY_SPEC.md
    ENV_SPEC.md
    CODEX_HARNESS.md
  .codex/
    config.toml
    agents/
    skills/
  ops/
```

---

## 9. 시스템 아키텍처 계약

```text
[Upbit Public WS]
      ↓
market-data-svc
      ↓
signal-engine ──→ regime-engine ──→ sizing-engine
      ↓                        ↓
decision-logger           risk-engine
      ↓                        ↓
demo/live executor ←──── recovery-orchestrator
      ↓
portfolio-svc
      ↓
dashboard-svc
      ↓
telegram-notifier
```

---

## 10. 대시보드 계약

### 10.1 차트 위 표시
#### 매수 마커
- 색상: 파란색
- 툴팁 필수
- 표시 정보:
  - 코인
  - 신호 세기
  - 매수 금액
  - 매수 수량
  - 매수 비율
  - 체결가
  - 손절가
  - 시각

#### 일반 매도 마커
- 색상: 빨간색
- 툴팁 필수
- 표시 정보:
  - 코인
  - 매도 금액
  - 매도 수량
  - 매도 비율
  - 체결가
  - 수수료
  - 실현손익
  - 시각

#### 손절 매도 마커
- 색상: 노란색
- 툴팁 필수
- 표시 정보:
  - 코인
  - 손절 사유
  - 손해 금액
  - 매도 금액
  - 매도 수량
  - 체결가
  - 손절 기준가
  - 시각

#### 손절 라인
- 활성 포지션 동안 `stop_loss_price` 표시
- 포지션 종료 시 제거

### 10.2 하단 패널
- 현재 보유 코인 수량
- 보유 현금
- 누적 실현손익
- 평가손익
- 매수 횟수
- 매도 횟수
- 손절 횟수
- 최근 손절 사유
- 현재 실행 모드
- LEARNING ON
- 최근 재기동 시각
- 승격 가능 여부

---

## 11. 자산 기반 비중 계산 계약

### 입력
- 현금 잔고
- 보유 코인 수량
- 현재가
- 평균 단가
- 신호 세기
- 국면 점수
- 유동성 점수
- 슬리피지 추정
- 수수료율

### 출력
- 매수 비율
- 매도 비율
- 매수 금액
- 매수 수량
- 매도 금액
- 매도 수량
- 손절가
- 허용 여부
- 차단 사유

### 계산 원칙
- reserve cash 유지
- spread/slippage 반영
- reentry block 반영
- risk_off 시 size 축소
- 기대값 음수면 진입 금지

---

## 12. 손절 계약

### 12.1 매수 시 주입
매수 체결 시 반드시 저장:
- entry_price
- stop_loss_price
- stop_loss_pct
- validation_window_sec
- min_expected_return_pct
- stop_loss_reason = null

### 12.2 하드 손절
- 현재가 ≤ stop_loss_price
- 즉시 손절 매도

### 12.3 소프트 손절
- validation window 내 기대 상승률 미달
- momentum 약화
- imbalance 역전
- 거래량 급감
- 필요한 경우 부분 청산

### 12.4 손절 후 처리
- 텔레그램 알림
- 노란 마커 표시
- DB 기록
- 재진입 차단

---

## 13. 항상 켜진 학습 계층 계약

### 저장 이벤트
- market_tick
- signal_generated
- regime_snapshot
- sizing_decision
- order_intent
- virtual_fill
- real_fill
- stop_loss_triggered
- position_closed
- restart_detected
- recovery_completed
- promotion_evaluated

### 형식
- JSONL 기본
- 일별 Parquet export 가능
- schema_version 포함

### 목적
- 전략 회귀 테스트
- feature 개선
- 모델 학습 데이터셋
- 승격 근거 확보

---

## 14. 재기동 복구 계약

### 절차
```text
프로세스 종료 감지
-> systemd/docker 재기동
-> 앱 부팅
-> restart event 저장
-> 잔고 sync
-> 오픈오더 reconcile
-> 손절 상태 복원
-> SAFE_MODE 진입
-> 텔레그램 재기동 알림
```

### 금지 사항
- 복구 전 신규 주문 금지
- 손절 상태 미복원 상태에서 거래 금지
- 연속 재기동 기준 초과 시 HARD_STOP

---

## 15. 테스트 하네스 계약

### 테스트 레벨
- 단위
- 통합
- 계약
- replay
- restart
- dashboard
- load

### 반드시 있어야 하는 실패 테스트
- demo에서 실주문 금지
- live에서만 실주문 허용
- 매수 시 손절가 주입
- 손절가 도달 시 손절 실행
- 기대 불일치 손절 실행
- 재기동 시 SAFE_MODE
- 재기동 텔레그램 전송
- 대시보드 마커 색상/툴팁 정합성
- 승격 기준 미달 시 live 거부

---

## 16. 문서 동기화 규칙
Codex는 변경 시 아래 문서를 항상 함께 고려한다.

- `PRD.md`
- `README.md`
- `Tasklist.md`
- `RUNBOOK.md`
- `STRATEGY_SPEC.md`
- `ENV_SPEC.md`
- `CODEX_HARNESS.md`

### 규칙
- 전략 변경 → `STRATEGY_SPEC.md` 수정
- 운영 절차 변경 → `RUNBOOK.md` 수정
- 환경 변수 변경 → `ENV_SPEC.md` 수정
- 기획 범위 변경 → `PRD.md` / `Tasklist.md` 수정

---

## 17. Codex 작업 템플릿

```text
Task:
Implement restart notification after automatic recovery.

Acceptance criteria:
- Persist restart event.
- Run portfolio sync before enabling trading.
- Enter SAFE_MODE after restart.
- Send Telegram message with restart reason, sync result, and balances.
- Add unit and integration tests.
- Update RUNBOOK.md and Tasklist.md.
- Commit in Korean.
```

---

## 18. 완료 정의(Definition of Done)

작업 완료 조건:
1. 요구사항이 문서와 일치한다
2. 실패 테스트가 먼저 존재했다
3. 테스트가 통과한다
4. `demo/live + always-on learning` 구조가 유지된다
5. 손절/재기동/텔레그램/대시보드 정합성이 유지된다
6. 관련 문서가 반영되었다
7. Git 커밋 메시지가 한국어다

---

## 19. Codex 시작 순서
Codex는 아래 순서로 문서를 읽는다.
1. `docs/CODEX_HARNESS.md`
2. `docs/PRD.md`
3. `docs/STRATEGY_SPEC.md`
4. `docs/ENV_SPEC.md`
5. `docs/RUNBOOK.md`
6. `docs/Tasklist.md`
7. `README.md`
