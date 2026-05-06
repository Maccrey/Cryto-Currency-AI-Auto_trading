# CODEX_HARNESS.md

## 1. 문서 목적

이 문서는 **업비트 급등·급락 기반 자동매매 시스템**을 Codex로 일관되게 개발하기 위한 단일 기준 문서다.

목표는 세 가지다.

1. Codex가 저장소를 읽고 수정할 때 **기획 의도와 구현 범위를 정확히 이해**하게 만든다.
2. 각 작업이 문서, 테스트, 코드, 운영 기준까지 **같은 계약 아래**에서 움직이게 만든다.
3. 데모 운영 → 학습 축적 → Codex 룰 개선 → replay/demo 검증 → 실거래 승격까지의 전 과정을 **누락 없이 구현**하게 만든다.

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
- 학습 로그 기반 Codex 룰 개선 리포트/변경안/replay/demo/live 승인 워크플로

### 3.2 금지 사항
- `demo` 모드에서 실주문 호출 금지
- `.env` 값을 코드에 하드코딩 금지
- 손절 없는 포지션 생성 금지
- 재기동 직후 바로 live 거래 활성화 금지
- 테스트 없는 전략 규칙 변경 금지
- replay 테스트 없는 룰 변경 금지
- 룰 변경안의 live 즉시 반영 금지
- 승인 없는 live 룰 반영 금지
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
- `LEARNING_ENABLED=true`는 필수 고정값이다.
- 학습 로그의 1차 목적은 TensorFlow 학습이 아니라 룰 개선 분석, replay 검증, 승격 평가다.

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
- 룰 개선 분석 데이터
- replay 검증 데이터
- demo→live 승격 평가 데이터
- 전략 회귀 테스트와 feature 개선
- 향후 모델 학습 데이터셋

---

## 14. Codex 룰 개선 루프 계약

초기 전략 개선은 TensorFlow 직접 학습보다 **학습 로그 기반 Codex 룰 개선 루프**를 우선한다. TensorFlow 모델은 충분한 로그, replay 기준, demo shadow 검증이 갖춰진 뒤 선택 의존성 `ml`에서 후순위로 다룬다.

### 14.1 고정 흐름
```text
최근 N일 학습 로그 집계
-> 주요 손실/손절/차단 원인 분석
-> Codex 룰 변경안 생성
-> 실패 테스트 및 replay 테스트 작성
-> 허용 파일만 수정
-> replay 테스트 통과
-> demo 적용
-> demo 지표 재검증
-> 운영자 승인
-> live 반영
-> 룰 변경 히스토리 원장 기록
```

### 14.2 표본 기준
- `RULE_REVIEW_WINDOW_DAYS` 기간의 로그만 기본 분석 대상으로 삼는다.
- `RULE_REVIEW_MIN_TRADES` 미만이면 룰 변경안을 생성하지 않는다.
- 손절률은 투자성향별 고정값이다. 단타/단기 -3%, 중기 -5%, 장기 -10%를 사용한다.
- `STOP_LOSS_*`, `stop_loss_pct`, `stop_loss_price`, `fixed_stop_loss_pct`는 Codex 룰 변경 금지 파라미터다.
- `RULE_REVIEW_MIN_STOPLOSSES`를 충족하더라도 손절 파라미터 변경안을 생성하지 않는다. 손절 관련 개선은 진입 조건, 사이징, 재진입 차단, 기대 검증 기준으로만 제안한다.
- 한 번에 변경 가능한 파라미터 수는 `RULE_CHANGE_MAX_PARAMS_PER_RUN` 이하로 제한한다.
- review/proposal 상태는 코인/투자성향별 학습 로그 디렉터리의 `rule-review-state.json`에 저장해 재기동 후에도 이어서 검토한다.
- 승인·거절·demo 적용·live 반영 등 의사결정 이력은 같은 디렉터리의 `rule-change-history.jsonl`에 append-only로 저장한다.
- XRP 기본 경로는 `LEARNING_LOG_DIR/<TRADING_PROFILE>/`, 다른 코인은 `LEARNING_LOG_DIR/<TRADE_COIN>/<TRADING_PROFILE>/`를 사용한다.

### 14.3 룰 변경 히스토리 원장
Codex는 매매룰을 바꿀 때 기존 룰과 새 룰의 차이뿐 아니라 “왜 바꿨는지”를 추적 가능하게 남겨야 한다. 이 히스토리는 실수를 줄이고 반복되는 잘못된 변경을 막으며, 장기적으로 최고의 트레이더에 가까워지기 위한 전략 학습 기록이다.

`rule-change-history.jsonl`의 각 행은 최소 아래 필드를 가진다.

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `history_id` | string | 히스토리 이벤트 고유 ID |
| `event_type` | string | `proposal_created`, `replay_verified`, `demo_applied`, `demo_apply_rejected`, `live_approved`, `live_approval_rejected`, `commit_linked`, `rollback`, `correction` |
| `review_id` | string | 원본 룰 리뷰 ID |
| `proposal_id` | string | 룰 변경안 ID |
| `market` | string | 대상 마켓, 예: `KRW-BTC` |
| `trade_coin` | string | 대상 코인 |
| `trading_profile` | string | 투자성향 |
| `mode` | string | 실행 모드 |
| `learning_log_dir` | string | 분석/히스토리 기준 로그 디렉터리 |
| `analysis_window_days` | number | 분석 대상 기간 |
| `trade_count` | number | 분석 표본 거래 수 |
| `stop_loss_count` | number | 분석 표본 손절 수 |
| `major_loss_causes` | array | 주요 손실/손절 원인 |
| `blocked_reason_summary` | array | proposal 차단/거절 사유 |
| `external_context_summary` | object | 온체인/ETF 표본 수, 상태 분포, 평균 가중치 |
| `previous_rule_snapshot` | object | 변경 전 파라미터 값 |
| `proposed_rule_snapshot` | object | 변경 후 후보 파라미터 값 |
| `changed_parameters` | array[string] | 변경 대상 파라미터 목록 |
| `change_reason` | string | 변경 사유 |
| `expected_effect` | string | 기대 효과 |
| `known_risks` | string | 알려진 리스크 |
| `replay_result` | object/null | replay 검증 결과 |
| `demo_result` | object | demo 적용 결과 |
| `approval_status` | string | `pending`, `passed`, `failed`, `applied`, `approved`, `rejected`, `linked` 등 |
| `approved_by` | string | 승인자 |
| `applied_target` | string | 적용 대상, 기본 `demo` |
| `created_at` | string | ISO-8601 기록 시각 |
| `commit_hash` | string | 룰 변경 커밋 hash, 커밋 전 이벤트는 빈 문자열 허용 |

`correction` 이벤트는 추가로 `correction_detail.reason`, `correction_detail.corrected_fields`, `correction_detail.corrected_by`를 포함할 수 있다. correction은 기존 행을 고치지 않고 새 행으로 보정 근거를 남기는 용도다.

`rollback` 이벤트는 추가로 `rollback_detail.reason`, `rollback_detail.target`, `rollback_detail.rolled_back_by`를 포함할 수 있다. rollback은 문제가 생긴 룰 변경안을 되돌렸다는 운영 판단과 대상을 남기는 용도이며 기존 히스토리 행을 수정하지 않는다.

`history_warnings`는 proposal 응답 필드이며 히스토리 원장 필수 필드는 아니다. Codex는 proposal 생성 시 동일 파라미터의 과거 `*_rejected`, `failed`, `rolled_back`, `rollback`, `correction` 이벤트를 검사해 `history_warnings`에 표시한다.

히스토리는 수정/삭제하지 않는다. 잘못된 기록이 있으면 새 correction 이벤트를 추가한다. Codex는 룰 변경 커밋 메시지와 `commit_hash`를 히스토리에 남기고, 후속 룰 변경 전 반드시 과거 히스토리에서 같은 파라미터의 반복 실패 여부를 확인한다.

### 14.4 허용 변경 파일
- `app/services/signals/**`
- `app/services/sizing/**`
- `app/services/risk/**`
- `app/services/regime/**`
- `app/core/settings.py`
- `app/services/rules/**`
- `tests/**`
- `STRATEGY_SPEC.md`, `ENV_SPEC.md`, `RUNBOOK.md`, `Tasklist.md`, `README.md`, `PRD.md`, `CODEX_HARNESS.md`

이 목록 밖의 변경은 별도 작업으로 분리한다.

### 14.5 룰 변경 금지 조건
- 실패 테스트가 없으면 금지
- replay 테스트가 없으면 금지
- demo 선반영 없이 live 반영 금지
- live 운영 중 즉시 반영 금지
- 손절률 고정값 변경 금지
- 기존 룰 변경 히스토리 검토 없이 변경 금지
- `change_reason`, `expected_effect`, `known_risks` 없는 변경 금지
- main 직접 반영 금지
- 한국어 커밋 없는 반영 금지

### 14.6 Git/TDD 규칙
- 룰 변경도 반드시 실패 테스트를 먼저 작성한다.
- replay 테스트를 통과해야 변경안을 demo에 적용할 수 있다.
- 변경안 생성 후 한국어 커밋을 만든다.
- 커밋 후 `upbit-link-rule-commit --proposal-id <id> --learning-log-dir <룰 로그 경로>` 또는 API로 `rule-change-history.jsonl`에 커밋 해시와 변경 근거를 연결한다.
- 브랜치 기반으로 검토하며 main 직접 반영은 금지한다.
- live 반영은 운영자 승인과 demo 재검증 통과가 필요하다.

### 14.6 오프라인 모델 학습 게이트
- TensorFlow 학습 CLI는 `ml` extra 환경에서만 실제 학습을 시도한다.
- 학습 데이터 표본 수가 부족하면 학습을 거부한다.
- train/validation/test 기간 분리가 없으면 학습을 거부한다.
- baseline보다 낮은 성능의 모델은 승격할 수 없다.
- 통과 결과도 먼저 `model-training-report.json`과 `shadow-predictions.jsonl`로 저장하며 live 주문 게이트를 직접 바꾸지 않는다.
- 손절, 사이징, SAFE_MODE, HARD_STOP, 룰 변경 승인 게이트가 모델 출력보다 우선한다.

---

## 15. 재기동 복구 계약

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

## 16. 테스트 하네스 계약

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
- 룰 변경안이 replay 테스트 없이 demo/live에 적용되지 않음
- 승인 없는 live 룰 반영 거부

---

## 17. 문서 동기화 규칙
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
- 룰 개선 워크플로 변경 → `CODEX_HARNESS.md` / `STRATEGY_SPEC.md` / `RUNBOOK.md` 수정

---

## 18. Codex 작업 템플릿

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

## 19. 완료 정의(Definition of Done)

작업 완료 조건:
1. 요구사항이 문서와 일치한다
2. 실패 테스트가 먼저 존재했다
3. 테스트가 통과한다
4. `demo/live + always-on learning` 구조가 유지된다
5. 손절/재기동/텔레그램/대시보드 정합성이 유지된다
6. 관련 문서가 반영되었다
7. Git 커밋 메시지가 한국어다
8. 룰 변경 작업은 replay + demo 검증 + 승인 정책을 통과했다

---

## 20. Codex 시작 순서
Codex는 아래 순서로 문서를 읽는다.
1. `docs/CODEX_HARNESS.md`
2. `docs/PRD.md`
3. `docs/STRATEGY_SPEC.md`
4. `docs/ENV_SPEC.md`
5. `docs/RUNBOOK.md`
6. `docs/Tasklist.md`
7. `README.md`
