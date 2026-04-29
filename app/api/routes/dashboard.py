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
    .status-line { margin-top: 10px; min-height: 28px; color: var(--muted); font-size: 13px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    main.wrap { padding-top: 18px; }
    .grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; min-width: 0; }
    .metric-card { min-height: 156px; display: flex; flex-direction: column; }
    .card h2 { margin: 0 0 10px; font-size: 15px; }
    .metric { min-height: 34px; font-size: 28px; font-weight: 800; line-height: 1.1; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
    .sub { margin-top: 6px; min-height: 36px; color: var(--muted); font-size: 13px; line-height: 1.35; }
    .price-stack { min-height: 92px; display: grid; grid-template-rows: 20px 34px 26px; align-content: start; row-gap: 6px; }
    .price-market { color: var(--muted); font-size: 14px; font-weight: 800; line-height: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .price-line { font-size: 24px; font-weight: 800; line-height: 34px; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .price-trend-line { min-height: 26px; line-height: 26px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .badge { display: inline-flex; align-items: center; min-height: 24px; padding: 0 8px; border-radius: 999px; background: var(--soft); color: var(--text); font-size: 12px; font-weight: 800; }
    .ok { background: #e8f6ed; color: #1f6b35; }
    .warn { background: #fff4d6; color: #7a5400; }
    .danger { background: #fff1f0; color: #b42318; }
    .price-up { color: #b42318; }
    .price-down { color: #145ea8; }
    .price-flat { color: var(--text); }
    .trend-up { background: #fff1f0; color: #b42318; border: 1px solid #f1b8b1; }
    .trend-down { background: #e7f1ff; color: #145ea8; border: 1px solid #b7d7ff; }
    .trend-flat { background: #ffffff; color: #172026; border: 1px solid #d8e0e6; }
    .neutral { background: #edf2f5; color: #33424c; }
    .observe { background: #e7f1ff; color: #145ea8; }
    .analysis { background: #f1e8ff; color: #6941c6; }
    .entry { background: #fff4d6; color: #7a5400; }
    .execute { background: #fff1f0; color: #b42318; }
    .manage { background: #e8f6ed; color: #1f6b35; }
    .blocked { background: #7f1d1d; color: #ffffff; }
    .panel { margin-top: 12px; display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 12px; }
    main.wrap > .card { margin-top: 12px; }
    .section-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .section-grid .card { min-height: 126px; }
    .progress { height: 12px; overflow: hidden; border-radius: 999px; background: var(--soft); }
    .bar { height: 100%; width: 0%; background: var(--primary); transition: width 160ms ease; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; }
    .empty { color: var(--muted); font-size: 13px; padding: 12px 0; }
    .table-box { min-height: 268px; overflow: hidden; }
    .state-panel { min-height: 366px; }
    .metric-table tbody { display: table-row-group; }
    .ai-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .ai-item { min-height: 78px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); }
    .ai-label { color: var(--muted); font-size: 12px; font-weight: 700; }
    .ai-value { margin-top: 8px; font-size: 18px; font-weight: 800; font-variant-numeric: tabular-nums; }
    .legend { margin-top: 12px; }
    .legend-toggle { margin-top: 12px; }
    .legend-panel { display: none; }
    .legend-panel.visible { display: block; }
    .theme-switch { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 10px; border: 1px solid #9eb0bd; border-radius: 999px; background: var(--surface); color: var(--text); font-size: 13px; font-weight: 700; cursor: pointer; }
    .toggle { position: relative; width: 38px; height: 20px; border-radius: 999px; background: #9eb0bd; }
    .toggle::after { content: ""; position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: white; transition: transform 120ms ease; }
    body.dark .toggle { background: var(--primary); }
    body.dark .toggle::after { transform: translateX(18px); }
    @media (max-width: 900px) {
      .grid, .ai-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
    <div class="card metric-card">
      <h2>실행 모드</h2>
      <div id="modeMetric" class="metric">-</div>
      <div id="modeSub" class="sub">-</div>
    </div>
    <div class="card metric-card">
      <h2>현재 가격</h2>
      <div class="price-stack">
        <div id="priceMarket" class="price-market">-</div>
        <div id="priceMetric" class="price-line">-</div>
        <div id="priceSub" class="price-trend-line">-</div>
      </div>
    </div>
    <div class="card metric-card">
      <h2>투자금</h2>
      <div id="capitalMetric" class="metric">-</div>
      <div id="capitalSub" class="sub">-</div>
    </div>
    <div class="card metric-card">
      <h2>학습 완료율</h2>
      <div id="learningProgressMetric" class="metric">-</div>
      <div class="progress"><div id="learningProgressBar" class="bar"></div></div>
      <div id="learningProgressSub" class="sub">-</div>
    </div>
    <div class="card metric-card">
      <h2>수익 성공률</h2>
      <div id="winRateMetric" class="metric">-</div>
      <div id="winRateSub" class="sub">-</div>
    </div>
    <div class="card metric-card">
      <h2>손익</h2>
      <div id="pnlMetric" class="metric">-</div>
      <div id="pnlSub" class="sub">-</div>
    </div>
  </section>

  <section class="card">
    <h2>AI 운용 모드</h2>
    <div class="ai-grid">
      <div class="ai-item">
        <div class="ai-label">AI 상태</div>
        <div id="aiState" class="ai-value">-</div>
      </div>
      <div class="ai-item">
        <div class="ai-label">자동매매</div>
        <div id="autoTradingState" class="ai-value">-</div>
      </div>
      <div class="ai-item">
        <div class="ai-label">리스크 등급</div>
        <div id="riskGrade" class="ai-value">-</div>
      </div>
      <div class="ai-item">
        <div class="ai-label">마지막 분석</div>
        <div id="lastAnalysisAt" class="ai-value">-</div>
      </div>
    </div>
    <button id="legendToggle" class="btn legend-toggle" type="button" onclick="toggleAiLegend()">상태 설명 펼치기</button>
    <div id="aiLegend" class="legend-panel">
      <table class="legend">
        <thead><tr><th>상태</th><th>의미</th><th>색상</th></tr></thead>
        <tbody>
          <tr><td><span class="badge neutral">대기</span></td><td>AI는 켜져 있지만 아직 분석 전</td><td>회색</td></tr>
          <tr><td><span class="badge observe">관찰 중</span></td><td>시장 데이터 수집 중</td><td>파란색</td></tr>
          <tr><td><span class="badge analysis">분석 중</span></td><td>AI가 매수/매도 조건 판단 중</td><td>보라색</td></tr>
          <tr><td><span class="badge entry">진입 대기</span></td><td>조건은 거의 충족, 최종 확인 중</td><td>노란색</td></tr>
          <tr><td><span class="badge execute">주문 실행</span></td><td>실제 매수/매도 주문 중</td><td>빨간색</td></tr>
          <tr><td><span class="badge manage">포지션 관리</span></td><td>이미 진입했고 익절/손절 관리 중</td><td>초록색</td></tr>
          <tr><td><span class="badge neutral">중지됨</span></td><td>사용자가 중지했거나 오류 발생</td><td>회색/검정</td></tr>
          <tr><td><span class="badge blocked">위험 차단</span></td><td>급변동, API 오류, 손실 제한 등으로 자동 중단</td><td>진한 빨간색</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <div class="card state-panel">
      <h2>현재 상황</h2>
      <div id="sections" class="section-grid"></div>
    </div>
    <div class="card table-box">
      <h2>학습 상태</h2>
      <table class="metric-table">
        <tbody id="learningTable"></tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <div class="card table-box">
      <h2>최근 체결</h2>
      <table>
        <thead><tr><th>구분</th><th>상태</th><th>가격</th><th>수량</th></tr></thead>
        <tbody id="executionsTable"></tbody>
      </table>
    </div>
    <div class="card table-box">
      <h2>실거래 전환 준비</h2>
      <table class="metric-table">
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

function toggleAiLegend() {
  const legend = document.getElementById("aiLegend");
  const visible = !legend.classList.contains("visible");
  legend.classList.toggle("visible", visible);
  document.getElementById("legendToggle").textContent = visible ? "상태 설명 접기" : "상태 설명 펼치기";
}

function number(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "데이터 부족";
  const pct = Number(value) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

function price(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "데이터 없음";
  return `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 4 })} KRW`;
}

function displayMarket(market) {
  if (!market) return "마켓";
  const parts = String(market).split("-");
  return parts.length === 2 ? `${parts[1]}-${parts[0]}` : String(market);
}

function trendClass(trend) {
  if (trend === "UP") return "price-up";
  if (trend === "DOWN") return "price-down";
  return "price-flat";
}

function trendBadgeClass(trend) {
  if (trend === "UP") return "trend-up";
  if (trend === "DOWN") return "trend-down";
  return "trend-flat";
}

function deriveTrendStreak(market) {
  const history = Array.isArray(market.history) ? market.history : [];
  const prices = history
    .map((item) => Number(item.price))
    .filter((value) => !Number.isNaN(value));
  if (market.current_price !== undefined && Number(market.current_price) !== prices[prices.length - 1]) {
    prices.push(Number(market.current_price));
  }
  if (prices.length < 2) {
    const trend = market.state_label || "FLAT";
    return {trend, count: prices.length ? 1 : 0};
  }
  const lastDiff = prices[prices.length - 1] - prices[prices.length - 2];
  const trend = lastDiff > 0 ? "UP" : lastDiff < 0 ? "DOWN" : "FLAT";
  let count = 1;
  for (let index = prices.length - 2; index > 0; index -= 1) {
    const diff = prices[index] - prices[index - 1];
    const currentTrend = diff > 0 ? "UP" : diff < 0 ? "DOWN" : "FLAT";
    if (currentTrend !== trend) break;
    count += 1;
  }
  return {trend, count};
}

function severityClass(severity) {
  if (severity === "critical") return "badge danger";
  if (severity === "warning") return "badge warn";
  return "badge ok";
}

function row(label, value) {
  return `<tr><th>${label}</th><td>${value}</td></tr>`;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, 19);
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
  return parts;
}

function aiBadge(label, className) {
  return `<span class="badge ${className}">${label}</span>`;
}

function setTextWithTitle(elementId, text) {
  const element = document.getElementById(elementId);
  element.textContent = text;
  element.title = text;
}

function setHtmlWithTitle(elementId, html, title) {
  const element = document.getElementById(elementId);
  element.innerHTML = html;
  element.title = title;
}

function deriveAiState({health, summary, market, executions}) {
  const latestExecution = (executions.history || []).slice(-1)[0];
  const hasPosition = Number(summary.coin_balance || 0) > 0;
  if (health.hard_stop) {
    return {ai: ["위험 차단", "blocked"], trading: ["중지됨", "neutral"], risk: ["위험 차단", "blocked"]};
  }
  if (!health.trading_ready || health.safe_mode) {
    return {ai: ["중지됨", "neutral"], trading: ["중지됨", "neutral"], risk: ["높음", "execute"]};
  }
  if (latestExecution && latestExecution.status === "filled") {
    return {ai: ["주문 실행", "execute"], trading: ["대기", "neutral"], risk: ["보통", "entry"]};
  }
  if (hasPosition) {
    return {ai: ["포지션 관리", "manage"], trading: ["대기", "neutral"], risk: ["보통", "entry"]};
  }
  if (market.current_price !== undefined) {
    return {ai: ["관찰 중", "observe"], trading: ["대기", "neutral"], risk: ["보통", "entry"]};
  }
  return {ai: ["대기", "neutral"], trading: ["대기", "neutral"], risk: ["보통", "entry"]};
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
  const trendStreak = deriveTrendStreak(market);
  const changeClass = trendClass(trendStreak.trend);
  const marketLabel = displayMarket(market.market);
  const priceText = market.current_price === undefined ? "데이터 없음" : `${price(market.current_price)} (${percent(market.recent_change_pct)})`;
  const trendText = market.current_price === undefined ? `${market.market || "마켓"} 현재가 데이터가 아직 없습니다.` : `${market.market || marketLabel} ${trendStreak.trend}(${trendStreak.count})`;
  setTextWithTitle("priceMarket", marketLabel);
  setHtmlWithTitle(
    "priceMetric",
    market.current_price === undefined
      ? "데이터 없음"
      : `${price(market.current_price)} <span class="${changeClass}">(${percent(market.recent_change_pct)})</span>`,
    priceText
  );
  setHtmlWithTitle(
    "priceSub",
    market.current_price === undefined
      ? trendText
      : `${market.market || marketLabel} <span class="badge ${trendBadgeClass(trendStreak.trend)}">${trendStreak.trend}(${trendStreak.count})</span>`,
    trendText
  );
  document.getElementById("capitalMetric").textContent = `${number(summary.cash_balance, 0)} KRW`;
  document.getElementById("capitalSub").textContent = summary.trading_mode === "demo" ? "데모 가상 투자금 1,000,000 KRW 기준" : "실계좌 사용 가능 현금 기준";
  document.getElementById("learningProgressMetric").textContent = `${progress}%`;
  document.getElementById("learningProgressBar").style.width = `${progress}%`;
  document.getElementById("learningProgressSub").textContent = `${totalEvents}/${LEARNING_TARGET_EVENTS} 이벤트 기록 기준. 신호 ${summary.learning_signal_count || 0}건, 체결 ${summary.learning_fill_count || 0}건.`;
  document.getElementById("winRateMetric").textContent = percent(winRate);
  document.getElementById("winRateSub").textContent = winRate === null ? "완료된 거래 손익 기록이 쌓이면 표시됩니다." : "현재 기록 기준 수익 거래 비율입니다.";
  document.getElementById("pnlMetric").textContent = `${number(summary.realized_pnl, 2)} KRW`;
  document.getElementById("pnlSub").textContent = `미실현 손익 ${number(summary.unrealized_pnl, 2)} KRW, 매수 ${summary.buy_count || 0}건, 매도 ${summary.sell_count || 0}건`;
  const aiState = deriveAiState({health, summary, market, executions});
  document.getElementById("aiState").innerHTML = aiBadge(aiState.ai[0], aiState.ai[1]);
  document.getElementById("autoTradingState").innerHTML = aiBadge(aiState.trading[0], aiState.trading[1]);
  document.getElementById("riskGrade").innerHTML = aiBadge(aiState.risk[0], aiState.risk[1]);
  document.getElementById("lastAnalysisAt").textContent = formatDateTime(market.recorded_at || summary.last_signal_recorded_at || summary.last_fill_recorded_at);

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
setInterval(refreshDashboard, 1000);
</script>
</body>
</html>
"""
