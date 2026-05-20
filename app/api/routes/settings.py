from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services.config.env_file import EnvFileService
from app.services.learning.reset import LearningDataResetService
from app.services.learning.service import LearningService


def build_settings_router(
    *,
    env_file_service: EnvFileService,
    learning_data_reset_service: LearningDataResetService | None = None,
    learning_service: LearningService | None = None,
    start_trading_service: Callable[[], dict[str, object]] | None = None,
    stop_trading_service: Callable[[], Awaitable[dict[str, object]] | dict[str, object]] | None = None,
    trading_status_service: Callable[[], dict[str, object]] | None = None,
    reset_demo_trading_data_service: Callable[[], dict[str, object]] | None = None,
    purge_runtime_data_service: Callable[[], dict[str, object]] | None = None,
    telegram_test_service: Callable[[], dict[str, object]] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/settings")

    @router.get("", response_class=HTMLResponse)
    def settings_page() -> str:
        return SETTINGS_HTML

    @router.get("/current")
    def current_settings() -> dict[str, object]:
        return env_file_service.current()

    @router.get("/secret/{key}")
    def secret_value(key: str) -> dict[str, object]:
        secret_keys = {
            "telegram-bot-token": "TELEGRAM_BOT_TOKEN",
            "upbit-access-key": "UPBIT_ACCESS_KEY",
            "upbit-secret-key": "UPBIT_SECRET_KEY",
        }
        return env_file_service.secret_value(secret_keys.get(key, key))

    @router.post("")
    def save_settings(payload: dict[str, object]) -> dict[str, object]:
        return env_file_service.save(payload)

    @router.get("/trading/readiness")
    def trading_readiness() -> dict[str, object]:
        return {
            "status": "ok",
            "start_readiness": env_file_service.trading_start_readiness(),
        }

    @router.get("/trading/status")
    def trading_status() -> dict[str, object]:
        if trading_status_service is None:
            return {
                "status": "not_configured",
                "running": False,
                "startable": False,
                "message": "trading status service is not configured",
            }
        return trading_status_service()

    @router.post("/trading/start")
    async def start_trading() -> dict[str, object]:
        readiness = env_file_service.trading_start_readiness()
        if not readiness["ready"]:
            return {
                "status": "blocked",
                "started": False,
                "start_readiness": readiness,
                "message": readiness["message"],
            }
        if start_trading_service is None:
            return {
                "status": "not_configured",
                "started": False,
                "start_readiness": readiness,
                "message": "trading start service is not configured",
            }
        result = start_trading_service()
        return {
            **result,
            "start_readiness": readiness,
        }

    @router.post("/trading/stop")
    async def stop_trading() -> dict[str, object]:
        if stop_trading_service is None:
            return {
                "status": "not_configured",
                "stopped": False,
                "running": False,
                "message": "trading stop service is not configured",
            }
        result = stop_trading_service()
        if hasattr(result, "__await__"):
            result = await result
        return result

    @router.post("/learning/reset")
    def reset_learning_data() -> dict[str, object]:
        if learning_data_reset_service is None:
            return {
                "status": "not_configured",
                "reset": False,
                "message": "learning reset service is not configured",
            }
        result = learning_data_reset_service.reset()
        if learning_service is not None:
            learning_service.clear_recent_events()
        return {
            "status": "reset" if result.reset else "skipped",
            "reset": result.reset,
            "log_path": result.log_path,
            "archive_path": result.archive_path,
            "message": result.message,
        }

    @router.post("/demo-trading/reset")
    def reset_demo_trading_data() -> dict[str, object]:
        if reset_demo_trading_data_service is None:
            return {
                "status": "not_configured",
                "reset": False,
                "message": "demo trading data reset service is not configured",
            }
        return reset_demo_trading_data_service()

    @router.post("/data/purge")
    def purge_runtime_data() -> dict[str, object]:
        if purge_runtime_data_service is None:
            return {
                "status": "not_configured",
                "reset": False,
                "message": "data purge service is not configured",
            }
        return purge_runtime_data_service()

    @router.post("/telegram/test")
    def send_telegram_test() -> dict[str, object]:
        if telegram_test_service is None:
            return {
                "status": "not_configured",
                "sent": False,
                "message": "telegram test service is not configured",
            }
        return telegram_test_service()

    return router


SETTINGS_HTML = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Settings</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; color: #172026; background: #f4f7f9; }
    main { max-width: 760px; margin: 0 auto; padding: 32px 20px; }
    section { background: white; border: 1px solid #d8e0e6; border-radius: 8px; padding: 20px; }
    h1 { font-size: 24px; margin: 0 0 18px; }
    label { display: block; font-size: 13px; font-weight: 650; margin-top: 14px; }
    .required-mark { color: #b42318; font-weight: 900; margin-left: 4px; }
    input { box-sizing: border-box; width: 100%; padding: 10px 12px; border: 1px solid #b8c4ce; border-radius: 6px; font-size: 14px; }
    input[type="checkbox"] { width: auto; }
    .secret-input { display: grid; grid-template-columns: 1fr 42px; gap: 8px; align-items: center; }
    .icon-button { width: 42px; height: 40px; border: 1px solid #9eb0bd; border-radius: 6px; background: white; color: #172026; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
    .icon-button svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    select { box-sizing: border-box; width: 100%; padding: 10px 12px; border: 1px solid #b8c4ce; border-radius: 6px; font-size: 14px; background: white; }
    .switch { display: inline-grid; grid-template-columns: 1fr 1fr; border: 1px solid #9eb0bd; border-radius: 999px; overflow: hidden; margin: 8px 0 10px; }
    .switch button { border: 0; padding: 10px 18px; background: #edf2f5; cursor: pointer; font-weight: 700; }
    .switch button.active { background: #1769aa; color: white; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .actions { margin-top: 18px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .primary { background: #1769aa; color: white; border: 0; border-radius: 6px; padding: 11px 16px; font-weight: 700; cursor: pointer; }
    .primary:disabled { background: #8da4b6; cursor: wait; }
    .status { display: none; width: 100%; margin-top: 4px; padding: 10px 12px; border-radius: 6px; border: 1px solid #b7d7bd; background: #edf8ef; color: #22522b; font-size: 13px; line-height: 1.45; }
    .status.visible { display: block; }
    .warning { border-color: #f1b8b1; background: #fff1f0; color: #b42318; font-weight: 700; }
    .pending { border-color: #b8c4ce; background: #edf2f5; color: #33424c; }
    .danger-button { background: #b42318; color: white; border: 0; border-radius: 6px; padding: 11px 16px; font-weight: 700; cursor: pointer; }
    .danger-button:disabled { background: #c9847c; cursor: wait; }
    .danger-zone { margin-top: 18px; padding-top: 16px; border-top: 1px solid #f1b8b1; }
    .subsection { margin-top: 18px; padding-top: 16px; border-top: 1px solid #d8e0e6; }
    .rule-actions { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
    .rule-result { width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 13px; }
    .rule-result th, .rule-result td { padding: 8px; border-top: 1px solid #d8e0e6; text-align: left; vertical-align: top; }
    .rule-result th { width: 150px; color: #52616d; }
    .modal-backdrop { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; padding: 20px; background: rgba(15, 23, 42, 0.54); z-index: 50; }
    .modal-backdrop.visible { display: flex; }
    .rule-modal { width: min(760px, 100%); max-height: min(82vh, 760px); display: flex; flex-direction: column; border-radius: 8px; background: white; border: 1px solid #b8c4ce; box-shadow: 0 18px 48px rgba(15, 23, 42, 0.28); overflow: hidden; }
    .rule-modal header { padding: 16px 18px; border-bottom: 1px solid #d8e0e6; }
    .rule-modal h2 { margin: 0; font-size: 18px; }
    .rule-modal-body { padding: 16px 18px; overflow-y: auto; line-height: 1.45; }
    .rule-step { padding: 10px 0; border-bottom: 1px solid #edf2f5; font-size: 13px; }
    .rule-step strong { display: block; margin-bottom: 4px; }
    .rule-step.completed strong { color: #1f6b35; }
    .rule-step.blocked strong { color: #b42318; }
    .rule-step.running strong { color: #1769aa; }
    .rule-final { margin-top: 14px; padding: 12px; border: 1px solid #d8e0e6; border-radius: 6px; background: #f4f7f9; white-space: pre-line; font-size: 13px; }
    .rule-modal-footer { padding: 12px 18px; border-top: 1px solid #d8e0e6; display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
    .hidden { display: none !important; }
    .next-steps { display: none; margin-top: 12px; gap: 8px; flex-wrap: wrap; }
    .next-steps.visible { display: flex; }
    .start-panel { display: none; margin-top: 14px; padding: 12px; border: 1px solid #b7d7bd; border-radius: 6px; background: #edf8ef; }
    .start-panel.visible { display: block; }
    .start-panel.blocked { border-color: #f1b8b1; background: #fff1f0; color: #8a1f13; }
    .secondary { display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 0 12px; border: 1px solid #9eb0bd; border-radius: 6px; background: white; color: #172026; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; }
    .note { color: #52616d; font-size: 13px; line-height: 1.45; }
    .checkbox-line { display: flex; gap: 8px; align-items: center; margin-top: 12px; font-size: 13px; font-weight: 650; }
  </style>
</head>
<body>
<main>
  <section>
    <h1>설정</h1>
    <div class="note">demo 모드는 API 키 없이 학습/검증용으로 실행할 수 있다. live 모드는 저장 시 업비트 API 키가 필요하다.</div>
    <label for="serverName">서버 이름</label>
    <input id="serverName" autocomplete="off" placeholder="예: 서울-데모-1">
    <div class="note">텔레그램 알림 앞에 표시되어 어떤 서버에서 보낸 메시지인지 구분한다.</div>
    <label>거래 모드<span class="required-mark">*</span></label>
    <div id="modeSwitch" class="switch">
      <button type="button" data-mode="demo">DEMO</button>
      <button type="button" data-mode="live">LIVE</button>
    </div>
    <label for="tradingProfile">투자성향<span class="required-mark">*</span></label>
    <select id="tradingProfile"></select>
    <div id="profileDescription" class="note"></div>
    <div class="row">
      <div>
        <label for="tradeMarket">마켓<span class="required-mark">*</span></label>
        <input id="tradeMarket" placeholder="KRW-XRP">
      </div>
      <div>
        <label for="tradeCoin">코인<span class="required-mark">*</span></label>
        <input id="tradeCoin" placeholder="XRP">
      </div>
    </div>
    <label for="demoInitialCapital">데모 시작 투자금<span class="required-mark">*</span></label>
    <input id="demoInitialCapital" type="number" min="0" step="10000" placeholder="1000000">
    <div class="subsection">
      <label>온체인/ETF 컨텍스트</label>
      <div class="checkbox-line">
        <input id="externalContextEnabled" type="checkbox">
        <span>학습 로그와 대시보드에 외부 시장 컨텍스트 반영</span>
      </div>
      <label for="externalContextCacheTtlSec">외부 컨텍스트 캐시 TTL(초)</label>
      <input id="externalContextCacheTtlSec" type="number" min="0" step="1" placeholder="300">
      <div class="row">
        <div>
          <label for="onchainState">온체인 상태</label>
          <select id="onchainState">
            <option value="bullish">bullish</option>
            <option value="neutral">neutral</option>
            <option value="bearish">bearish</option>
          </select>
        </div>
        <div>
          <label for="onchainActiveAddressesChangePct">활성 주소 변화율(%)</label>
          <input id="onchainActiveAddressesChangePct" type="number" step="0.01" placeholder="0.0">
        </div>
      </div>
      <label for="onchainContextUrl">온체인 컨텍스트 URL</label>
      <input id="onchainContextUrl" autocomplete="off" placeholder="https://.../onchain-context">
      <div class="row">
        <div>
          <label for="onchainExchangeNetflowState">거래소 순유입 상태</label>
          <select id="onchainExchangeNetflowState">
            <option value="inflow">inflow</option>
            <option value="neutral">neutral</option>
            <option value="outflow">outflow</option>
          </select>
        </div>
        <div>
          <label for="etfState">ETF 상태</label>
          <select id="etfState">
            <option value="inflow">inflow</option>
            <option value="neutral">neutral</option>
            <option value="outflow">outflow</option>
            <option value="not_applicable">not_applicable</option>
          </select>
        </div>
      </div>
      <label for="etfContextUrl">ETF 컨텍스트 URL</label>
      <input id="etfContextUrl" autocomplete="off" placeholder="https://.../etf-context">
      <label for="etfFlowUsd">ETF 순유입/순유출 USD</label>
      <input id="etfFlowUsd" type="number" step="1" placeholder="0.0">
      <div class="note">URL이 있으면 market/coin 쿼리로 JSON을 읽어 학습 컨텍스트에 병합한다. BTC/ETH는 ETF 상태를 반영하고, XRP 등 미지원 코인은 not_applicable로 표시된다.</div>
      <div class="note">URL을 비워두면 웹 공개 데이터 소스를 사용한다. BTC 온체인은 Blockchain.com 차트, XRP 온체인은 XRPSCAN 원장 활동, BTC ETF는 Farside ETF flow 표를 조회한다.</div>
    </div>
    <div class="subsection">
      <label>무거래 완화 정책</label>
      <div class="checkbox-line">
        <input id="noTradeAdaptiveEnabled" type="checkbox">
        <span>demo에서 규칙 차단만 반복될 때 약한 신호 완화 후보 허용</span>
      </div>
      <div class="row">
        <div>
          <label for="noTradeRelaxAfterCycles">완화 전 연속 차단 사이클</label>
          <input id="noTradeRelaxAfterCycles" type="number" min="1" step="1" placeholder="100">
        </div>
        <div>
          <label for="noTradeRelaxMinScore">완화 최소 신호 점수</label>
          <input id="noTradeRelaxMinScore" type="number" min="0" max="1" step="0.01" placeholder="0.18">
        </div>
      </div>
      <div class="note">live에는 즉시 완화 반영하지 않고 replay와 demo 검증 후 승인 플로우를 거친다.</div>
    </div>
    <div class="subsection">
      <label>횡보장 리스크 가드</label>
      <div class="checkbox-line">
        <input id="sidewaysRiskGuardEnabled" type="checkbox">
        <span>가격과 거래대금이 정체된 구간에서 약신호 매수와 평단 근처 추가매수 차단</span>
      </div>
      <div class="row">
        <div>
          <label for="sidewaysPriceRangePct">가격 범위 상한</label>
          <input id="sidewaysPriceRangePct" type="number" min="0" max="0.05" step="0.0001" placeholder="0.002">
        </div>
        <div>
          <label for="sidewaysTradedValueRangePct">거래대금 범위 상한</label>
          <input id="sidewaysTradedValueRangePct" type="number" min="0" max="0.05" step="0.0001" placeholder="0.003">
        </div>
      </div>
      <div class="row">
        <div>
          <label for="sidewaysMaxAvgAbsReturnPct">평균 절대 변화율 상한</label>
          <input id="sidewaysMaxAvgAbsReturnPct" type="number" min="0" max="0.05" step="0.0001" placeholder="0.001">
        </div>
        <div>
          <label for="sidewaysScaleInMinDiscountPct">추가매수 최소 할인율</label>
          <input id="sidewaysScaleInMinDiscountPct" type="number" min="0" max="0.1" step="0.0001" placeholder="0.003">
        </div>
      </div>
      <div class="note">횡보장에서는 약신호 추가매수를 항상 막고, medium 이상 신호도 기존 진입가보다 충분히 낮을 때만 추가매수를 허용한다.</div>
    </div>
    <div class="subsection">
      <label>데이터 저장소</label>
      <label for="storageDir">storage 디렉터리</label>
      <input id="storageDir" autocomplete="off" placeholder="./storage">
      <div id="dataPathStatus" class="note"></div>
    </div>
    <div class="subsection">
      <label>자동 룰 업데이트</label>
      <div class="checkbox-line">
        <input id="autoRuleUpdateEnabled" type="checkbox">
        <span>학습데이터 충족률 100%에서 replay 통과 시 자동 룰 재평가</span>
      </div>
      <div class="row">
        <div>
          <label for="autoRuleCompletionRate">학습데이터 충족률 기준</label>
          <input id="autoRuleCompletionRate" type="number" min="0" max="1" step="0.01" placeholder="1.0">
        </div>
        <div>
          <label for="autoRuleWinRateSkip">자동 변경 제외 승률</label>
          <input id="autoRuleWinRateSkip" type="number" min="0" max="1" step="0.01" placeholder="0.8">
        </div>
      </div>
      <div id="autoRuleStatus" class="note"></div>
    </div>
    <div id="upbitCredentialSection" class="subsection">
      <label for="accessKey">업비트 액세스 키<span class="required-mark live-required">*</span></label>
      <input id="accessKey" autocomplete="off" placeholder="저장된 키가 있으면 ********로 표시">
      <label for="secretKey">업비트 시크릿 키<span class="required-mark live-required">*</span></label>
      <input id="secretKey" type="password" autocomplete="off" placeholder="저장된 키가 있으면 ********로 표시">
      <div class="note">LIVE 모드에서만 필요하다. DEMO 모드에서는 입력 폼을 숨기고 저장된 키를 변경하지 않는다.</div>
    </div>
    <div class="subsection">
      <label for="telegramToken">텔레그램 봇 토큰</label>
      <div class="secret-input">
        <input id="telegramToken" type="password" autocomplete="off" placeholder="저장된 토큰이 있으면 ********로 표시">
        <button id="telegramTokenToggle" class="icon-button" type="button" onclick="toggleTelegramToken()" aria-label="텔레그램 봇 토큰 보기" title="텔레그램 봇 토큰 보기">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          </svg>
        </button>
      </div>
      <div id="telegramTokenStatus" class="note"></div>
      <label for="telegramChat">텔레그램 채팅 ID</label>
      <input id="telegramChat" autocomplete="off" placeholder="-1003988291151 또는 telegram:group:-1003988291151">
      <div class="note">그룹 채팅은 Bot API 전송용 숫자 ID(-100...)로 저장된다. Chat 값이 telegram:group:-100... 형식이면 저장할 때 자동 변환된다.</div>
      <div class="row">
        <div>
          <label for="telegramUserId">텔레그램 사용자 ID</label>
          <input id="telegramUserId" autocomplete="off" placeholder="467359360">
        </div>
        <div>
          <label for="telegramUsername">텔레그램 사용자명</label>
          <input id="telegramUsername" autocomplete="off" placeholder="@maccrey">
        </div>
      </div>
      <label for="telegramAllowFrom">텔레그램 허용 사용자</label>
      <input id="telegramAllowFrom" autocomplete="off" placeholder="467359360">
      <div class="note">Identity의 AllowFrom 값을 기록해 둔다. 현재는 발신 알림 대상이 아니라 운영자 식별/향후 수신 명령 제한용 설정이다.</div>
      <button class="secondary" type="button" onclick="sendTelegramTest()">텔레그램 테스트 메시지 전송</button>
    </div>
    <div class="actions">
      <button id="saveButton" class="primary" type="button" onclick="saveSettings()">저장</button>
      <span id="status" class="status"></span>
    </div>
    <div class="subsection">
      <label>룰 개선</label>
      <div class="note">Codex 자동 룰 개선은 분석, 변경안 생성, replay 검증, demo 적용을 한 번에 실행하고 진행 과정을 모달로 표시한다. live 반영은 결과 확인 후 별도 승인한다.</div>
      <div class="rule-actions">
        <button class="primary" type="button" onclick="runCodexRuleAutomation()">Codex 자동 룰 개선 시작</button>
        <button class="primary" type="button" onclick="approveRuleProposalForLive()">live 승인 적용</button>
        <button class="secondary" type="button" onclick="linkRuleProposalCommitHash()">커밋 해시 연결</button>
        <button class="secondary" type="button" onclick="appendRuleHistoryCorrection()">히스토리 보정</button>
        <button class="danger-button" type="button" onclick="rollbackRuleProposal()">룰 변경 롤백</button>
      </div>
      <table class="rule-result">
        <tbody id="ruleReviewTable">
          <tr><td>룰 개선 분석을 실행하면 분석 대상 기간, 거래 수, 손절 수, 손실 원인, 변경안, replay 결과, 승인 필요 여부가 표시됩니다.</td></tr>
        </tbody>
      </table>
      <table class="rule-result">
        <tbody id="ruleHistoryTable">
          <tr><td>룰 변경 히스토리가 표시됩니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div id="startPanel" class="start-panel">
      <div id="startMessage" class="note"></div>
      <div class="actions">
        <button id="startTradingButton" class="primary" type="button" onclick="toggleTradingServer()">자동매매 루프 시작</button>
      </div>
    </div>
    <div id="nextSteps" class="next-steps">
      <a class="secondary" href="/health" target="_blank" rel="noreferrer">상태 확인</a>
      <a class="secondary" href="/dashboard" target="_blank" rel="noreferrer">대시보드 열기</a>
      <button class="secondary" type="button" onclick="loadSettings()">설정 다시 불러오기</button>
    </div>
    <div class="danger-zone">
      <label>학습 데이터</label>
      <div class="note">현재 선택된 투자성향의 학습 로그를 보관 폴더로 이동하고 새로 학습을 시작한다. 트레이딩 서버는 중단하지 않는다.</div>
      <div class="actions">
        <button id="resetLearningButton" class="danger-button" type="button" onclick="resetLearningData()">현재 성향 학습데이터 리셋</button>
        <button id="resetDemoTradingButton" class="danger-button" type="button" onclick="resetDemoTradingData()">데모트레이딩데이터 리셋</button>
        <button id="purgeRuntimeDataButton" class="danger-button" type="button" onclick="purgeRuntimeData()">완전 데이터 삭제</button>
      </div>
    </div>
  </section>
</main>
<div id="ruleAutomationModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="ruleAutomationTitle">
  <div class="rule-modal">
    <header>
      <h2 id="ruleAutomationTitle">Codex 자동 룰 개선 진행</h2>
      <div class="note">진행 내용이 길면 아래 영역을 스크롤해서 전체 변경 이유와 결과를 확인하세요.</div>
    </header>
    <div class="rule-modal-body">
      <div id="ruleAutomationSteps"></div>
      <div id="ruleAutomationFinal" class="rule-final hidden"></div>
    </div>
    <div class="rule-modal-footer">
      <button id="ruleAutomationRetry" class="secondary hidden" type="button" onclick="runCodexRuleAutomation()">다시 룰 개선</button>
      <button id="ruleAutomationClose" class="primary hidden" type="button" onclick="closeRuleAutomationModal()">확인</button>
    </div>
  </div>
</div>
<script>
let mode = "demo";
let profiles = [];
let telegramTokenVisible = false;
let telegramTokenLoaded = false;
let latestStartReadiness = null;
let latestTradingStatus = {running: false, startable: false};
let latestRuleReviewId = null;
let latestRuleProposalId = null;
function openRuleAutomationModal() {
  document.getElementById("ruleAutomationModal").classList.add("visible");
  document.getElementById("ruleAutomationSteps").innerHTML = "";
  document.getElementById("ruleAutomationFinal").classList.add("hidden");
  document.getElementById("ruleAutomationFinal").textContent = "";
  document.getElementById("ruleAutomationRetry").classList.add("hidden");
  document.getElementById("ruleAutomationClose").classList.add("hidden");
}
function closeRuleAutomationModal() {
  document.getElementById("ruleAutomationModal").classList.remove("visible");
}
function appendRuleAutomationStep(name, status, message) {
  const steps = document.getElementById("ruleAutomationSteps");
  const item = document.createElement("div");
  item.className = `rule-step ${status}`;
  item.innerHTML = `<strong>${name}</strong><div>${message || ""}</div>`;
  steps.appendChild(item);
}
function renderRuleAutomationResult(payload) {
  document.getElementById("ruleAutomationSteps").innerHTML = "";
  (payload.steps || []).forEach((step) => appendRuleAutomationStep(step.name, step.status, step.message));
  const summary = payload.final_summary || {};
  const changed = (summary.changed_parameters || []).join(", ") || "실제 변경 없음";
  const rejected = (summary.rejection_reasons || []).join(", ") || "없음";
  const replay = summary.replay_result ? JSON.stringify(summary.replay_result, null, 2) : "replay 결과 없음";
  const final = [
    `완료 상태: ${payload.status === "completed" ? "demo 적용 완료" : "추가 개선 필요"}`,
    `바뀐 항목: ${changed}`,
    `변경 이유: ${summary.change_reason || "-"}`,
    `replay 결과: ${replay}`,
    `demo 적용: ${summary.demo_applied ? "완료" : "미완료"}`,
    `live 승인 필요: ${summary.live_requires_approval ? "필요" : "불필요"}`,
    `차단/보류 사유: ${rejected}`
  ].join("\\n");
  const finalBox = document.getElementById("ruleAutomationFinal");
  finalBox.textContent = final;
  finalBox.classList.remove("hidden");
  document.getElementById("ruleAutomationClose").classList.remove("hidden");
  document.getElementById("ruleAutomationRetry").classList.toggle("hidden", !payload.can_retry);
}
function showStatus(message, kind = "") {
  const status = document.getElementById("status");
  status.className = `status visible ${kind}`.trim();
  status.textContent = message;
}
function showNextSteps(visible) {
  document.getElementById("nextSteps").classList.toggle("visible", visible);
}
function showStartPanel(visible, readiness = null, tradingStatus = null) {
  const panel = document.getElementById("startPanel");
  const button = document.getElementById("startTradingButton");
  const message = document.getElementById("startMessage");
  latestStartReadiness = readiness;
  if (tradingStatus) latestTradingStatus = tradingStatus;
  panel.classList.toggle("visible", visible);
  const ready = Boolean(readiness && readiness.ready);
  const running = Boolean(latestTradingStatus && latestTradingStatus.running);
  panel.classList.toggle("blocked", visible && !ready);
  button.style.display = ready ? "inline-flex" : "none";
  button.textContent = running ? "자동매매 루프 중지" : "자동매매 루프 시작";
  button.className = running ? "danger-button" : "primary";
  message.textContent = !visible
    ? ""
    : running
      ? "자동매매 루프가 실행 중입니다. 중지 버튼을 누르면 매매 판단만 멈추고 설정 화면과 서버 프로세스는 유지됩니다."
      : ready
        ? "필수 설정이 저장되었습니다. 자동매매 루프를 시작할 수 있습니다."
        : `아직 시작할 수 없습니다. ${formatReadinessProblems(readiness)}`;
}
function formatReadinessProblems(readiness) {
  if (!readiness) return "필수값을 저장해야 합니다.";
  const parts = [];
  if (readiness.missing && readiness.missing.length) parts.push(`누락: ${readiness.missing.join(", ")}`);
  if (readiness.invalid && readiness.invalid.length) parts.push(`확인 필요: ${readiness.invalid.join(", ")}`);
  return parts.length ? parts.join(" / ") : readiness.message;
}
function setMode(next) {
  mode = next;
  document.querySelectorAll("#modeSwitch button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  document.getElementById("upbitCredentialSection").style.display = mode === "live" ? "block" : "none";
  document.querySelectorAll(".live-required").forEach((mark) => {
    mark.style.display = mode === "live" ? "inline" : "none";
  });
  showStartPanel(false);
}
document.querySelectorAll("#modeSwitch button").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});
function renderProfiles(selected) {
  const select = document.getElementById("tradingProfile");
  select.innerHTML = "";
  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.key;
    option.textContent = profile.label;
    select.appendChild(option);
  });
  select.value = selected || "scalping";
  updateProfileDescription();
}
function updateProfileDescription() {
  const selected = document.getElementById("tradingProfile").value;
  const profile = profiles.find((item) => item.key === selected);
  document.getElementById("profileDescription").textContent = profile
    ? `${profile.description} · 주기 ${profile.auto_interval_sec}초 · 최소 순엣지 ${(profile.min_net_edge_pct * 100).toFixed(2)}%`
    : "";
}
document.getElementById("tradingProfile").addEventListener("change", updateProfileDescription);
function syncTradeMarketFromCoin() {
  const coin = document.getElementById("tradeCoin").value.trim().toUpperCase();
  const marketInput = document.getElementById("tradeMarket");
  const currentMarket = marketInput.value.trim().toUpperCase();
  if (!coin) return;
  document.getElementById("tradeCoin").value = coin;
  if (!currentMarket || currentMarket.startsWith("KRW-")) {
    marketInput.value = `KRW-${coin}`;
  }
}
document.getElementById("tradeCoin").addEventListener("change", syncTradeMarketFromCoin);
function setTelegramTokenHidden(hasToken) {
  const tokenInput = document.getElementById("telegramToken");
  const toggle = document.getElementById("telegramTokenToggle");
  telegramTokenVisible = false;
  telegramTokenLoaded = false;
  tokenInput.type = "password";
  tokenInput.value = hasToken ? "********" : "";
  toggle.setAttribute("aria-label", "텔레그램 봇 토큰 보기");
  toggle.setAttribute("title", "텔레그램 봇 토큰 보기");
}
async function toggleTelegramToken() {
  const tokenInput = document.getElementById("telegramToken");
  const toggle = document.getElementById("telegramTokenToggle");
  if (telegramTokenVisible) {
    tokenInput.type = "password";
    telegramTokenVisible = false;
    toggle.setAttribute("aria-label", "텔레그램 봇 토큰 보기");
    toggle.setAttribute("title", "텔레그램 봇 토큰 보기");
    return;
  }
  if (!telegramTokenLoaded && tokenInput.value && new Set(tokenInput.value.split("")).size === 1 && tokenInput.value[0] === "*") {
    const response = await fetch("/settings/secret/telegram-bot-token");
    const result = await response.json();
    if (!result.found) {
      showStatus("저장된 텔레그램 봇 토큰이 없습니다.", "warning");
      return;
    }
    tokenInput.value = result.value;
    telegramTokenLoaded = true;
  }
  tokenInput.type = "text";
  telegramTokenVisible = true;
  toggle.setAttribute("aria-label", "텔레그램 봇 토큰 숨기기");
  toggle.setAttribute("title", "텔레그램 봇 토큰 숨기기");
}
async function loadSettings() {
  try {
    const response = await fetch("/settings/current");
    const data = await response.json();
    const values = data.values || {};
    profiles = data.profiles || [
      {key: "scalping", label: "단타", description: "짧은 주기로 관찰", auto_interval_sec: 3, min_net_edge_pct: 0.0008}
    ];
    setMode(data.mode || values.TRADING_MODE || "demo");
    renderProfiles(data.profile || values.TRADING_PROFILE || "scalping");
    document.getElementById("serverName").value = values.SERVER_NAME || "";
    document.getElementById("tradeMarket").value = values.TRADE_MARKET || "KRW-XRP";
    document.getElementById("tradeCoin").value = values.TRADE_COIN || "XRP";
    document.getElementById("demoInitialCapital").value = values.DEMO_INITIAL_CAPITAL || "1000000";
    document.getElementById("externalContextEnabled").checked = values.EXTERNAL_CONTEXT_ENABLED !== "false";
    document.getElementById("externalContextCacheTtlSec").value = values.EXTERNAL_CONTEXT_CACHE_TTL_SEC || "300";
    document.getElementById("onchainContextUrl").value = values.ONCHAIN_CONTEXT_URL || "";
    document.getElementById("onchainState").value = values.ONCHAIN_STATE || "neutral";
    document.getElementById("onchainActiveAddressesChangePct").value = values.ONCHAIN_ACTIVE_ADDRESSES_CHANGE_PCT || "0.0";
    document.getElementById("onchainExchangeNetflowState").value = values.ONCHAIN_EXCHANGE_NETFLOW_STATE || "neutral";
    document.getElementById("etfContextUrl").value = values.ETF_CONTEXT_URL || "";
    document.getElementById("etfState").value = values.ETF_STATE || "neutral";
    document.getElementById("etfFlowUsd").value = values.ETF_FLOW_USD || "0.0";
    document.getElementById("noTradeAdaptiveEnabled").checked = values.NO_TRADE_ADAPTIVE_ENABLED !== "false";
    document.getElementById("noTradeRelaxAfterCycles").value = values.NO_TRADE_RELAX_AFTER_CYCLES || "100";
    document.getElementById("noTradeRelaxMinScore").value = values.NO_TRADE_RELAX_MIN_SCORE || "0.18";
    document.getElementById("sidewaysRiskGuardEnabled").checked = values.SIDEWAYS_RISK_GUARD_ENABLED !== "false";
    document.getElementById("sidewaysPriceRangePct").value = values.SIDEWAYS_PRICE_RANGE_PCT || "0.002";
    document.getElementById("sidewaysTradedValueRangePct").value = values.SIDEWAYS_TRADED_VALUE_RANGE_PCT || "0.003";
    document.getElementById("sidewaysMaxAvgAbsReturnPct").value = values.SIDEWAYS_MAX_AVG_ABS_RETURN_PCT || "0.001";
    document.getElementById("sidewaysScaleInMinDiscountPct").value = values.SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT || "0.003";
    document.getElementById("storageDir").value = values.STORAGE_DIR || "./storage";
    document.getElementById("autoRuleUpdateEnabled").checked = values.AUTO_RULE_UPDATE_ENABLED === "true";
    document.getElementById("autoRuleCompletionRate").value = values.AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE || "1.0";
    document.getElementById("autoRuleWinRateSkip").value = values.AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD || "0.8";
    const dataPath = data.data_path_status || {};
    document.getElementById("dataPathStatus").textContent = `로그 ${dataPath.learning_log_dir || "-"} / 데이터셋 ${dataPath.learning_dataset_dir || "-"}`;
    const autoRule = data.auto_rule_update || {};
    document.getElementById("autoRuleStatus").textContent = `현재 ${autoRule.enabled ? "ON" : "OFF"} / 충족률 ${autoRule.learning_completion_rate_required || 1.0} / 승률 기준 ${autoRule.win_rate_skip_threshold || 0.8}`;
    document.getElementById("accessKey").value = values.UPBIT_ACCESS_KEY || "";
    document.getElementById("secretKey").value = values.UPBIT_SECRET_KEY || "";
    setTelegramTokenHidden(values.TELEGRAM_BOT_TOKEN === "***");
    document.getElementById("telegramTokenStatus").textContent = values.TELEGRAM_BOT_TOKEN === "***"
      ? "저장된 봇 토큰이 있습니다. 변경하지 않으면 기존 토큰을 유지합니다."
      : "저장된 봇 토큰이 없습니다.";
    document.getElementById("telegramChat").value = values.TELEGRAM_CHAT_ID || "";
    document.getElementById("telegramUserId").value = values.TELEGRAM_USER_ID || "";
    document.getElementById("telegramUsername").value = values.TELEGRAM_USERNAME || "";
    document.getElementById("telegramAllowFrom").value = values.TELEGRAM_ALLOW_FROM || "";
    showStartPanel(Boolean(data.start_readiness && data.start_readiness.ready), data.start_readiness);
    await refreshTradingStatus(data.start_readiness);
    renderLatestRuleProposal(await fetchJson("/api/v1/rules/proposals"));
    renderRuleHistory(await fetchJson("/api/v1/rules/history"));
  } catch (error) {
    showStatus("현재 설정을 불러오지 못했다. 서버 상태를 확인한 뒤 다시 시도한다.", "warning");
  }
}
function row(label, value) {
  return `<tr><th>${label}</th><td>${value}</td></tr>`;
}
function number(value, digits = 0) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "-";
  return numeric.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}
function signedNumber(value, digits = 0) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "-";
  const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  return `${sign}${number(Math.abs(numeric), digits)}`;
}
async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}
async function postJson(url, body = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}
function renderRulePipeline(payload) {
  const review = payload.review || {};
  const proposal = payload.proposal || {};
  latestRuleReviewId = review.id || proposal.review_id || latestRuleReviewId;
  latestRuleProposalId = proposal.id || latestRuleProposalId;
  const source = proposal.id ? proposal : review;
  const causes = (source.major_loss_causes || []).map((item) => `${item.reason} ${item.count}건`).join(", ") || "데이터 부족";
  const changes = (proposal.codex_suggested_changes || []).map((item) => `${item.parameter}: ${item.proposed_value}`).join(", ") || "변경안 없음";
  const replay = proposal.replay_result ? JSON.stringify(proposal.replay_result) : "replay 필요";
  const reasons = (proposal.rejection_reasons || []).join(", ") || "없음";
  const externalContext = formatRuleExternalContext(source.external_context_summary || {});
  const historyWarnings = formatRuleHistoryWarnings(proposal.history_warnings || []);
  document.getElementById("ruleReviewTable").innerHTML = [
    row("분석 대상 기간", source.analysis_window_days ? `${source.analysis_window_days}일` : "-"),
    row("대상 코인", source.trade_coin || "-"),
    row("룰 로그 경로", source.learning_log_dir || "-"),
    row("거래 수", source.trade_count || 0),
    row("손절 수", source.stop_loss_count || 0),
    row("외부 컨텍스트", externalContext),
    row("히스토리 경고", historyWarnings),
    row("주요 손실 원인", causes),
    row("Codex 제안 변경 항목", changes),
    row("replay 결과", replay),
    row("승인 필요 여부", source.approval_required ? "필요" : "불필요"),
    row("차단/승인 사유", reasons)
  ].join("");
}
function formatRuleExternalContext(summary) {
  const onchain = Object.entries(summary.onchain_state_counts || {}).map(([key, value]) => `${formatContextState(key)} ${value}건`).join(", ") || "없음";
  const etf = Object.entries(summary.etf_state_counts || {}).map(([key, value]) => `${formatContextState(key)} ${value}건`).join(", ") || "없음";
  const flow = `ETF 순흐름 ${signedNumber(summary.etf_flow_usd_total || 0, 0)} USD`;
  return `표본 ${summary.sample_count || 0}건 / 온체인 ${onchain} / ETF ${etf} / 평균 가중치 ${summary.avg_learning_weight || 1} / ${flow}`;
}
function formatContextState(value) {
  const labels = {
    bullish: "강세",
    bearish: "약세",
    neutral: "중립",
    inflow: "자금 유입",
    outflow: "자금 유출",
    disabled: "비활성",
    not_applicable: "해당 없음"
  };
  return labels[value] || value || "-";
}
function formatRuleHistoryWarnings(warnings) {
  return warnings.length
    ? warnings.map((item) => `${item.parameter}: ${item.message}`).join(", ")
    : "없음";
}
function renderLatestRuleProposal(payload) {
  const latest = payload.latest_proposal;
  if (!latest) return;
  renderRulePipeline({proposal: latest});
}
function renderRuleHistory(payload) {
  const history = payload.history || [];
  document.getElementById("ruleHistoryTable").innerHTML = history.length
    ? history.slice(0, 5).map((item) => row(
        `${item.event_type || "-"} / ${item.approval_status || "-"}`,
        `${item.trade_coin || "-"} ${item.changed_parameters ? item.changed_parameters.join(", ") : ""} / ${item.change_reason || "-"}${item.commit_hash ? ` / commit ${item.commit_hash}` : ""}`
      )).join("")
    : '<tr><td>룰 변경 히스토리가 없습니다.</td></tr>';
}
async function refreshRuleHistory() {
  renderRuleHistory(await fetchJson("/api/v1/rules/history"));
}
async function runCodexRuleAutomation() {
  openRuleAutomationModal();
  appendRuleAutomationStep("Codex CLI 룰 개선 하네스 시작", "running", "학습 로그를 읽고 변경안을 생성하는 자동 파이프라인을 실행합니다.");
  try {
    const result = await postJson("/api/v1/rules/auto-improve", {fixture_path: "fixtures/replay_ticks.json"});
    renderRuleAutomationResult(result);
    renderRulePipeline({proposal: result.proposal || {}, review: result.review || {}});
    await refreshRuleHistory();
  } catch (error) {
    appendRuleAutomationStep("자동 룰 개선 실패", "blocked", error.message);
    const finalBox = document.getElementById("ruleAutomationFinal");
    finalBox.textContent = "자동 룰 개선 요청이 실패했습니다. 서버 상태와 replay fixture를 확인한 뒤 다시 실행하세요.";
    finalBox.classList.remove("hidden");
    document.getElementById("ruleAutomationRetry").classList.remove("hidden");
    document.getElementById("ruleAutomationClose").classList.remove("hidden");
  }
}
async function runRuleReview() {
  renderRulePipeline(await postJson("/api/v1/rules/review"));
}
async function createRuleProposal() {
  renderRulePipeline(await postJson("/api/v1/rules/proposals", {review_id: latestRuleReviewId}));
}
async function applyRuleProposalToDemo() {
  if (!latestRuleProposalId) await createRuleProposal();
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/apply-demo`));
}
async function verifyRuleProposalReplay() {
  if (!latestRuleProposalId) await createRuleProposal();
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/replay`, {fixture_path: "fixtures/replay_ticks.json"}));
}
async function approveRuleProposalForLive() {
  if (!latestRuleProposalId) await createRuleProposal();
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/approve-live`, {approved_by: ""}));
}
async function linkRuleProposalCommitHash() {
  if (!latestRuleProposalId) await createRuleProposal();
  const commitHash = window.prompt("연결할 Git 커밋 해시를 입력하세요.", "");
  if (!commitHash) return;
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/commit-hash`, {commit_hash: commitHash}));
  await refreshRuleHistory();
}
async function appendRuleHistoryCorrection() {
  if (!latestRuleProposalId) await createRuleProposal();
  const reason = window.prompt("히스토리 보정 사유를 입력하세요.", "");
  if (!reason) return;
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/history-corrections`, {reason, corrected_fields: {}, corrected_by: "operator"}));
  await refreshRuleHistory();
}
async function rollbackRuleProposal() {
  if (!latestRuleProposalId) await createRuleProposal();
  const reason = window.prompt("룰 변경 롤백 사유를 입력하세요.", "");
  if (!reason) return;
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/rollback`, {reason, target: "demo", rolled_back_by: "operator"}));
  await refreshRuleHistory();
}
async function refreshTradingStatus(readiness = latestStartReadiness) {
  try {
    const response = await fetch("/settings/trading/status");
    const status = await response.json();
    latestTradingStatus = status;
    showStartPanel(Boolean(readiness && readiness.ready), readiness, status);
  } catch (error) {
    latestTradingStatus = {running: false, startable: false};
  }
}
async function saveSettings() {
  const saveButton = document.getElementById("saveButton");
  saveButton.disabled = true;
  showStatus("설정을 저장하는 중...", "pending");
  syncTradeMarketFromCoin();
  const payload = {
    TRADING_MODE: mode,
    SERVER_NAME: document.getElementById("serverName").value,
    TRADING_PROFILE: document.getElementById("tradingProfile").value || "scalping",
    LEARNING_ENABLED: "true",
    TRADE_MARKET: document.getElementById("tradeMarket").value || "KRW-XRP",
    TRADE_COIN: document.getElementById("tradeCoin").value || "XRP",
    DEMO_INITIAL_CAPITAL: document.getElementById("demoInitialCapital").value || "1000000",
    AUTO_TRADING_ENABLED: "true",
    AUTO_TRADING_LIVE_ENABLED: mode === "live" ? "true" : "false",
    EXTERNAL_CONTEXT_ENABLED: document.getElementById("externalContextEnabled").checked ? "true" : "false",
    EXTERNAL_CONTEXT_CACHE_TTL_SEC: document.getElementById("externalContextCacheTtlSec").value || "300",
    ONCHAIN_CONTEXT_SOURCE: document.getElementById("onchainContextUrl").value ? "http" : "manual",
    ONCHAIN_CONTEXT_URL: document.getElementById("onchainContextUrl").value,
    ONCHAIN_STATE: document.getElementById("onchainState").value || "neutral",
    ONCHAIN_ACTIVE_ADDRESSES_CHANGE_PCT: document.getElementById("onchainActiveAddressesChangePct").value || "0.0",
    ONCHAIN_EXCHANGE_NETFLOW_STATE: document.getElementById("onchainExchangeNetflowState").value || "neutral",
    ETF_CONTEXT_SOURCE: document.getElementById("etfContextUrl").value ? "http" : "web",
    ETF_CONTEXT_URL: document.getElementById("etfContextUrl").value,
    ETF_STATE: document.getElementById("etfState").value || "neutral",
    ETF_FLOW_USD: document.getElementById("etfFlowUsd").value || "0.0",
    NO_TRADE_ADAPTIVE_ENABLED: document.getElementById("noTradeAdaptiveEnabled").checked ? "true" : "false",
    NO_TRADE_RELAX_AFTER_CYCLES: document.getElementById("noTradeRelaxAfterCycles").value || "100",
    NO_TRADE_RELAX_MIN_SCORE: document.getElementById("noTradeRelaxMinScore").value || "0.18",
    SIDEWAYS_RISK_GUARD_ENABLED: document.getElementById("sidewaysRiskGuardEnabled").checked ? "true" : "false",
    SIDEWAYS_PRICE_RANGE_PCT: document.getElementById("sidewaysPriceRangePct").value || "0.002",
    SIDEWAYS_TRADED_VALUE_RANGE_PCT: document.getElementById("sidewaysTradedValueRangePct").value || "0.003",
    SIDEWAYS_MAX_AVG_ABS_RETURN_PCT: document.getElementById("sidewaysMaxAvgAbsReturnPct").value || "0.001",
    SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT: document.getElementById("sidewaysScaleInMinDiscountPct").value || "0.003",
    STORAGE_DIR: document.getElementById("storageDir").value || "./storage",
    AUTO_RULE_UPDATE_ENABLED: document.getElementById("autoRuleUpdateEnabled").checked ? "true" : "false",
    AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE: document.getElementById("autoRuleCompletionRate").value || "1.0",
    AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD: document.getElementById("autoRuleWinRateSkip").value || "0.8",
    TELEGRAM_BOT_TOKEN: document.getElementById("telegramToken").value,
    TELEGRAM_CHAT_ID: document.getElementById("telegramChat").value,
    TELEGRAM_USER_ID: document.getElementById("telegramUserId").value,
    TELEGRAM_USERNAME: document.getElementById("telegramUsername").value,
    TELEGRAM_ALLOW_FROM: document.getElementById("telegramAllowFrom").value
  };
  if (mode === "live") {
    payload.UPBIT_ACCESS_KEY = document.getElementById("accessKey").value;
    payload.UPBIT_SECRET_KEY = document.getElementById("secretKey").value;
  }
  try {
    const response = await fetch("/settings", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    showStatus(
      result.saved
        ? `저장됨: ${mode.toUpperCase()} 모드, 투자성향 ${document.getElementById("tradingProfile").selectedOptions[0].textContent}.`
        : result.message,
      result.saved ? "" : "warning"
    );
    showNextSteps(false);
    showStartPanel(Boolean(result.saved), result.start_readiness);
    await refreshTradingStatus(result.start_readiness);
  } catch (error) {
    showStatus("저장 요청에 실패했다. 서버가 실행 중인지 확인한 뒤 다시 시도한다.", "warning");
    showNextSteps(false);
    showStartPanel(false);
  } finally {
    saveButton.disabled = false;
  }
}
async function sendTelegramTest() {
  showStatus("텔레그램 테스트 메시지를 전송하는 중...", "pending");
  try {
    const response = await fetch("/settings/telegram/test", {method: "POST"});
    const result = await response.json();
    showStatus(result.message || (result.sent ? "텔레그램 테스트 메시지를 전송했습니다." : "텔레그램 테스트 메시지를 전송하지 못했습니다."), result.sent ? "" : "warning");
  } catch (error) {
    showStatus("텔레그램 테스트 메시지 전송 요청에 실패했습니다.", "warning");
  }
}
async function toggleTradingServer() {
  if (latestTradingStatus && latestTradingStatus.running) {
    await stopTradingServer();
    return;
  }
  await startTradingServer();
}
async function startTradingServer() {
  const button = document.getElementById("startTradingButton");
  button.disabled = true;
  showStatus("자동매매 루프를 시작하는 중...", "pending");
  try {
    const response = await fetch("/settings/trading/start", {method: "POST"});
    const result = await response.json();
    if (result.started) {
      showStatus(result.message || "자동매매 루프가 시작되었습니다.");
      showNextSteps(true);
      await refreshTradingStatus(result.start_readiness || latestStartReadiness);
      return;
    }
    showStatus(result.message || "자동매매 루프를 시작하지 못했습니다.", "warning");
    showStartPanel(true, result.start_readiness || latestStartReadiness);
  } catch (error) {
    showStatus("자동매매 루프 시작 요청에 실패했습니다.", "warning");
  } finally {
    button.disabled = false;
  }
}
async function stopTradingServer() {
  if (!confirm("자동매매 루프를 중지할까요? 서버 화면은 유지되지만 매수/매도 판단은 멈춥니다.")) return;
  const button = document.getElementById("startTradingButton");
  button.disabled = true;
  showStatus("자동매매 루프를 중지하는 중...", "pending");
  try {
    const response = await fetch("/settings/trading/stop", {method: "POST"});
    const result = await response.json();
    if (result.stopped || result.status === "already_stopped") {
      showStatus(result.message || "자동매매 루프가 중지되었습니다.");
      showNextSteps(true);
      await refreshTradingStatus(latestStartReadiness);
      return;
    }
    showStatus(result.message || "자동매매 루프를 중지하지 못했습니다.", "warning");
    await refreshTradingStatus(latestStartReadiness);
  } catch (error) {
    showStatus("자동매매 루프 중지 요청에 실패했습니다.", "warning");
  } finally {
    button.disabled = false;
  }
}
async function resetLearningData() {
  const button = document.getElementById("resetLearningButton");
  const profile = document.getElementById("tradingProfile").selectedOptions[0]?.textContent || "현재 성향";
  if (!confirm(`${profile} 학습 데이터를 리셋할까요? 기존 파일은 보관 폴더로 이동됩니다.`)) return;
  button.disabled = true;
  showStatus("학습 데이터를 리셋하는 중...", "pending");
  try {
    const response = await fetch("/settings/learning/reset", {method: "POST"});
    const result = await response.json();
    showStatus(
      result.reset
        ? `학습 데이터 리셋 완료. 새 로그: ${result.log_path}${result.archive_path ? `, 보관: ${result.archive_path}` : ""}`
        : result.message,
      result.reset ? "" : "warning"
    );
    showNextSteps(true);
  } catch (error) {
    showStatus("학습 데이터 리셋 요청에 실패했다. 서버 상태를 확인한 뒤 다시 시도한다.", "warning");
  } finally {
    button.disabled = false;
  }
}
async function resetDemoTradingData() {
  const button = document.getElementById("resetDemoTradingButton");
  if (!confirm("현재 데모 매수/매도 데이터와 포지션 상태를 리셋할까요? 학습 로그 파일은 유지됩니다.")) return;
  button.disabled = true;
  showStatus("데모 트레이딩 데이터를 리셋하는 중...", "pending");
  try {
    const response = await fetch("/settings/demo-trading/reset", {method: "POST"});
    const result = await response.json();
    showStatus(
      result.reset
        ? `데모 트레이딩 데이터 리셋 완료. 현금 ${result.cash_balance} KRW, 보유 ${result.asset_balance} ${result.asset_currency}`
        : result.message,
      result.reset ? "" : "warning"
    );
    showNextSteps(true);
  } catch (error) {
    showStatus("데모 트레이딩 데이터 리셋 요청에 실패했다. 서버 상태를 확인한 뒤 다시 시도한다.", "warning");
  } finally {
    button.disabled = false;
  }
}
async function purgeRuntimeData() {
  const button = document.getElementById("purgeRuntimeDataButton");
  const profile = document.getElementById("tradingProfile").selectedOptions[0]?.textContent || "현재 성향";
  if (!confirm(`${profile} 학습 로그와 데모 매매 데이터를 보관 없이 완전히 삭제하고 초기화할까요?`)) return;
  const phrase = prompt("완전 삭제를 진행하려면 아래에 '완전삭제'를 입력하세요.");
  if (phrase !== "완전삭제") {
    showStatus("완전 삭제가 취소되었습니다.", "warning");
    return;
  }
  button.disabled = true;
  showStatus("데이터를 보관 없이 완전 삭제하는 중...", "pending");
  try {
    const response = await fetch("/settings/data/purge", {method: "POST"});
    const result = await response.json();
    showStatus(
      result.reset
        ? `완전 삭제 완료. 새 학습 로그: ${result.learning_log_path}${result.deleted_paths?.length ? `, 삭제/초기화: ${result.deleted_paths.join(", ")}` : ""}`
        : result.message,
      result.reset ? "" : "warning"
    );
    showNextSteps(true);
    await refreshTradingStatus(latestStartReadiness);
  } catch (error) {
    showStatus("완전 데이터 삭제 요청에 실패했다. 서버 상태를 확인한 뒤 다시 시도한다.", "warning");
  } finally {
    button.disabled = false;
  }
}
loadSettings();
</script>
</body>
</html>
"""
