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
    .next-steps { display: none; margin-top: 12px; gap: 8px; flex-wrap: wrap; }
    .next-steps.visible { display: flex; }
    .start-panel { display: none; margin-top: 14px; padding: 12px; border: 1px solid #b7d7bd; border-radius: 6px; background: #edf8ef; }
    .start-panel.visible { display: block; }
    .start-panel.blocked { border-color: #f1b8b1; background: #fff1f0; color: #8a1f13; }
    .secondary { display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 0 12px; border: 1px solid #9eb0bd; border-radius: 6px; background: white; color: #172026; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; }
    .note { color: #52616d; font-size: 13px; line-height: 1.45; }
  </style>
</head>
<body>
<main>
  <section>
    <h1>설정</h1>
    <div class="note">demo 모드는 API 키 없이 학습/검증용으로 실행할 수 있다. live 모드는 저장 시 업비트 API 키가 필요하다.</div>
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
    <label for="accessKey">업비트 액세스 키<span class="required-mark live-required">*</span></label>
    <input id="accessKey" autocomplete="off">
    <label for="secretKey">업비트 시크릿 키<span class="required-mark live-required">*</span></label>
    <input id="secretKey" type="password" autocomplete="off">
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
    </div>
    <div class="actions">
      <button id="saveButton" class="primary" type="button" onclick="saveSettings()">저장</button>
      <span id="status" class="status"></span>
    </div>
    <div class="subsection">
      <label>룰 개선</label>
      <div class="note">즉시 반영이 아니라 분석, 변경안 생성, replay 검증, demo 적용, 승인 후 live 반영 순서로 진행한다.</div>
      <div class="rule-actions">
        <button class="secondary" type="button" onclick="runRuleReview()">룰 개선 분석 실행</button>
        <button class="secondary" type="button" onclick="createRuleProposal()">룰 변경안 생성</button>
        <button class="secondary" type="button" onclick="applyRuleProposalToDemo()">demo 적용</button>
        <button class="primary" type="button" onclick="approveRuleProposalForLive()">live 승인 적용</button>
      </div>
      <table class="rule-result">
        <tbody id="ruleReviewTable">
          <tr><td>룰 개선 분석을 실행하면 분석 대상 기간, 거래 수, 손절 수, 손실 원인, 변경안, replay 결과, 승인 필요 여부가 표시됩니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div id="startPanel" class="start-panel">
      <div id="startMessage" class="note"></div>
      <div class="actions">
        <button id="startTradingButton" class="primary" type="button" onclick="toggleTradingServer()">트레이딩 서버 시작</button>
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
      </div>
    </div>
  </section>
</main>
<script>
let mode = "demo";
let profiles = [];
let telegramTokenVisible = false;
let telegramTokenLoaded = false;
let latestStartReadiness = null;
let latestTradingStatus = {running: false, startable: false};
let latestRuleReviewId = null;
let latestRuleProposalId = null;
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
  button.textContent = running ? "트레이딩 서버 중지" : "트레이딩 서버 시작";
  button.className = running ? "danger-button" : "primary";
  message.textContent = !visible
    ? ""
    : running
      ? "트레이딩 서버가 실행 중입니다. 중지 버튼을 누르면 자동매매 루프만 멈추고 설정 화면은 유지됩니다."
      : ready
        ? "필수 설정이 저장되었습니다. 트레이딩 서버를 시작할 수 있습니다."
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
    document.getElementById("tradeMarket").value = values.TRADE_MARKET || "KRW-XRP";
    document.getElementById("tradeCoin").value = values.TRADE_COIN || "XRP";
    document.getElementById("demoInitialCapital").value = values.DEMO_INITIAL_CAPITAL || "1000000";
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
  } catch (error) {
    showStatus("현재 설정을 불러오지 못했다. 서버 상태를 확인한 뒤 다시 시도한다.", "warning");
  }
}
function row(label, value) {
  return `<tr><th>${label}</th><td>${value}</td></tr>`;
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
  document.getElementById("ruleReviewTable").innerHTML = [
    row("분석 대상 기간", source.analysis_window_days ? `${source.analysis_window_days}일` : "-"),
    row("거래 수", source.trade_count || 0),
    row("손절 수", source.stop_loss_count || 0),
    row("주요 손실 원인", causes),
    row("Codex 제안 변경 항목", changes),
    row("replay 결과", replay),
    row("승인 필요 여부", source.approval_required ? "필요" : "불필요"),
    row("차단/승인 사유", reasons)
  ].join("");
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
async function approveRuleProposalForLive() {
  if (!latestRuleProposalId) await createRuleProposal();
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/approve-live`, {approved_by: ""}));
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
  const payload = {
    TRADING_MODE: mode,
    TRADING_PROFILE: document.getElementById("tradingProfile").value || "scalping",
    LEARNING_ENABLED: "true",
    TRADE_MARKET: document.getElementById("tradeMarket").value || "KRW-XRP",
    TRADE_COIN: document.getElementById("tradeCoin").value || "XRP",
    DEMO_INITIAL_CAPITAL: document.getElementById("demoInitialCapital").value || "1000000",
    AUTO_TRADING_ENABLED: "true",
    AUTO_TRADING_LIVE_ENABLED: mode === "live" ? "true" : "false",
    UPBIT_ACCESS_KEY: document.getElementById("accessKey").value,
    UPBIT_SECRET_KEY: document.getElementById("secretKey").value,
    TELEGRAM_BOT_TOKEN: document.getElementById("telegramToken").value,
    TELEGRAM_CHAT_ID: document.getElementById("telegramChat").value,
    TELEGRAM_USER_ID: document.getElementById("telegramUserId").value,
    TELEGRAM_USERNAME: document.getElementById("telegramUsername").value,
    TELEGRAM_ALLOW_FROM: document.getElementById("telegramAllowFrom").value
  };
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
  showStatus("트레이딩 서버를 시작하는 중...", "pending");
  try {
    const response = await fetch("/settings/trading/start", {method: "POST"});
    const result = await response.json();
    if (result.started) {
      showStatus(result.message || "트레이딩 서버가 시작되었습니다.");
      showNextSteps(true);
      await refreshTradingStatus(result.start_readiness || latestStartReadiness);
      return;
    }
    showStatus(result.message || "트레이딩 서버를 시작하지 못했습니다.", "warning");
    showStartPanel(true, result.start_readiness || latestStartReadiness);
  } catch (error) {
    showStatus("트레이딩 서버 시작 요청에 실패했습니다.", "warning");
  } finally {
    button.disabled = false;
  }
}
async function stopTradingServer() {
  const button = document.getElementById("startTradingButton");
  button.disabled = true;
  showStatus("트레이딩 서버를 중지하는 중...", "pending");
  try {
    const response = await fetch("/settings/trading/stop", {method: "POST"});
    const result = await response.json();
    if (result.stopped || result.status === "already_stopped") {
      showStatus(result.message || "트레이딩 서버가 중지되었습니다.");
      showNextSteps(true);
      await refreshTradingStatus(latestStartReadiness);
      return;
    }
    showStatus(result.message || "트레이딩 서버를 중지하지 못했습니다.", "warning");
    await refreshTradingStatus(latestStartReadiness);
  } catch (error) {
    showStatus("트레이딩 서버 중지 요청에 실패했습니다.", "warning");
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
loadSettings();
</script>
</body>
</html>
"""
