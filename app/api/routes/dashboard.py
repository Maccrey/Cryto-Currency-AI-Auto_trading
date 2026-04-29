from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services.dashboard.executions_facade import DashboardExecutionsFacade
from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.learning_facade import DashboardLearningFacade
from app.services.dashboard.market_facade import DashboardMarketFacade
from app.services.dashboard.positions_facade import DashboardPositionsFacade
from app.services.dashboard.recovery_facade import DashboardRecoveryFacade
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.recovery.orchestrator import BootState


def build_dashboard_router(
    *,
    boot_state: BootState,
    trading_mode: str,
    learning_enabled: bool,
    dashboard_summary_facade: DashboardSummaryFacade,
    dashboard_market_facade: DashboardMarketFacade,
    dashboard_executions_facade: DashboardExecutionsFacade,
    dashboard_positions_facade: DashboardPositionsFacade,
    dashboard_learning_facade: DashboardLearningFacade,
    dashboard_recovery_facade: DashboardRecoveryFacade,
    promotion_dashboard_facade: PromotionDashboardFacade,
) -> APIRouter:
    router = APIRouter(prefix="/dashboard")

    @router.get("", response_class=HTMLResponse)
    def dashboard_page() -> str:
        return DASHBOARD_HTML

    @router.get("/summary")
    def dashboard_summary() -> dict[str, object]:
        return dashboard_summary_facade.build_response(
            boot_state=boot_state,
            trading_mode=trading_mode,
            learning_enabled=learning_enabled,
        )

    @router.get("/market")
    def dashboard_market(history_limit: int = 20) -> dict[str, object]:
        return dashboard_market_facade.build_current_response(
            history_limit=history_limit,
        )

    @router.get("/executions")
    def dashboard_executions(limit: int = 20) -> dict[str, object]:
        return dashboard_executions_facade.build_history_response(limit=limit)

    @router.get("/positions/history")
    def dashboard_positions_history(limit: int = 20) -> dict[str, object]:
        return dashboard_positions_facade.build_history_response(limit=limit)

    @router.get("/learning")
    def dashboard_learning(limit: int = 20) -> dict[str, object]:
        return dashboard_learning_facade.build_response(limit=limit)

    @router.get("/learning/health")
    def dashboard_learning_health(limit: int = 50) -> dict[str, object]:
        return dashboard_learning_facade.build_health_response(limit=limit)

    @router.get("/recovery")
    def dashboard_recovery(limit: int = 20) -> dict[str, object]:
        return dashboard_recovery_facade.build_response(limit=limit)

    @router.get("/promotion")
    def dashboard_promotion() -> dict[str, object]:
        return promotion_dashboard_facade.build_current_response()

    @router.get("/promotion/history")
    def dashboard_promotion_history() -> dict[str, object]:
        return promotion_dashboard_facade.build_history_response()

    return router


DASHBOARD_HTML = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Dashboard</title>
  <style>
    :root { color-scheme: light; --bg: #f3f6f8; --surface: #ffffff; --text: #172026; --muted: #52616d; --border: #d8e0e6; --soft: #edf2f5; --primary: #1769aa; }
    body.dark { color-scheme: dark; --bg: #12181d; --surface: #1d252c; --text: #ecf2f6; --muted: #a9b7c2; --border: #34434e; --soft: #29343d; --primary: #4ea1dc; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; }
    header { background: var(--surface); border-bottom: 1px solid var(--border); }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 22px 20px; }
    .top { display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap; }
    h1 { margin: 0; font-size: 24px; }
    .nav { display: flex; gap: 8px; flex-wrap: wrap; }
    .btn { display: inline-flex; align-items: center; justify-content: center; min-height: 36px; padding: 0 12px; border: 1px solid #9eb0bd; border-radius: 6px; background: var(--surface); color: var(--text); font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; }
    .primary { background: var(--primary); color: white; border-color: var(--primary); }
    .status-line { margin-top: 10px; color: var(--muted); font-size: 13px; }
    main.wrap { padding-top: 18px; }
    .grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; min-width: 0; }
    .card h2 { margin: 0 0 10px; font-size: 15px; }
    .metric { font-size: 28px; font-weight: 800; line-height: 1.1; overflow-wrap: anywhere; }
    .sub { margin-top: 6px; color: var(--muted); font-size: 13px; line-height: 1.35; }
    .badge { display: inline-flex; align-items: center; min-height: 24px; padding: 0 8px; border-radius: 999px; background: var(--soft); color: var(--text); font-size: 12px; font-weight: 800; }
    .ok { background: #e8f6ed; color: #1f6b35; }
    .warn { background: #fff4d6; color: #7a5400; }
    .danger { background: #fff1f0; color: #b42318; }
    .panel { margin-top: 12px; display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 12px; }
    .section-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .progress { height: 12px; overflow: hidden; border-radius: 999px; background: var(--soft); }
    .bar { height: 100%; width: 0%; background: var(--primary); transition: width 160ms ease; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; }
    .empty { color: var(--muted); font-size: 13px; padding: 12px 0; }
    .theme-switch { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 10px; border: 1px solid #9eb0bd; border-radius: 999px; background: var(--surface); color: var(--text); font-size: 13px; font-weight: 700; cursor: pointer; }
    .toggle { position: relative; width: 38px; height: 20px; border-radius: 999px; background: #9eb0bd; }
    .toggle::after { content: ""; position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: white; transition: transform 120ms ease; }
    body.dark .toggle { background: var(--primary); }
    body.dark .toggle::after { transform: translateX(18px); }
    @media (max-width: 900px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .panel { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .grid, .section-grid { grid-template-columns: 1fr; }
      .wrap { padding-left: 14px; padding-right: 14px; }
    }
  </style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>자동매매 대시보드</h1>
        <div id="statusLine" class="status-line">데이터를 불러오는 중...</div>
      </div>
      <nav class="nav">
        <button id="themeToggle" class="theme-switch" type="button" onclick="toggleTheme()"><span class="toggle"></span><span id="themeLabel">다크모드</span></button>
        <button class="btn primary" type="button" onclick="refreshDashboard()">새로고침</button>
        <a class="btn" href="/settings">설정</a>
        <a class="btn" href="/health" target="_blank" rel="noreferrer">상태 API</a>
      </nav>
    </div>
  </div>
</header>
<main class="wrap">
  <section class="grid">
    <div class="card">
      <h2>실행 모드</h2>
      <div id="modeMetric" class="metric">-</div>
      <div id="modeSub" class="sub">-</div>
    </div>
    <div class="card">
      <h2>현재 가격</h2>
      <div id="priceMetric" class="metric">-</div>
      <div id="priceSub" class="sub">-</div>
    </div>
    <div class="card">
      <h2>학습 완료율</h2>
      <div id="learningProgressMetric" class="metric">-</div>
      <div class="progress"><div id="learningProgressBar" class="bar"></div></div>
      <div id="learningProgressSub" class="sub">-</div>
    </div>
    <div class="card">
      <h2>수익 성공률</h2>
      <div id="winRateMetric" class="metric">-</div>
      <div id="winRateSub" class="sub">-</div>
    </div>
    <div class="card">
      <h2>손익</h2>
      <div id="pnlMetric" class="metric">-</div>
      <div id="pnlSub" class="sub">-</div>
    </div>
  </section>

  <section class="panel">
    <div class="card">
      <h2>현재 상황</h2>
      <div id="sections" class="section-grid"></div>
    </div>
    <div class="card">
      <h2>학습 상태</h2>
      <table>
        <tbody id="learningTable"></tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <div class="card">
      <h2>최근 체결</h2>
      <table>
        <thead><tr><th>구분</th><th>상태</th><th>가격</th><th>수량</th></tr></thead>
        <tbody id="executionsTable"></tbody>
      </table>
    </div>
    <div class="card">
      <h2>실거래 전환 준비</h2>
      <table>
        <tbody id="promotionTable"></tbody>
      </table>
    </div>
  </section>
</main>
<script>
const LEARNING_TARGET_EVENTS = 50;
const THEME_KEY = "cryptoDashboardTheme";

function applyTheme(theme) {
  document.body.classList.toggle("dark", theme === "dark");
  document.getElementById("themeLabel").textContent = theme === "dark" ? "라이트모드" : "다크모드";
  localStorage.setItem(THEME_KEY, theme);
}

function toggleTheme() {
  applyTheme(document.body.classList.contains("dark") ? "light" : "dark");
}

function number(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "데이터 부족";
  return `${Math.round(Number(value) * 100)}%`;
}

function price(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "데이터 없음";
  return `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 4 })} KRW`;
}

function severityClass(severity) {
  if (severity === "critical") return "badge danger";
  if (severity === "warning") return "badge warn";
  return "badge ok";
}

function row(label, value) {
  return `<tr><th>${label}</th><td>${value}</td></tr>`;
}

function deriveWinRate(summary, promotion) {
  const metrics = promotion && promotion.metrics ? promotion.metrics : null;
  if (metrics && metrics.win_rate !== undefined) return metrics.win_rate;
  if (!summary.sell_count) return null;
  if (summary.realized_pnl > 0) return 1;
  if (summary.realized_pnl < 0) return 0;
  return null;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}

async function refreshDashboard() {
  document.getElementById("statusLine").textContent = "데이터를 불러오는 중...";
  try {
    const [health, summary, marketResponse, learningResponse, learningHealthResponse, executions, promotionResponse] = await Promise.all([
      fetchJson("/health"),
      fetchJson("/dashboard/summary"),
      fetchJson("/dashboard/market"),
      fetchJson("/dashboard/learning"),
      fetchJson("/dashboard/learning/health"),
      fetchJson("/dashboard/executions"),
      fetchJson("/dashboard/promotion")
    ]);
    renderDashboard({
      health,
      summary,
      learning: learningResponse.learning || {},
      learningHealth: learningHealthResponse.health || {},
      executions,
      promotion: promotionResponse.promotion,
      market: marketResponse.summary || {market: marketResponse.market}
    });
  } catch (error) {
    document.getElementById("statusLine").textContent = `대시보드 데이터를 불러오지 못했다: ${error.message}`;
  }
}

function renderDashboard(data) {
  const {health, summary, market, learning, learningHealth, executions, promotion} = data;
  const totalEvents = learning.total_events || learningHealth.total_events || 0;
  const progress = Math.min(100, Math.round((totalEvents / LEARNING_TARGET_EVENTS) * 100));
  const winRate = deriveWinRate(summary, promotion);
  const readyBadge = health.trading_ready ? '<span class="badge ok">거래 준비됨</span>' : '<span class="badge warn">점검 필요</span>';
  const learningBadge = summary.learning_enabled ? '<span class="badge ok">학습 기록 중</span>' : '<span class="badge warn">학습 비활성</span>';

  document.getElementById("statusLine").innerHTML = `${readyBadge} ${learningBadge}`;
  document.getElementById("modeMetric").textContent = String(summary.trading_mode || health.mode).toUpperCase();
  document.getElementById("modeSub").textContent = summary.trading_mode === "live" ? "실제 주문 모드입니다. API 키와 리스크 상태를 계속 확인하세요." : "데모 주문 모드입니다. API 키 없이 학습과 검증을 진행합니다.";
  document.getElementById("priceMetric").textContent = price(market.current_price);
  document.getElementById("priceSub").textContent = market.current_price === undefined ? `${market.market || "마켓"} 현재가 데이터가 아직 없습니다.` : `${market.market} ${percent(market.recent_change_pct)} ${market.state_label || ""} · ${market.recorded_at || "시각 없음"}`;
  document.getElementById("learningProgressMetric").textContent = `${progress}%`;
  document.getElementById("learningProgressBar").style.width = `${progress}%`;
  document.getElementById("learningProgressSub").textContent = `${totalEvents}/${LEARNING_TARGET_EVENTS} 이벤트 기록 기준. 신호 ${summary.learning_signal_count || 0}건, 체결 ${summary.learning_fill_count || 0}건.`;
  document.getElementById("winRateMetric").textContent = percent(winRate);
  document.getElementById("winRateSub").textContent = winRate === null ? "완료된 거래 손익 기록이 쌓이면 표시됩니다." : "현재 기록 기준 수익 거래 비율입니다.";
  document.getElementById("pnlMetric").textContent = `${number(summary.realized_pnl, 2)} KRW`;
  document.getElementById("pnlSub").textContent = `미실현 손익 ${number(summary.unrealized_pnl, 2)} KRW, 매수 ${summary.buy_count || 0}건, 매도 ${summary.sell_count || 0}건`;

  document.getElementById("sections").innerHTML = (summary.sections || []).map((section) => `
    <div class="card">
      <h2>${section.name}</h2>
      <span class="${severityClass(section.severity)}">${section.state_label}</span>
      <div class="sub">${section.state_message}</div>
      <div class="sub">${section.recommended_action}</div>
    </div>
  `).join("");

  const categories = learningHealth.category_counts || {};
  document.getElementById("learningTable").innerHTML = [
    row("총 이벤트", number(totalEvents)),
    row("최근 이벤트", learning.last_event_name || "없음"),
    row("최근 기록 시각", learning.last_recorded_at || learningHealth.last_recorded_at || "없음"),
    row("신호/체결/포지션", `${number(categories.signals || 0)} / ${number(categories.fills || 0)} / ${number(categories.positions || 0)}`),
    row("상태", learning.state_message || learningHealth.state_message || "학습 데이터가 아직 없습니다.")
  ].join("");

  const history = executions.history || [];
  document.getElementById("executionsTable").innerHTML = history.length
    ? history.slice(-8).reverse().map((item) => `
        <tr><td>${item.side}</td><td>${item.status}</td><td>${number(item.filled_price, 4)}</td><td>${number(item.filled_quantity, 6)}</td></tr>
      `).join("")
    : '<tr><td colspan="4" class="empty">아직 체결 기록이 없습니다.</td></tr>';

  const promotionMetrics = promotion && promotion.metrics ? promotion.metrics : {};
  document.getElementById("promotionTable").innerHTML = [
    row("준비 상태", summary.promotion_ready ? '<span class="badge ok">준비됨</span>' : '<span class="badge warn">미준비</span>'),
    row("승률", promotionMetrics.win_rate === undefined ? "데이터 부족" : percent(promotionMetrics.win_rate)),
    row("수익 팩터", promotionMetrics.profit_factor === undefined ? "데이터 부족" : number(promotionMetrics.profit_factor, 2)),
    row("최대 낙폭", promotionMetrics.max_drawdown === undefined ? "데이터 부족" : percent(promotionMetrics.max_drawdown)),
    row("최근 검토", summary.last_promotion_reviewed_at || "없음")
  ].join("");
}

applyTheme(localStorage.getItem(THEME_KEY) || "light");
refreshDashboard();
setInterval(refreshDashboard, 10000);
</script>
</body>
</html>
"""
