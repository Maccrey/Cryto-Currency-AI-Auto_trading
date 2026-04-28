# README.md

## 1. 프로젝트 소개

### 제품명
**Upbit Momentum Auto Trader**

### 슬로건
**데모로 검증하고, 실거래로 확장하며, 모든 모드에서 계속 학습하는 업비트 자동매매 시스템**

### 핵심 소개
이 프로젝트는 업비트의 급등·급락 신호를 실시간으로 감지하고, 현재 보유 자산을 기준으로 자동 비중을 계산해 `demo` 또는 `live` 모드로 거래를 수행한다.  
매수 시 손절가를 함께 주입하고, 가격 기반 손절과 기대 불일치 손절을 모두 지원한다.  
모든 모드에서 학습 로그를 항상 기록하여 전략과 AI 개선에 활용한다.

---

## 2. 실행 모드 정책

### 허용 모드
- `demo`
- `live`

### 공통 규칙
- 학습 로깅은 항상 ON
- 구조화 로그는 항상 저장
- 대시보드/텔레그램/재기동 기록 모두 유지

### demo 모드
- 실제 주문 API 호출 금지
- 가상 체결 사용
- 운영 흐름 전체 검증
- 실거래 승격 전 기본 운용 모드

### live 모드
- 실제 주문 허용
- 부팅 후 기본 SAFE_MODE
- 잔고 sync / 오픈오더 reconcile / health check 이후 활성화

---

## 3. 초기 운영 권장 방식
1. 기본값은 `demo`
2. 일정 기간 데모 운영
3. 승격 기준 평가
4. 운영자 승인 또는 자동 정책으로 `live` 전환
5. `live`에서도 계속 학습 로그 축적

---

## 4. 개발 환경

### 런타임 / 프레임워크
- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic v2

### 패키지 / 빌드
- uv 또는 pip
- pre-commit

### 타입 / 포맷 / 린트
- pre-commit

### 관찰성
- structlog

---

## 5. 권장 디렉터리 구조
```text
app/
  main.py
  api/
  core/
  domain/
  integrations/
    upbit/
    telegram/
  services/
  workers/
  dashboard/
strategy/
tests/
fixtures/
docs/
ops/
.codex/
```

---

## 6. 로컬 실행

### uv 사용
```bash
uv sync
uv run uvicorn app.main:app --reload
uv run pytest -q
uv run pre-commit run --all-files
```

### pip 사용
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
pytest -q
pre-commit run --all-files
```

---

## 7. 환경 변수
실제 값은 `.env`에 두고, 저장소에는 `.env.example`만 둔다.

주요 변수:
- `TRADING_MODE=demo|live`
- `LEARNING_ENABLED=true`
- `TRADE_MARKET=KRW-XRP`
- `TRADE_COIN=XRP`
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

자세한 스펙은 `ENV_SPEC.md`를 따른다.

---

## 8. 핵심 기능 요약
- 실시간 급등·급락 신호 탐지
- 자산 기반 자동 비중 계산
- 매수 시 손절가 자동 주입
- 가격 손절 + 기대 불일치 손절
- 텔레그램 거래/재기동 알림
- 파란/빨간/노란 마커가 있는 대시보드
- 장애 자동 복구 및 SAFE_MODE
- demo→live 승격 평가
- 항상 켜진 학습 로그 계층

---

## 9. 대시보드 표시 요구사항

### 차트 상단
- 파란색 매수 마커 + 툴팁
- 빨간색 일반 매도 마커 + 툴팁
- 노란색 손절 매도 마커 + 툴팁
- 손절가 라인

### 하단 패널
- 보유 코인 수량
- 보유 현금
- 누적 실현손익
- 평가손익
- 매수 횟수
- 매도 횟수
- 손절 횟수
- 최근 손절 사유
- 현재 모드
- LEARNING ON
- 최근 재기동 시각
- 승격 가능 여부

---

## 10. 학습 로그 정책
이 프로젝트는 실행 모드와 무관하게 항상 학습 로그를 저장한다.

### 저장 대상
- 시세 feature
- signal score
- sizing decision
- order intent
- fill result
- stop loss trigger
- restart / recovery
- promotion evaluation

### 활용
- 전략 회귀 검증
- replay 테스트
- feature 개선
- 모델 학습 데이터셋 생성
- demo→live 승격 품질 판단

---

## 11. TDD + Git 커밋 규칙

### 개발 절차
1. 실패 테스트 작성
2. 최소 구현
3. 리팩터링
4. 통합/계약 테스트
5. 문서 업데이트
6. Git 커밋

### Git 보조 설정
```bash
git config commit.template .gitmessage.ko.txt
pre-commit install
```

- 커밋 메시지는 반드시 한국어로 작성
- 커밋 전에 `pytest -q`와 `pre-commit run --all-files` 통과 확인

### 커밋 규칙
- 모든 커밋 메시지는 **반드시 한국어**
- 구현 단위별 커밋
- 테스트 없는 커밋 금지
- 문서 변경과 계약 변경은 함께 커밋

### 커밋 예시
```bash
git add .
git commit -m "손절가 주입 로직과 매수 알림 테스트 추가"
```

```bash
git add .
git commit -m "재기동 복구 오케스트레이터와 SAFE_MODE 전환 구현"
```

---

## 12. 품질 기준
- 테스트 커버리지 80% 이상
- 핵심 거래/손절 경로 커버리지 95% 목표
- `demo`에서 실주문 0건
- 손절 주입 성공률 100%
- 텔레그램 알림 성공률 99% 이상
- 재기동 후 복구 성공률 99% 이상

---

## 13. 운영 체크리스트
- [ ] `.env` 누락 없이 설정
- [ ] `TRADING_MODE=demo`로 시작
- [ ] 텔레그램 봇 테스트
- [ ] 잔고 sync 정상 확인
- [ ] 대시보드 마커 표시 확인
- [ ] 손절 라인 표시 확인
- [ ] 재기동 알림 테스트
- [ ] 승격 평가기 기준 확인
- [ ] `live` 전환 전 승인 절차 완료

---

## 14. 관련 문서
- `PRD.md`
- `Tasklist.md`
- `RUNBOOK.md`
- `STRATEGY_SPEC.md`
- `ENV_SPEC.md`
- `CODEX_HARNESS.md`
