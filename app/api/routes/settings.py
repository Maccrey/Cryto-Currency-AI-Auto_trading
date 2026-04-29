from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services.config.env_file import EnvFileService


def build_settings_router(*, env_file_service: EnvFileService) -> APIRouter:
    router = APIRouter(prefix="/settings")

    @router.get("", response_class=HTMLResponse)
    def settings_page() -> str:
        return SETTINGS_HTML

    @router.get("/current")
    def current_settings() -> dict[str, object]:
        return env_file_service.current()

    @router.post("")
    def save_settings(payload: dict[str, object]) -> dict[str, object]:
        return env_file_service.save(payload)

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
    input { box-sizing: border-box; width: 100%; padding: 10px 12px; border: 1px solid #b8c4ce; border-radius: 6px; font-size: 14px; }
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
    .next-steps { display: none; margin-top: 12px; gap: 8px; flex-wrap: wrap; }
    .next-steps.visible { display: flex; }
    .secondary { display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 0 12px; border: 1px solid #9eb0bd; border-radius: 6px; background: white; color: #172026; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; }
    .note { color: #52616d; font-size: 13px; line-height: 1.45; }
  </style>
</head>
<body>
<main>
  <section>
    <h1>설정</h1>
    <div class="note">demo 모드는 API 키 없이 학습/검증용으로 실행할 수 있다. live 모드는 저장 시 업비트 API 키가 필요하다.</div>
    <label>거래 모드</label>
    <div id="modeSwitch" class="switch">
      <button type="button" data-mode="demo">DEMO</button>
      <button type="button" data-mode="live">LIVE</button>
    </div>
    <div class="row">
      <div>
        <label for="tradeMarket">마켓</label>
        <input id="tradeMarket" placeholder="KRW-XRP">
      </div>
      <div>
        <label for="tradeCoin">코인</label>
        <input id="tradeCoin" placeholder="XRP">
      </div>
    </div>
    <label for="accessKey">업비트 액세스 키</label>
    <input id="accessKey" autocomplete="off">
    <label for="secretKey">업비트 시크릿 키</label>
    <input id="secretKey" type="password" autocomplete="off">
    <label for="telegramToken">텔레그램 봇 토큰</label>
    <input id="telegramToken" type="password" autocomplete="off">
    <label for="telegramChat">텔레그램 채팅 ID</label>
    <input id="telegramChat" autocomplete="off">
    <div class="actions">
      <button id="saveButton" class="primary" type="button" onclick="saveSettings()">저장</button>
      <span id="status" class="status"></span>
    </div>
    <div id="nextSteps" class="next-steps">
      <a class="secondary" href="/health" target="_blank" rel="noreferrer">상태 확인</a>
      <a class="secondary" href="/dashboard" target="_blank" rel="noreferrer">대시보드 열기</a>
      <button class="secondary" type="button" onclick="loadSettings()">설정 다시 불러오기</button>
    </div>
  </section>
</main>
<script>
let mode = "demo";
function showStatus(message, kind = "") {
  const status = document.getElementById("status");
  status.className = `status visible ${kind}`.trim();
  status.textContent = message;
}
function showNextSteps(visible) {
  document.getElementById("nextSteps").classList.toggle("visible", visible);
}
function setMode(next) {
  mode = next;
  document.querySelectorAll("#modeSwitch button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
}
document.querySelectorAll("#modeSwitch button").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});
async function loadSettings() {
  try {
    const response = await fetch("/settings/current");
    const data = await response.json();
    const values = data.values || {};
    setMode(data.mode || values.TRADING_MODE || "demo");
    document.getElementById("tradeMarket").value = values.TRADE_MARKET || "KRW-XRP";
    document.getElementById("tradeCoin").value = values.TRADE_COIN || "XRP";
    document.getElementById("telegramChat").value = values.TELEGRAM_CHAT_ID || "";
  } catch (error) {
    showStatus("현재 설정을 불러오지 못했다. 서버 상태를 확인한 뒤 다시 시도한다.", "warning");
  }
}
async function saveSettings() {
  const saveButton = document.getElementById("saveButton");
  saveButton.disabled = true;
  showStatus("설정을 저장하는 중...", "pending");
  const payload = {
    TRADING_MODE: mode,
    LEARNING_ENABLED: "true",
    TRADE_MARKET: document.getElementById("tradeMarket").value || "KRW-XRP",
    TRADE_COIN: document.getElementById("tradeCoin").value || "XRP",
    UPBIT_ACCESS_KEY: document.getElementById("accessKey").value,
    UPBIT_SECRET_KEY: document.getElementById("secretKey").value,
    TELEGRAM_BOT_TOKEN: document.getElementById("telegramToken").value,
    TELEGRAM_CHAT_ID: document.getElementById("telegramChat").value
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
        ? `저장됨: ${mode.toUpperCase()} 모드. 현재 실행 상태는 상태 확인에서 볼 수 있다. 모드나 API 키를 바꾼 경우 앱 재시작 후 런타임에 반영된다.`
        : result.message,
      result.saved ? "" : "warning"
    );
    showNextSteps(Boolean(result.saved));
  } catch (error) {
    showStatus("저장 요청에 실패했다. 서버가 실행 중인지 확인한 뒤 다시 시도한다.", "warning");
    showNextSteps(false);
  } finally {
    saveButton.disabled = false;
  }
}
loadSettings();
</script>
</body>
</html>
"""
