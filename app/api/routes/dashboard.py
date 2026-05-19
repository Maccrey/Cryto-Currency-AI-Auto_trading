from __future__ import annotations

from collections.abc import Callable

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
    trading_profile: str,
    trading_profile_label: str,
    learning_enabled: bool,
    dashboard_summary_facade: DashboardSummaryFacade,
    dashboard_market_facade: DashboardMarketFacade,
    dashboard_executions_facade: DashboardExecutionsFacade,
    dashboard_positions_facade: DashboardPositionsFacade,
    dashboard_learning_facade: DashboardLearningFacade,
    dashboard_recovery_facade: DashboardRecoveryFacade,
    promotion_dashboard_facade: PromotionDashboardFacade,
    external_context_provider: Callable[[], dict[str, object]] | None = None,
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
            trading_profile=trading_profile,
            trading_profile_label=trading_profile_label,
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

    @router.get("/external-context")
    def dashboard_external_context() -> dict[str, object]:
        if external_context_provider is None:
            return {
                "status": "not_configured",
                "context": None,
            }
        return {
            "status": "ok",
            "context": external_context_provider(),
        }

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
    .runtime-pill { display: none; align-items: center; justify-content: center; min-height: 36px; width: 258px; padding: 0 12px; box-sizing: border-box; border: 1px solid #f97316; border-radius: 6px; background: #f97316; color: #ffffff; font-size: 13px; font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; flex: 0 0 258px; }
    .runtime-pill.visible { display: inline-flex; }
    .status-line { margin-top: 10px; min-height: 28px; color: var(--muted); font-size: 13px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    main.wrap { padding-top: 18px; }
    .grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; min-width: 0; }
    .metric-card { min-height: 156px; display: flex; flex-direction: column; }
    .card h2 { margin: 0 0 10px; font-size: 15px; }
    .metric { min-height: 34px; font-size: 28px; font-weight: 800; line-height: 1.1; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
    .flip-number { display: inline-flex; align-items: baseline; gap: 1px; row-gap: 3px; max-width: 100%; min-width: 0; white-space: normal; flex-wrap: wrap; perspective: 900px; font-variant-numeric: tabular-nums; }
    .flip-char { display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; min-width: 0.34em; height: 1.04em; line-height: 1em; }
    .flip-unit { min-width: 0; height: auto; padding-left: 1px; font-size: 0.58em; line-height: 1; opacity: 0.82; white-space: nowrap; }
    .flip-slot { position: relative; display: inline-block; flex: 0 0 auto; min-width: 0.62em; height: 1.04em; line-height: 1em; overflow: hidden; perspective: 900px; border-radius: 4px; vertical-align: baseline; background: linear-gradient(#f8fafc 0 49%, #e7eef4 50% 100%); box-shadow: inset 0 0 0 1px rgba(82, 97, 109, 0.22); }
    body.dark .flip-slot { background: linear-gradient(#2a3540 0 49%, #202a33 50% 100%); box-shadow: inset 0 0 0 1px rgba(169, 183, 194, 0.22); }
    .flip-slot::after { content: ""; position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: rgba(82, 97, 109, 0.26); transform: translateY(-50%); z-index: 3; }
    body.dark .flip-slot::after { background: rgba(169, 183, 194, 0.24); }
    .flip-card-old, .flip-card-new, .flip-card-static { position: absolute; inset: 0; display: inline-flex; align-items: center; justify-content: center; backface-visibility: hidden; transform-origin: 50% 50%; will-change: transform; }
    .flip-card-old { animation: flip-clock-old 760ms cubic-bezier(.2, .75, .25, 1) forwards; }
    .flip-card-new { transform: translateY(-55%) rotateX(-90deg); animation: flip-clock-new 760ms cubic-bezier(.2, .75, .25, 1) forwards; }
    @keyframes flip-clock-old {
      0% { transform: translateY(0) rotateX(0deg); opacity: 1; }
      48% { transform: translateY(54%) rotateX(88deg); opacity: 0.72; }
      100% { transform: translateY(62%) rotateX(90deg); opacity: 0; }
    }
    @keyframes flip-clock-new {
      0% { transform: translateY(-62%) rotateX(-90deg); opacity: 0; }
      48% { transform: translateY(-54%) rotateX(-88deg); opacity: 0.78; }
      100% { transform: translateY(0) rotateX(0deg); opacity: 1; }
    }
    .sub { margin-top: 6px; min-height: 36px; color: var(--muted); font-size: 13px; line-height: 1.35; }
    .price-stack { min-height: 104px; display: grid; grid-template-rows: 20px minmax(30px, auto) 18px minmax(26px, auto); align-content: start; row-gap: 4px; }
    .price-market { color: var(--muted); font-size: 14px; font-weight: 800; line-height: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .price-line { min-height: 30px; font-size: 24px; font-weight: 800; line-height: 30px; font-variant-numeric: tabular-nums; white-space: normal; overflow: visible; }
    .price-change-line { font-size: 11px; font-weight: 800; line-height: 18px; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .price-trend-line { min-height: 26px; font-size: 13px; line-height: 1.35; white-space: normal; overflow: visible; overflow-wrap: anywhere; }
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
    .sub-line { display: block; margin-top: 2px; }
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
    .context-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .context-item.half { grid-column: span 2; }
    .context-item { min-height: 78px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); }
    .context-label { color: var(--muted); font-size: 12px; font-weight: 700; }
    .context-value { margin-top: 8px; font-size: 16px; font-weight: 800; overflow-wrap: anywhere; white-space: pre-line; }
    .context-value.compact { font-size: 13px; line-height: 1.45; font-weight: 700; }
    .context-value.usd-price { font-size: 26px; line-height: 1.15; font-weight: 800; }
    .context-value.usd-price span { font-size: 13px; line-height: 1.3; font-weight: 800; }
    .context-value.usd-price .krw-price { display: inline-block; margin-top: 4px; font-size: 13px; line-height: 1.3; color: var(--text); }
    .exchange-sim { display: grid; grid-template-columns: 1fr 1.15fr; gap: 12px; align-items: stretch; }
    .exchange-stage { min-height: 240px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); padding: 14px; display: grid; gap: 12px; }
    .ticker-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .ticker-cell { min-height: 58px; padding: 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
    .ticker-label { color: var(--muted); font-size: 11px; font-weight: 800; }
    .ticker-value { margin-top: 4px; font-size: 15px; font-weight: 900; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .ai-crew { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .agent-card { min-height: 126px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); padding: 12px; display: flex; flex-direction: column; gap: 10px; }
    .agent-avatar { width: 46px; height: 46px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: var(--soft); color: var(--text); font-size: 13px; font-weight: 900; border: 1px solid var(--border); }
    .agent-title { font-size: 13px; font-weight: 900; }
    .agent-status { color: var(--muted); font-size: 12px; line-height: 1.35; }
    .variant-board { min-height: 240px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); padding: 14px; }
    .variant-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .variant-card { min-height: 142px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); padding: 12px; }
    .variant-card.active { border-color: #f97316; box-shadow: inset 0 0 0 2px rgba(249, 115, 22, 0.28); }
    .variant-title { font-size: 14px; font-weight: 900; }
    .variant-score { margin-top: 8px; font-size: 22px; font-weight: 900; font-variant-numeric: tabular-nums; }
    .variant-desc { margin-top: 8px; color: var(--muted); font-size: 12px; line-height: 1.35; }
    .variant-reason { margin-top: 12px; color: var(--muted); font-size: 13px; line-height: 1.45; white-space: pre-line; }
    .profit-chart { width: 100%; height: 180px; display: block; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); }
    .profit-chart polyline { fill: none; stroke: var(--primary); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
    .profit-chart .market-price-line { stroke: #f97316; stroke-width: 2; stroke-dasharray: 5 4; opacity: 0.8; }
    .profit-chart .market-price-point { fill: #f97316; stroke: var(--surface); stroke-width: 2; }
    .profit-chart .price-axis-label { fill: #facc15; font-size: 11px; font-weight: 800; text-anchor: end; }
    .profit-chart .axis { stroke: var(--border); stroke-width: 1; }
    .profit-chart .trade-marker { stroke: var(--surface); stroke-width: 2; cursor: help; }
    .profit-chart .trade-marker.buy { fill: #b42318; }
    .profit-chart .trade-marker.sell { fill: #145ea8; }
    .profit-chart .trade-marker.stop-loss { fill: #facc15; }
    .legend { margin-top: 12px; }
    .legend-toggle { margin-top: 12px; }
    .legend-panel { display: none; }
    .legend-panel.visible { display: block; }
    .theme-switch { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 10px; border: 1px solid #9eb0bd; border-radius: 999px; background: var(--surface); color: var(--text); font-size: 13px; font-weight: 700; cursor: pointer; }
    .toggle { position: relative; width: 38px; height: 20px; border-radius: 999px; background: #9eb0bd; }
    .toggle::after { content: ""; position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: white; transition: transform 120ms ease; }
    body.dark .toggle { background: var(--primary); }
    body.dark .toggle::after { transform: translateX(18px); }
    .action-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
    .rule-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .rule-item { min-height: 78px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); }
    .rule-label { color: var(--muted); font-size: 12px; font-weight: 700; }
    .rule-value { margin-top: 8px; font-size: 16px; font-weight: 800; overflow-wrap: anywhere; }
    .modal-backdrop { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; padding: 20px; background: rgba(15, 23, 42, 0.56); z-index: 50; }
    .modal-backdrop.visible { display: flex; }
    .rule-modal { width: min(780px, 100%); max-height: min(82vh, 760px); display: flex; flex-direction: column; border-radius: 8px; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 18px 48px rgba(15, 23, 42, 0.32); overflow: hidden; }
    .rule-modal header { padding: 16px 18px; border-bottom: 1px solid var(--border); }
    .rule-modal h2 { margin: 0; font-size: 18px; }
    .rule-modal-body { padding: 16px 18px; overflow-y: auto; line-height: 1.45; }
    .rule-step { padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
    .rule-step strong { display: block; margin-bottom: 4px; }
    .rule-step.completed strong { color: #1f6b35; }
    .rule-step.blocked strong { color: #b42318; }
    .rule-step.running strong { color: var(--primary); }
    .rule-final { margin-top: 14px; padding: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); white-space: pre-line; font-size: 13px; }
    .rule-modal-footer { padding: 12px 18px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
    .hidden { display: none !important; }
    @media (max-width: 900px) {
      .grid, .ai-grid, .rule-grid, .context-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .exchange-sim { grid-template-columns: 1fr; }
      .panel { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .grid, .section-grid, .rule-grid, .context-grid, .ticker-strip, .ai-crew, .variant-grid { grid-template-columns: 1fr; }
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
        <span id="tradingRuntime" class="runtime-pill" title="트레이딩 운영시간"></span>
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
        <div id="priceChange" class="price-change-line">-</div>
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
    <h2>24시간 수익률</h2>
    <svg id="profitRateChart" class="profit-chart" viewBox="0 0 720 180" role="img" aria-label="24시간 수익률 선그래프"></svg>
    <div id="profitRateChartSub" class="sub">-</div>
  </section>

  <section class="card">
    <h2>코인거래소 시뮬레이션</h2>
    <div class="exchange-sim">
      <div class="exchange-stage">
        <div class="ticker-strip">
          <div class="ticker-cell"><div class="ticker-label">현재가</div><div id="simTickerPrice" class="ticker-value">-</div></div>
          <div class="ticker-cell"><div class="ticker-label">장세</div><div id="simTickerRegime" class="ticker-value">-</div></div>
          <div class="ticker-cell"><div class="ticker-label">운용상태</div><div id="simTickerAction" class="ticker-value">-</div></div>
        </div>
        <div class="ai-crew">
          <div class="agent-card"><div class="agent-avatar">AI-A</div><div class="agent-title">분석 AI</div><div id="agentAnalysis" class="agent-status">-</div></div>
          <div class="agent-card"><div class="agent-avatar">AI-R</div><div class="agent-title">리스크 AI</div><div id="agentRisk" class="agent-status">-</div></div>
          <div class="agent-card"><div class="agent-avatar">AI-X</div><div class="agent-title">실행 AI</div><div id="agentExecution" class="agent-status">-</div></div>
        </div>
      </div>
      <div class="variant-board">
        <h2>데모 룰 A/B/C 내부 테스트</h2>
        <div id="ruleVariantBoard" class="variant-grid">
          <div class="variant-card"><div class="variant-title">룰 A</div><div class="variant-score">-</div><div class="variant-desc">대기 중</div></div>
          <div class="variant-card"><div class="variant-title">룰 B</div><div class="variant-score">-</div><div class="variant-desc">대기 중</div></div>
          <div class="variant-card"><div class="variant-title">룰 C</div><div class="variant-score">-</div><div class="variant-desc">대기 중</div></div>
        </div>
        <div id="ruleVariantReason" class="variant-reason">데모 모드에서 매매 판단이 실행되면 최근 학습 테스트 점수와 선택 이유가 표시됩니다.</div>
      </div>
    </div>
  </section>

  <section class="card">
    <h2>온체인/ETF 상황</h2>
    <div class="context-grid">
      <div class="context-item"><div class="context-label">USD 가격</div><div id="contextUsdPrice" class="context-value usd-price">-</div></div>
      <div class="context-item"><div class="context-label">온체인 데이터</div><div id="onchainState" class="context-value compact">-</div></div>
      <div class="context-item"><div class="context-label">ETF 상태</div><div id="etfState" class="context-value compact">-</div></div>
      <div class="context-item"><div class="context-label">학습 가중치</div><div id="contextWeight" class="context-value">-</div></div>
      <div class="context-item half"><div class="context-label">수집 상태</div><div id="contextStatus" class="context-value">-</div></div>
      <div class="context-item half"><div class="context-label">기록 시각</div><div id="contextRecordedAt" class="context-value">-</div></div>
    </div>
  </section>

  <section class="card">
    <h2>무거래 진단</h2>
    <div class="context-grid">
      <div class="context-item"><div class="context-label">진단 상태</div><div id="noTradeDiagnosis" class="context-value compact">-</div></div>
      <div class="context-item"><div class="context-label">대응안</div><div id="noTradeMitigation" class="context-value compact">-</div></div>
      <div class="context-item"><div class="context-label">차단 사유</div><div id="noTradeBlockedReasons" class="context-value compact">-</div></div>
      <div class="context-item"><div class="context-label">외부 컨텍스트</div><div id="noTradeExternalContext" class="context-value compact">-</div></div>
      <div class="context-item"><div class="context-label">스캔 이벤트</div><div id="noTradeEventsScanned" class="context-value compact">-</div></div>
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
        <thead><tr><th>일시</th><th>구분</th><th>상태</th><th>가격</th><th>수량</th></tr></thead>
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

  <section class="card">
    <h2>룰 개선</h2>
    <div class="action-row">
      <button class="btn primary" type="button" onclick="runCodexRuleAutomation()">Codex 자동 룰 개선 시작</button>
      <button class="btn primary" type="button" onclick="approveRuleProposalForLive()">live 승인 적용</button>
      <button class="btn" type="button" onclick="linkRuleProposalCommitHash()">커밋 해시 연결</button>
      <button class="btn" type="button" onclick="appendRuleHistoryCorrection()">히스토리 보정</button>
      <button class="btn danger" type="button" onclick="rollbackRuleProposal()">룰 변경 롤백</button>
    </div>
    <div class="rule-grid">
      <div class="rule-item"><div class="rule-label">분석 대상 기간</div><div id="ruleWindow" class="rule-value">-</div></div>
      <div class="rule-item"><div class="rule-label">거래 수</div><div id="ruleTrades" class="rule-value">-</div></div>
      <div class="rule-item"><div class="rule-label">손절 수</div><div id="ruleStopLosses" class="rule-value">-</div></div>
      <div class="rule-item"><div class="rule-label">승인 필요</div><div id="ruleApproval" class="rule-value">-</div></div>
    </div>
    <table>
      <tbody id="ruleReviewTable">
        <tr><td class="empty">룰 개선 분석을 실행하면 결과가 표시됩니다.</td></tr>
      </tbody>
    </table>
    <table>
      <tbody id="ruleHistoryTable">
        <tr><td class="empty">룰 변경 히스토리가 표시됩니다.</td></tr>
      </tbody>
    </table>
  </section>
</main>
<div id="ruleAutomationModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="ruleAutomationTitle">
  <div class="rule-modal">
    <header>
      <h2 id="ruleAutomationTitle">Codex 자동 룰 개선 진행</h2>
      <div class="sub">진행 내용이 길면 아래 영역을 스크롤해서 전체 변경 이유와 결과를 확인하세요.</div>
    </header>
    <div class="rule-modal-body">
      <div id="ruleAutomationSteps"></div>
      <div id="ruleAutomationFinal" class="rule-final hidden"></div>
    </div>
    <div class="rule-modal-footer">
      <button id="ruleAutomationRetry" class="btn hidden" type="button" onclick="runCodexRuleAutomation()">다시 룰 개선</button>
      <button id="ruleAutomationClose" class="btn primary hidden" type="button" onclick="closeRuleAutomationModal()">확인</button>
    </div>
  </div>
</div>
<script>
const THEME_KEY = "cryptoDashboardTheme";
let latestRuleReviewId = null;
let latestRuleProposalId = null;
let dashboardRefreshInFlight = false;
let dashboardSlowRefreshInFlight = false;
let lastSlowDashboardRefreshAt = 0;
let cachedRuleProposalResponse = {latest_proposal: null, proposals: []};
let cachedRuleHistoryResponse = {history: []};
let cachedExternalContextResponse = {context: {}};
let cachedDiagnosticsResponse = {diagnostics: {}};
const DASHBOARD_REFRESH_INTERVAL_MS = 3000;
const DASHBOARD_SLOW_REFRESH_INTERVAL_MS = 10000;
const AUTO_RULE_READY_KEY = "cryptoDashboardAutoRuleImproveReady";
let autoRuleImproveInFlight = false;

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

function signedNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toLocaleString("ko-KR", { maximumFractionDigits: digits })}`;
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "데이터 부족";
  const pct = Number(value) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

function usd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "데이터 없음";
  return `$${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 4 })}`;
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

function changeClass(value) {
  const numeric = Number(value);
  if (numeric > 0) return "price-up";
  if (numeric < 0) return "price-down";
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

function formatTradingRuntime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return `${days}day ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function renderTradingRuntime(status) {
  const runtime = document.getElementById("tradingRuntime");
  if (!status || !status.running) {
    runtime.classList.remove("visible");
    runtime.textContent = "";
    return;
  }
  runtime.textContent = `트레이딩 운영시간 : ${formatTradingRuntime(status.uptime_sec)}`;
  runtime.classList.add("visible");
}

function renderExchangeSimulation({market, tradingStatus, winRate}) {
  const lastCycle = tradingStatus && tradingStatus.last_cycle ? tradingStatus.last_cycle : {};
  const shadow = lastCycle.rule_variant_shadow || {};
  const results = Array.isArray(shadow.results) ? shadow.results : [];
  const statusLabel = tradingStatus && tradingStatus.running ? "자동매매 실행 중" : "자동매매 대기";
  const actionLabel = lastCycle.status
    ? `${formatCycleStatus(lastCycle.status)}${lastCycle.reason ? " / " + formatBlockedReason(lastCycle.reason) : ""}`
    : statusLabel;

  document.getElementById("simTickerPrice").textContent = market.current_price === undefined ? "-" : price(market.current_price);
  document.getElementById("simTickerRegime").textContent = market.market_state_label || "-";
  document.getElementById("simTickerAction").textContent = actionLabel;
  document.getElementById("agentAnalysis").textContent = lastCycle.signal_level
    ? `신호 ${lastCycle.signal_level}, 점수 ${number(lastCycle.signal_score || 0, 3)}`
    : "가격, 거래량, 장세 데이터를 수집 중입니다.";
  document.getElementById("agentRisk").textContent = `장세 ${market.market_state_label || "-"}, 성공률 ${percent(winRate)}`;
  document.getElementById("agentExecution").textContent = shadow.leader_label
    ? `${shadow.leader_label} 수익률 우세, 실제 주문 룰은 변경하지 않음`
    : "A/B/C 동시 테스트 결과를 기다리는 중입니다.";

  const fallback = [
    {variant_key: "A", variant_label: "룰 A 안정형", description: "기본 신호를 그대로 사용", profit_rate: null, last_action: "대기"},
    {variant_key: "B", variant_label: "룰 B 추세형", description: "상승 추세에서만 주문 크기 확대", profit_rate: null, last_action: "대기"},
    {variant_key: "C", variant_label: "룰 C 방어형", description: "하락장과 박스권에서 방어", profit_rate: null, last_action: "대기"}
  ];
  const rows = results.length ? results : fallback;
  document.getElementById("ruleVariantBoard").innerHTML = rows.map((item) => {
    const active = item.variant_key && item.variant_key === shadow.leader_key ? " active" : "";
    const scoreText = item.profit_rate === null || item.profit_rate === undefined ? "-" : percent(item.profit_rate);
    const actionText = item.last_action ? `최근 ${formatTradeAction(item.last_action)}` : "대기";
    return `<div class="variant-card${active}">
      <div class="variant-title">${item.variant_label || "룰"}</div>
      <div class="variant-score">${scoreText}</div>
      <div class="variant-desc">${actionText}<br>실현손익 ${number(item.realized_pnl || 0, 0)} KRW<br>${item.description || ""}</div>
    </div>`;
  }).join("");
  document.getElementById("ruleVariantReason").textContent = shadow.leader_reason || "데모 모드에서 같은 실시간 데이터를 기준으로 A/B/C 가상 포트폴리오를 동시에 테스트합니다.";
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

function setFlipTextWithTitle(elementId, text, title = text) {
  const element = document.getElementById(elementId);
  const previous = element.dataset.flipText;
  const changed = previous !== text;
  element.dataset.flipText = text;
  element.title = title;
  element.classList.add("flip-number");
  if (!changed) {
    fitFlipTextToContainer(element);
    return;
  }
  if (text === "-" || text === "데이터 없음") {
    renderStaticFlipText(element, text);
    fitFlipTextToContainer(element);
    return;
  }
  renderFlipText(element, previous === undefined ? seedFlipText(text) : previous, text);
  fitFlipTextToContainer(element);
  window.setTimeout(() => {
    renderStaticFlipText(element, text);
    fitFlipTextToContainer(element);
  }, 780);
}

function seedFlipText(text) {
  return Array.from(text).map((char) => /\\d/.test(char) ? "0" : char).join("");
}

function renderStaticFlipText(element, text) {
  element.replaceChildren();
  flipTextTokens(text).forEach((token) => {
    element.appendChild(/^\\d$/.test(token) ? staticFlipDigit(token) : staticFlipChar(token));
  });
}

function renderFlipText(element, previous, next) {
  element.replaceChildren();
  const length = Math.max(previous.length, next.length);
  const oldText = previous.padStart(length, " ");
  const nextText = next.padStart(length, " ");
  let flipped = false;
  for (let index = 0; index < nextText.length; index += 1) {
    const char = nextText[index] || " ";
    if (/[A-Za-z]/.test(char)) {
      let token = char;
      while (index + 1 < nextText.length && /[A-Za-z]/.test(nextText[index + 1])) {
        token += nextText[index + 1];
        index += 1;
      }
      element.appendChild(staticFlipChar(token));
      continue;
    }
    const oldChar = oldText[index] || " ";
    if (char !== oldChar && /\\d/.test(char)) {
      flipped = true;
      element.appendChild(flipDigit(oldChar, char));
      continue;
    }
    element.appendChild(/\\d/.test(char) ? staticFlipDigit(char) : staticFlipChar(char));
  }
  if (!flipped) renderStaticFlipText(element, next);
}

function flipTextTokens(text) {
  const tokens = [];
  const chars = Array.from(text);
  for (let index = 0; index < chars.length; index += 1) {
    const char = chars[index];
    if (/[A-Za-z]/.test(char)) {
      let token = char;
      while (index + 1 < chars.length && /[A-Za-z]/.test(chars[index + 1])) {
        token += chars[index + 1];
        index += 1;
      }
      tokens.push(token);
      continue;
    }
    tokens.push(char);
  }
  return tokens;
}

function fitFlipTextToContainer(element) {
  element.style.fontSize = "";
  const parent = element.parentElement;
  if (!parent) return;
  const availableWidth = Math.max(parent.clientWidth - 2, 1);
  const contentWidth = element.scrollWidth;
  if (contentWidth <= availableWidth) return;
  const currentFontSize = Number.parseFloat(window.getComputedStyle(element).fontSize) || 28;
  const nextFontSize = Math.max(Math.floor(currentFontSize * (availableWidth / contentWidth) * 0.96), 14);
  element.style.fontSize = `${nextFontSize}px`;
}

function flipDigit(oldChar, newChar) {
  const slot = document.createElement("span");
  slot.className = "flip-slot";
  const oldValue = document.createElement("span");
  oldValue.className = "flip-card-old";
  oldValue.textContent = /\\d/.test(oldChar) ? oldChar : newChar;
  const newValue = document.createElement("span");
  newValue.className = "flip-card-new";
  newValue.textContent = newChar;
  slot.append(oldValue, newValue);
  return slot;
}

function staticFlipDigit(char) {
  const slot = document.createElement("span");
  slot.className = "flip-slot";
  const value = document.createElement("span");
  value.className = "flip-card-static";
  value.textContent = char;
  slot.appendChild(value);
  return slot;
}

function staticFlipChar(char) {
  const item = document.createElement("span");
  item.className = /[A-Za-z]/.test(char) ? "flip-char flip-unit" : "flip-char";
  item.textContent = char === " " ? "\u00a0" : char;
  return item;
}

function setLinesWithTitle(elementId, lines) {
  const element = document.getElementById(elementId);
  element.replaceChildren();
  lines.forEach((line) => {
    const item = document.createElement("span");
    item.className = "sub-line";
    item.textContent = line;
    element.appendChild(item);
  });
  element.title = lines.join(" ");
}

function formatCycleStatus(value) {
  const labels = {
    filled: "체결 완료",
    blocked: "매매 차단",
    disabled: "비활성",
    waiting: "대기 중",
    position_checked: "포지션 점검",
    skipped: "건너뜀",
    stopped: "중지됨",
    started: "시작됨",
    running: "실행 중",
    synced: "동기화 완료",
    completed: "완료",
    ok: "정상",
    empty: "데이터 없음",
    failed: "실패",
    unknown: "상태 미확인",
    not_ready: "준비 안 됨",
    not_configured: "설정 안 됨",
    not_implemented: "미구현",
    demo_skipped: "데모 생략",
    recovered: "복구 완료",
    reconciled: "주문 동기화 완료",
    passed: "검증 통과",
    applied: "적용 완료",
    approved: "승인 완료",
    rejected: "반려됨",
    pending: "대기 중",
    proposed: "제안됨",
    reviewed: "검토 완료",
    demo_applied: "데모 적용 완료",
    live_approved: "실거래 승인 완료",
    needs_retry: "재시도 필요",
    rolled_back: "롤백 완료",
    linked: "연결 완료",
    trained: "학습 완료",
    refused: "거부됨",
    error: "오류",
    hold: "대기"
  };
  return formatKoreanLabel(value, labels, "상태 확인 필요");
}

function formatTradeAction(value) {
  const labels = {
    buy: "매수",
    sell: "매도",
    hold: "대기",
    wait: "대기",
    waiting: "대기 중",
    blocked: "차단",
    skipped: "건너뜀",
    filled: "체결",
    position_checked: "포지션 점검",
    stop_loss: "손절",
    take_profit: "익절"
  };
  return formatKoreanLabel(value, labels, "상태 확인 필요");
}

function formatKoreanLabel(value, labels, fallback = "확인 필요") {
  if (value === null || value === undefined || value === "") return "-";
  const key = String(value).trim();
  const normalized = key
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[-\\s]+/g, "_")
    .toLowerCase();
  return labels[key] || labels[normalized] || fallback;
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

function deriveExecutionWinRate(executions) {
  const history = executions && Array.isArray(executions.history) ? executions.history : [];
  const lots = [];
  let wins = 0;
  let closedSells = 0;

  history.forEach((execution) => {
    if (execution.status !== "filled") return;
    const quantity = Number(execution.filled_quantity || 0);
    const priceValue = Number(execution.filled_price || 0);
    const fee = Number(execution.fee || 0);
    if (quantity <= 0 || priceValue <= 0) return;

    if (execution.side === "buy") {
      lots.push({quantity, costPerUnit: ((priceValue * quantity) + fee) / quantity});
      return;
    }
    if (execution.side !== "sell") return;

    let remaining = quantity;
    let sellPnl = 0;
    while (remaining > 0 && lots.length > 0) {
      const lot = lots[0];
      const matched = Math.min(remaining, lot.quantity);
      const allocatedFee = fee * (matched / quantity);
      sellPnl += (priceValue * matched) - allocatedFee - (lot.costPerUnit * matched);
      lot.quantity = Number((lot.quantity - matched).toFixed(8));
      remaining = Number((remaining - matched).toFixed(8));
      if (lot.quantity <= 0) lots.shift();
    }
    if (remaining < quantity) {
      closedSells += 1;
      if (sellPnl > 0) wins += 1;
    }
  });

  return closedSells > 0 ? wins / closedSells : null;
}

function deriveWinRate(summary, promotion, executions) {
  const metrics = promotion && promotion.metrics ? promotion.metrics : null;
  if (metrics && metrics.win_rate !== undefined) return metrics.win_rate;
  return deriveExecutionWinRate(executions);
}

function deriveReadinessProgress(readiness) {
  const metrics = readiness && readiness.metrics ? readiness.metrics : null;
  const required = readiness && readiness.required ? readiness.required : null;
  if (!metrics || !required) {
    return {
      percent: 0,
      lines: ["모델 학습 준비도 데이터를 불러오지 못했습니다."]
    };
  }
  const keys = ["total_events", "signal_events", "fill_events", "exit_events", "blocked_cycles"];
  const ratios = keys.map((key) => {
    const requiredValue = Number(required[key] || 0);
    if (requiredValue <= 0) return 1;
    return Math.min(Number(metrics[key] || 0) / requiredValue, 1);
  });
  const percent = Math.floor((ratios.reduce((sum, value) => sum + value, 0) / ratios.length) * 100);
  return {
    percent,
    lines: [
      "모델 학습 준비도 기준. 체결 수는 학습 로그 누적값이며 최근 체결 표와 다를 수 있습니다.",
      `총 ${number(metrics.total_events || 0)}/${number(required.total_events || 0)}`,
      `매매판단신호 ${number(metrics.signal_events || 0)}/${number(required.signal_events || 0)}`,
      `누적 학습 로그 체결 ${number(metrics.fill_events || 0)}/${number(required.fill_events || 0)}`,
    ]
  };
}

function deriveInvestmentValue(summary, market) {
  const cash = Number(summary.cash_balance || 0);
  const coin = Number(summary.coin_balance || 0);
  const currentPrice = Number(market.current_price);
  if (Number.isNaN(currentPrice)) {
    return {
      total: cash,
      lines: [
        `현금 ${number(cash, 0)} KRW`,
        `보유 코인 ${number(coin, 8)}개, 현재가 데이터 없음`
      ]
    };
  }
  const coinValue = coin * currentPrice;
  return {
    total: cash + coinValue,
    lines: [
      `현금 ${number(cash, 0)} KRW`,
      `보유 ${number(coin, 8)}개 × 현재가 ${number(currentPrice, 4)} KRW = ${number(coinValue, 0)} KRW`
    ]
  };
}

function renderProfitRateChart(points, executions = [], market = {}) {
  const svg = document.getElementById("profitRateChart");
  const sub = document.getElementById("profitRateChartSub");
  const data = Array.isArray(points)
    ? points.filter((item) => Number.isFinite(Number(item.profit_rate)) && item.recorded_at)
    : [];
  const values = data.length ? data.map((item) => Number(item.profit_rate)) : [0];
  const minValue = Math.min(...values, -0.001);
  const maxValue = Math.max(...values, 0.001);
  const span = Math.max(maxValue - minValue, 0.001);
  const width = 672;
  const height = 128;
  const left = 24;
  const top = 24;
  const {startTime, endTime, timeSpan} = profitChartDomain(data, executions, market);
  const coords = data.map((item, index) => {
    const timestamp = new Date(item.recorded_at).getTime();
    const x = Number.isFinite(timestamp)
      ? left + ((timestamp - startTime) / timeSpan) * width
      : left + (data.length <= 1 ? width : (index / (data.length - 1)) * width);
    const y = top + height - ((Number(item.profit_rate) - minValue) / span) * height;
    return `${number(x, 1)},${number(y, 1)}`;
  }).join(" ");
  const zeroY = top + height - ((0 - minValue) / span) * height;
  const marketPriceLine = buildMarketPriceLine({
    market,
    startTime,
    endTime,
    timeSpan,
    left,
    top,
    width,
    height
  });
  const markers = buildProfitTradeMarkers({
    executions,
    data,
    startTime,
    endTime,
    timeSpan,
    minValue,
    span,
    left,
    top,
    width,
    height
  });
  const profitLine = coords ? `<polyline points="${coords}"></polyline>` : "";
  svg.innerHTML = `<line class="axis" x1="24" y1="${number(zeroY, 1)}" x2="696" y2="${number(zeroY, 1)}"></line>${profitLine}${marketPriceLine}${markers}`;
  const latest = data.length ? values[values.length - 1] : null;
  const target = 0.005;
  const priceSummary = marketPriceSummary(market, startTime, endTime);
  sub.textContent = data.length
    ? `최근 수익률 ${percent(latest)} / 일 목표 ${percent(target)}${priceSummary ? ` / 가격 ${priceSummary}` : ""}`
    : `최근 24시간 수익률 데이터가 아직 없습니다.${priceSummary ? ` / 가격 ${priceSummary}` : ""}`;
}

function profitChartDomain(data, executions, market) {
  const times = [];
  data.forEach((item) => {
    const timestamp = new Date(item.recorded_at).getTime();
    if (Number.isFinite(timestamp)) times.push(timestamp);
  });
  const history = Array.isArray(market.history) ? market.history : [];
  history.forEach((item) => {
    const timestamp = new Date(item.recorded_at).getTime();
    if (Number.isFinite(timestamp)) times.push(timestamp);
  });
  const currentTimestamp = new Date(market.recorded_at).getTime();
  if (Number.isFinite(currentTimestamp)) times.push(currentTimestamp);
  const filled = Array.isArray(executions) ? executions : [];
  filled.forEach((item) => {
    const timestamp = new Date(item.recorded_at).getTime();
    if (Number.isFinite(timestamp)) times.push(timestamp);
  });
  const endTime = Math.max(...times, Date.now());
  const timeSpan = 24 * 60 * 60 * 1000;
  return {startTime: endTime - timeSpan, endTime, timeSpan};
}

function buildMarketPriceLine({market, startTime, endTime, timeSpan, left, top, width, height}) {
  const points = marketPricePoints(market, startTime, endTime);
  if (!points.length) return "";
  points.sort((leftItem, rightItem) => leftItem.timestamp - rightItem.timestamp);
  const displayDomain = marketPriceDisplayDomain(points, startTime, endTime, timeSpan);
  const prices = points.map((item) => item.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const flatPrice = maxPrice === minPrice;
  const priceSpan = Math.max(maxPrice - minPrice, Math.max(maxPrice * 0.001, 1));
  const coords = points.map((item) => {
    const x = left + ((item.timestamp - displayDomain.startTime) / displayDomain.timeSpan) * width;
    const y = flatPrice ? top + (height / 2) : top + height - ((item.price - minPrice) / priceSpan) * height;
    return `${number(x, 1)},${number(y, 1)}`;
  }).join(" ");
  const labels = `<text class="price-axis-label" x="${left + width}" y="${top + 12}">${number(maxPrice, 0)}</text><text class="price-axis-label" x="${left + width}" y="${top + height - 4}">${number(minPrice, 0)}</text>`;
  if (points.length < 2) {
    return `<circle class="market-price-point" cx="${number(left + width, 1)}" cy="${number(top + height / 2, 1)}" r="4"><title>업비트 현재가 ${price(maxPrice)}</title></circle>${labels}`;
  }
  return `<polyline class="market-price-line" points="${coords}"><title>업비트 실제 가격 흐름 ${price(minPrice)} ~ ${price(maxPrice)}</title></polyline>${labels}`;
}

function marketPriceDisplayDomain(points, startTime, endTime, timeSpan) {
  if (points.length < 2) return {startTime, endTime, timeSpan};
  const firstTime = points[0].timestamp;
  const lastTime = points[points.length - 1].timestamp;
  const observedSpan = Math.max(lastTime - firstTime, 1);
  if (observedSpan < timeSpan * 0.5) {
    return {startTime: firstTime, endTime: lastTime, timeSpan: observedSpan};
  }
  return {startTime, endTime, timeSpan};
}

function marketPricePoints(market, startTime, endTime) {
  const history = Array.isArray(market.history) ? market.history : [];
  const points = history
    .map((item) => ({
      recorded_at: item.recorded_at,
      timestamp: new Date(item.recorded_at).getTime(),
      price: Number(item.price)
    }))
    .filter((item) => Number.isFinite(item.timestamp) && Number.isFinite(item.price) && item.price > 0 && item.timestamp >= startTime && item.timestamp <= endTime);
  const currentTimestamp = new Date(market.recorded_at).getTime();
  const currentPrice = Number(market.current_price);
  if (Number.isFinite(currentTimestamp) && Number.isFinite(currentPrice) && currentPrice > 0 && currentTimestamp >= startTime && currentTimestamp <= endTime) {
    const last = points[points.length - 1];
    if (!last || last.timestamp !== currentTimestamp || last.price !== currentPrice) {
      points.push({recorded_at: market.recorded_at, timestamp: currentTimestamp, price: currentPrice});
    }
  }
  return points;
}

function marketPriceSummary(market, startTime, endTime) {
  const prices = marketPricePoints(market, startTime, endTime).map((item) => item.price);
  if (!prices.length) return "";
  return `${price(Math.min(...prices))}~${price(Math.max(...prices))}`;
}

function buildProfitTradeMarkers({executions, data, startTime, endTime, timeSpan, minValue, span, left, top, width, height}) {
  const history = Array.isArray(executions) ? executions : [];
  const filled = history.filter((item) => item.status === "filled" && item.recorded_at && ["buy", "sell"].includes(item.side));
  return filled.map((execution) => {
    const timestamp = new Date(execution.recorded_at).getTime();
    if (!Number.isFinite(timestamp) || timestamp < startTime || timestamp > endTime) return "";
    const nearest = nearestProfitPoint(data, timestamp);
    const profitRate = nearest ? Number(nearest.profit_rate) : 0;
    const x = left + ((timestamp - startTime) / timeSpan) * width;
    const y = top + height - ((profitRate - minValue) / span) * height;
    const markerClass = execution.is_stop_loss ? "stop-loss" : execution.side;
    const radius = execution.side === "buy" ? 5.5 : 5;
    const title = escapeHtml(profitMarkerTitle(execution, profitRate));
    return `<circle class="trade-marker ${markerClass}" cx="${number(x, 1)}" cy="${number(y, 1)}" r="${radius}"><title>${title}</title></circle>`;
  }).join("");
}

function nearestProfitPoint(data, timestamp) {
  let nearest = null;
  let nearestDistance = Infinity;
  data.forEach((item) => {
    const pointTime = new Date(item.recorded_at).getTime();
    if (!Number.isFinite(pointTime)) return;
    const distance = Math.abs(pointTime - timestamp);
    if (distance < nearestDistance) {
      nearest = item;
      nearestDistance = distance;
    }
  });
  return nearest;
}

function profitMarkerTitle(execution, profitRate) {
  const side = execution.side === "buy" ? "매수" : execution.is_stop_loss ? "손절 매도" : "매도";
  const reason = execution.reason_code ? formatBlockedReason(execution.reason_code) : defaultExecutionReason(execution);
  const strength = execution.signal_level
    ? `${formatSignalLevel(execution.signal_level)}${execution.signal_score !== null && execution.signal_score !== undefined ? ` / 점수 ${number(execution.signal_score, 3)}` : ""}`
    : "강도 데이터 없음";
  return [
    `${side} ${formatDateTime(execution.recorded_at)}`,
    `이유: ${reason}`,
    `강도: ${strength}`,
    `체결가: ${price(execution.filled_price)}`,
    `수량: ${number(execution.filled_quantity, 8)}`,
    `당시 수익률: ${percent(profitRate)}`
  ].join("\\n");
}

function defaultExecutionReason(execution) {
  if (execution.side === "buy") return "진입 신호 충족";
  if (execution.is_stop_loss) return "손절 조건 충족";
  return "청산 조건 충족";
}

function formatSignalLevel(value) {
  const labels = {
    weak: "약함",
    medium: "보통",
    strong: "강함",
    very_strong: "매우 강함"
  };
  return labels[value] || value || "-";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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
  document.getElementById("ruleWindow").textContent = source.analysis_window_days ? `${source.analysis_window_days}일` : "-";
  document.getElementById("ruleTrades").textContent = number(source.trade_count || 0);
  document.getElementById("ruleStopLosses").textContent = number(source.stop_loss_count || 0);
  document.getElementById("ruleApproval").textContent = source.approval_required ? "필요" : "불필요";
  const causes = (source.major_loss_causes || []).map((item) => `${item.reason} ${number(item.count)}건`).join(", ") || "데이터 부족";
  const changes = (proposal.codex_suggested_changes || []).map((item) => `${item.parameter}: ${item.proposed_value}`).join(", ") || "변경안 없음";
  const replay = proposal.replay_result ? JSON.stringify(proposal.replay_result) : "replay 필요";
  const reasons = (proposal.rejection_reasons || []).join(", ") || "없음";
  const externalContext = formatRuleExternalContext(source.external_context_summary || {});
  const historyWarnings = formatRuleHistoryWarnings(proposal.history_warnings || []);
  document.getElementById("ruleReviewTable").innerHTML = [
    row("대상 코인", source.trade_coin || "-"),
    row("룰 로그 경로", source.learning_log_dir || "-"),
    row("외부 컨텍스트", externalContext),
    row("히스토리 경고", historyWarnings),
    row("주요 손실 원인", causes),
    row("Codex 제안 변경 항목", changes),
    row("replay 결과", replay),
    row("차단/승인 사유", reasons),
    row("상태", proposal.status || "reviewed")
  ].join("");
}

function formatRuleExternalContext(summary) {
  const onchain = Object.entries(summary.onchain_state_counts || {}).map(([key, value]) => `${formatContextState(key)} ${number(value)}건`).join(", ") || "없음";
  const etf = Object.entries(summary.etf_state_counts || {}).map(([key, value]) => `${formatContextState(key)} ${number(value)}건`).join(", ") || "없음";
  const flow = `ETF 순흐름 ${signedNumber(summary.etf_flow_usd_total || 0, 0)} USD`;
  return `표본 ${number(summary.sample_count || 0)}건 / 온체인 ${onchain} / ETF ${etf} / 평균 가중치 ${number(summary.avg_learning_weight || 1, 3)} / ${flow}`;
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
    : '<tr><td class="empty">룰 변경 히스토리가 없습니다.</td></tr>';
}

async function refreshRuleHistory() {
  renderRuleHistory(await fetchJson("/api/v1/rules/history"));
}

async function runCodexRuleAutomation(initialMessage = "학습 로그를 읽고 변경안을 생성하는 자동 파이프라인을 실행합니다.") {
  openRuleAutomationModal();
  appendRuleAutomationStep("Codex CLI 룰 개선 하네스 시작", "running", initialMessage);
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

async function maybeRunAutoRuleImprove(progress) {
  if (progress < 100 || autoRuleImproveInFlight) return;
  if (sessionStorage.getItem(AUTO_RULE_READY_KEY) === "done") return;
  autoRuleImproveInFlight = true;
  sessionStorage.setItem(AUTO_RULE_READY_KEY, "done");
  try {
    await runCodexRuleAutomation("학습완료율 100% 도달로 학습 데이터, 온체인 데이터, ETF 상태를 함께 분석합니다.");
  } finally {
    autoRuleImproveInFlight = false;
  }
}

async function runRuleReview() {
  renderRulePipeline(await postJson("/api/v1/rules/review"));
}

async function createRuleProposal() {
  renderRulePipeline(await postJson("/api/v1/rules/proposals", {review_id: latestRuleReviewId}));
}

async function applyRuleProposalToDemo() {
  if (!latestRuleProposalId) {
    await createRuleProposal();
  }
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/apply-demo`));
}

async function verifyRuleProposalReplay() {
  if (!latestRuleProposalId) {
    await createRuleProposal();
  }
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/replay`, {fixture_path: "fixtures/replay_ticks.json"}));
}

async function approveRuleProposalForLive() {
  if (!latestRuleProposalId) {
    await createRuleProposal();
  }
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/approve-live`, {approved_by: ""}));
}

async function linkRuleProposalCommitHash() {
  if (!latestRuleProposalId) {
    await createRuleProposal();
  }
  const commitHash = window.prompt("연결할 Git 커밋 해시를 입력하세요.", "");
  if (!commitHash) return;
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/commit-hash`, {commit_hash: commitHash}));
  await refreshRuleHistory();
}

async function appendRuleHistoryCorrection() {
  if (!latestRuleProposalId) {
    await createRuleProposal();
  }
  const reason = window.prompt("히스토리 보정 사유를 입력하세요.", "");
  if (!reason) return;
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/history-corrections`, {reason, corrected_fields: {}, corrected_by: "operator"}));
  await refreshRuleHistory();
}

async function rollbackRuleProposal() {
  if (!latestRuleProposalId) {
    await createRuleProposal();
  }
  const reason = window.prompt("룰 변경 롤백 사유를 입력하세요.", "");
  if (!reason) return;
  renderRulePipeline(await postJson(`/api/v1/rules/proposals/${latestRuleProposalId}/rollback`, {reason, target: "demo", rolled_back_by: "operator"}));
  await refreshRuleHistory();
}

async function refreshDashboard() {
  if (dashboardRefreshInFlight) return;
  dashboardRefreshInFlight = true;
  document.getElementById("statusLine").textContent = "데이터를 불러오는 중...";
  try {
    const now = Date.now();
    const shouldRefreshSlowData = now - lastSlowDashboardRefreshAt >= DASHBOARD_SLOW_REFRESH_INTERVAL_MS;
    const slowRefreshPromise = shouldRefreshSlowData ? refreshSlowDashboardData(now) : Promise.resolve();
    const [health, summary, marketResponse, learningResponse, learningHealthResponse, readinessResponse, executions, promotionResponse, tradingStatus] = await Promise.all([
      fetchJson("/health"),
      fetchJson("/dashboard/summary"),
      fetchJson("/dashboard/market?history_limit=288"),
      fetchJson("/dashboard/learning"),
      fetchJson("/dashboard/learning/health"),
      fetchJson("/learning/model-readiness"),
      fetchJson("/dashboard/executions?limit=1000"),
      fetchJson("/dashboard/promotion"),
      fetchJson("/settings/trading/status")
    ]);
    await slowRefreshPromise;
    renderLatestRuleProposal(cachedRuleProposalResponse);
    renderRuleHistory(cachedRuleHistoryResponse);
    renderExternalContext(cachedExternalContextResponse.context || {}, marketResponse.summary || {});
    renderNoTradeDiagnostics(cachedDiagnosticsResponse.diagnostics || {});
    renderDashboard({
      health,
      summary,
      learning: learningResponse.learning || {},
      learningLogDir: learningResponse.learning_log_dir || "",
      learningHealth: learningHealthResponse.health || {},
      readiness: readinessResponse.readiness || {},
      executions,
      promotion: promotionResponse.promotion,
      market: marketResponse.summary || {market: marketResponse.market},
      tradingStatus
    });
  } catch (error) {
    document.getElementById("statusLine").textContent = `대시보드 데이터를 불러오지 못했다: ${error.message}`;
  } finally {
    dashboardRefreshInFlight = false;
  }
}

async function refreshSlowDashboardData(startedAt) {
  if (dashboardSlowRefreshInFlight) return;
  dashboardSlowRefreshInFlight = true;
  try {
    const [ruleProposalResponse, ruleHistoryResponse, externalContextResponse, diagnosticsResponse] = await Promise.all([
      fetchJson("/api/v1/rules/proposals"),
      fetchJson("/api/v1/rules/history"),
      fetchJson("/dashboard/external-context"),
      fetchJson("/learning/diagnostics")
    ]);
    cachedRuleProposalResponse = ruleProposalResponse;
    cachedRuleHistoryResponse = ruleHistoryResponse;
    cachedExternalContextResponse = externalContextResponse;
    cachedDiagnosticsResponse = diagnosticsResponse;
  } catch (error) {
    console.warn(`느린 대시보드 데이터 갱신 실패: ${error.message}`);
  } finally {
    lastSlowDashboardRefreshAt = startedAt;
    dashboardSlowRefreshInFlight = false;
  }
}

function renderExternalContext(context, market) {
  const onchain = context.onchain || {};
  const etf = context.etf || {};
  const marketData = context.market_data || {};
  const usdChange = marketData.usd_change_pct_24h;
  const upbitChangeRate = market.signed_change_rate ?? market.recent_change_pct;
  const krwPriceLine = market.current_price === undefined
    ? "현재가 데이터 없음"
    : `<span class="krw-price">${price(market.current_price)} <span class="${changeClass(upbitChangeRate)}">(${percent(upbitChangeRate)})</span></span>`;
  document.getElementById("contextUsdPrice").innerHTML = `${usd(marketData.usd_price)}<br><span class="${changeClass(usdChange)}">24시간 ${percent(usdChange)}</span><br>${krwPriceLine}`;
  document.getElementById("onchainState").textContent = [
    `${formatContextState(onchain.state)} / 주소변화 ${percent(onchain.active_addresses_change_pct || 0)}`,
    `거래소 순유입·순유출: ${formatContextState(onchain.exchange_netflow_state)}`,
    `고래 지갑 움직임: ${formatContextState(onchain.whale_activity_state)}${formatContextBasis(onchain.whale_activity_basis)}`,
    `MVRV/SOPR: ${formatContextState(onchain.valuation_state)}${formatContextBasis(onchain.valuation_basis)}`
  ].join("\\n");
  const tradeCoin = context.trade_coin || "";
  const holdingChange = Number(etf.holding_change_coin || 0);
  const etfFlowLines = formatEtfFlowLines(etf);
  const etfLines = [
    `${formatContextState(etf.state)}`,
    ...etfFlowLines,
    formatEtfMetricLine("보유수량 변화", holdingChange, `${tradeCoin}`, holdingChange, 0),
    etf.total_aum_usd ? formatEtfMetricLine("총 AUM", etf.total_aum_usd, "USD", etf.total_aum_usd_change, 0, false) : "",
    etf.total_holding_coin ? formatEtfMetricLine("총 보유", etf.total_holding_coin, tradeCoin, etf.total_holding_coin_change, 0, false) : ""
  ].filter(Boolean);
  document.getElementById("etfState").innerHTML = etfLines.join("<br>");
  document.getElementById("etfState").title = etfLines.map((line) => line.replace(/<[^>]*>/g, "")).join("\\n");
  document.getElementById("contextWeight").textContent = number(context.learning_weight || 1, 3);
  document.getElementById("contextStatus").textContent = formatExternalContextStatus(onchain, etf);
  document.getElementById("contextRecordedAt").textContent = context.recorded_at ? new Date(context.recorded_at).toLocaleString("ko-KR") : "-";
}

function formatEtfFlowLine(etf) {
  const flow = Number(etf.flow_usd || 0);
  if (flow > 0) return `순유입 ${number(flow, 0)} USD`;
  if (flow < 0) return `순유출 ${number(Math.abs(flow), 0)} USD`;
  const inflow = Number(etf.inflow_usd || 0);
  const outflow = Number(etf.outflow_usd || 0);
  if (inflow > 0) return `순유입 ${number(inflow, 0)} USD`;
  if (outflow > 0) return `순유출 ${number(outflow, 0)} USD`;
  return etf.state === "unknown" ? "순흐름 데이터 없음" : "순흐름 0 USD";
}

function formatEtfFlowLines(etf) {
  const inflow = Number(etf.inflow_usd || 0);
  const outflow = Number(etf.outflow_usd || 0);
  const lines = [];
  if (inflow > 0) lines.push(formatEtfMetricLine("순유입", inflow, "USD", etf.inflow_usd_change, 0));
  if (outflow > 0) lines.push(formatEtfMetricLine("순유출", outflow, "USD", etf.outflow_usd_change, 0));
  if (lines.length) return lines;
  return [formatEtfFlowLine(etf)];
}

function formatEtfMetricLine(label, value, unit, changeValue, digits = 0, showValueSign = true) {
  const numericValue = Number(value || 0);
  const numericChange = Number(changeValue || 0);
  const unitText = unit ? ` ${unit}` : "";
  const formattedValue = showValueSign ? signedNumber(numericValue, digits) : number(numericValue, digits);
  return `${label} <span class="${changeClass(numericChange)}">${formattedValue}${unitText}</span>`;
}

function formatExternalContextStatus(onchain, etf) {
  const errors = [];
  if (onchain.fetch_error) errors.push("온체인 오류");
  if (etf.fetch_error) errors.push("ETF 오류");
  if (errors.length) return errors.join(" / ");
  if (onchain.state === "disabled" || etf.state === "disabled") return "비활성";
  return "정상";
}

function formatContextState(value) {
  const labels = {
    bullish: "강세",
    bearish: "약세",
    neutral: "중립",
    inflow: "자금 유입",
    outflow: "자금 유출",
    disabled: "비활성",
    not_applicable: "해당 없음",
    unknown: "데이터 없음"
  };
  return labels[value] || value || "-";
}

function formatContextBasis(value) {
  const labels = {
    activity_volume_proxy: " (활동·거래량 대체)",
    price_change_proxy: " (가격변화 대체)"
  };
  return labels[value] || "";
}

function formatDiagnosisState(value) {
  const labels = {
    NO_LEARNING_LOG: "학습 로그 없음",
    AUTO_TRADING_NOT_RUNNING: "자동매매 미실행",
    TRADES_FOUND: "체결 이벤트 확인",
    TRADE_BLOCKED_BY_RULES: "매매 규칙 차단",
    INSUFFICIENT_ACTIVITY: "활동 데이터 부족",
    NO_TRADE_DATA: "거래 데이터 없음",
    WAITING_FOR_SIGNAL: "신호 대기 중",
    ACTIVE_TRADING: "거래 진행 중"
  };
  return labels[value] || value || "-";
}

function formatMitigationAction(value) {
  const labels = {
    RELAX_ENTRY_RULES_FOR_DEMO: "데모 진입 규칙 완화 검토",
    COLLECT_MORE_DATA: "데이터 추가 수집",
    KEEP_CURRENT_RULES: "현재 룰 유지",
    REVIEW_RISK_RULES: "리스크 규칙 점검",
    NONE: "조치 불필요",
    MONITOR: "추가 관찰"
  };
  return labels[value] || value || "-";
}

function formatBlockedReason(value) {
  const labels = {
    AUTO_TRADING_DISABLED_OR_NOT_READY: "자동매매 비활성 또는 준비 안 됨",
    MARKET_HISTORY_WARMING_UP: "시세 이력 준비 중",
    PRICE_PROVIDER_ERROR: "현재가 조회 오류",
    PRICE_SNAPSHOT_UNAVAILABLE: "현재가 데이터 없음",
    INVALID_PRICE_SNAPSHOT: "현재가 데이터 오류",
    POSITION_HELD: "포지션 보유 중",
    POSITION_EXIT_TRIGGERED: "포지션 청산 실행",
    LIVE_ORDER_PENDING: "실거래 주문 처리 대기",
    LIVE_ORDER_STATUS_UNAVAILABLE: "실거래 주문 상태 확인 불가",
    ORDER_STATUS_UNAVAILABLE: "주문 상태 확인 불가",
    ORDER_STATUS_ERROR: "주문 상태 확인 오류",
    DEMO_ASSET_WITHOUT_ACTIVE_POSITION: "데모 보유자산과 포지션 불일치",
    LIVE_ASSET_WITHOUT_ACTIVE_POSITION: "실거래 보유자산과 포지션 불일치",
    REENTRY_BLOCK_AFTER_SELL: "매도 후 재진입 대기",
    REENTRY_BLOCK_ACTIVE: "재진입 제한 중",
    MARKET_STATE_BEAR_ENTRY_BLOCK: "하락장 약한 진입 차단",
    AUTO_MIN_SIGNAL_LEVEL: "최소 신호 점수 미달",
    DEMO_CASH_LIMIT: "데모 현금 부족",
    SIGNAL_BLOCKED: "신호 차단",
    REGIME_BLOCKED: "장세 조건 차단",
    SPREAD_OR_SLIPPAGE_LIMIT: "스프레드/슬리피지 한도 초과",
    INVALID_CURRENT_PRICE: "현재가 오류",
    FEE_ADJUSTED_EDGE_LIMIT: "수수료 반영 기대수익 부족",
    MIN_CASH_RESERVE: "최소 현금 보유 기준 미달",
    STOP_LOSS_RISK_LIMIT: "손절 리스크 한도 초과",
    MIN_ORDER_AMOUNT: "최소 주문 금액 미달",
    MIN_ORDER_AMOUNT_SELL: "최소 매도 주문 금액 미달",
    STOP_LOSS_PRICE_HIT: "손절가 도달",
    TAKE_PROFIT_TARGET_HIT: "익절 목표 도달",
    POST_ENTRY_TIMEOUT: "진입 후 보유 시간 초과",
    LOW_LIQUIDITY_BLOCKED: "유동성 부족",
    MICRO_MOMENTUM_REVERSAL_BLOCKED: "초단기 모멘텀 반전",
    EXCESSIVE_SHORT_VOLATILITY_BLOCKED: "단기 변동성 과다",
    TECHNICAL_OVERBOUGHT_BLOCKED: "보조지표 과매수 차단",
    EXTERNAL_CONTEXT_BULLISH_BOOST: "외부 컨텍스트 상승 보정",
    EXTERNAL_CONTEXT_RISK_OFF: "외부 컨텍스트 위험 회피",
    TARGET_DAILY_RETURN_0_5PCT: "일 목표 수익률 기준 반영"
  };
  return formatKoreanLabel(value, labels, "기타 차단 사유");
}

function renderNoTradeDiagnostics(diagnostics) {
  const diagnosis = diagnostics.diagnosis || {};
  const mitigation = diagnostics.mitigation || {};
  document.getElementById("noTradeDiagnosis").textContent = `${formatDiagnosisState(diagnosis.state)} / ${diagnosis.message || ""}`.trim();
  document.getElementById("noTradeMitigation").textContent = `${formatMitigationAction(mitigation.action)} / ${mitigation.message || ""}`.trim();
  document.getElementById("noTradeBlockedReasons").textContent = formatBlockedReasons(diagnostics);
  document.getElementById("noTradeExternalContext").textContent = formatDiagnosticsExternalContext(diagnostics.external_context_summary || {});
  document.getElementById("noTradeEventsScanned").textContent = number(diagnostics.events_scanned || 0);
}

function formatDiagnosticsExternalContext(summary) {
  const onchain = Object.entries(summary.onchain_state_counts || {}).map(([key, value]) => `${formatContextState(key)} ${number(value)}건`).join(", ") || "없음";
  const etf = Object.entries(summary.etf_state_counts || {}).map(([key, value]) => `${formatContextState(key)} ${number(value)}건`).join(", ") || "없음";
  return `표본 ${number(summary.sample_count || 0)}건\n온체인 ${onchain}\nETF ${etf}\n평균 가중치 ${number(summary.avg_learning_weight || 1, 3)}`;
}

function formatBlockedReasons(diagnostics) {
  const pairs = [];
  const autoReasons = diagnostics.auto_cycle_blocked_reasons || {};
  const sizingReasons = diagnostics.sizing_blocked_reasons || {};
  Object.entries(autoReasons).forEach(([key, value]) => pairs.push(`${formatBlockedReason(key)} ${number(value)}건`));
  Object.entries(sizingReasons).forEach(([key, value]) => pairs.push(`사이징: ${formatBlockedReason(key)} ${number(value)}건`));
  return pairs.length ? pairs.join(", ") : "차단 기록 없음";
}

function renderDashboard(data) {
  const {health, summary, market, learning, learningLogDir, learningHealth, readiness, executions, promotion, tradingStatus} = data;
  const totalEvents = learning.total_events || learningHealth.total_events || 0;
  const readinessProgress = deriveReadinessProgress(readiness);
  const progress = readinessProgress.percent;
  const winRate = deriveWinRate(summary, promotion, executions);
  const readyBadge = health.trading_ready ? '<span class="badge ok">거래 준비됨</span>' : '<span class="badge warn">점검 필요</span>';
  const learningBadge = summary.learning_enabled ? '<span class="badge ok">학습 기록 중</span>' : '<span class="badge warn">학습 비활성</span>';
  maybeRunAutoRuleImprove(progress);

  document.getElementById("statusLine").innerHTML = `${readyBadge} ${learningBadge}`;
  renderTradingRuntime(tradingStatus);
  renderExchangeSimulation({market, tradingStatus, winRate});
  document.getElementById("modeMetric").textContent = String(summary.trading_mode || health.mode).toUpperCase();
  const profileLabel = summary.trading_profile_label || summary.trading_profile || "단타";
  const modeDescription = summary.trading_mode === "live" ? "실제 주문 모드입니다. API 키와 리스크 상태를 계속 확인하세요." : "데모 주문 모드입니다. API 키 없이 학습과 검증을 진행합니다.";
  setLinesWithTitle("modeSub", [modeDescription, `투자성향: ${profileLabel}`]);
  const trendStreak = deriveTrendStreak(market);
  const marketLabel = displayMarket(market.market);
  const upbitChangeRate = market.signed_change_rate ?? market.recent_change_pct;
  const priceText = market.current_price === undefined ? "데이터 없음" : `${price(market.current_price)} (${percent(upbitChangeRate)})`;
  const changeText = market.current_price === undefined ? "-" : `(${percent(upbitChangeRate)})`;
  const rangeText = market.market_state === "box" && market.box_range_low !== null && market.box_range_high !== null
    ? ` ${price(market.box_range_low)}~${price(market.box_range_high)}`
    : "";
  const trendText = market.current_price === undefined ? "거래량 데이터가 아직 없습니다." : `${market.market_state_label || "박스권"}${rangeText}`;
  setTextWithTitle("priceMarket", marketLabel);
  setFlipTextWithTitle("priceMetric", market.current_price === undefined ? "데이터 없음" : price(market.current_price));
  setHtmlWithTitle("priceChange", `<span class="${changeClass(upbitChangeRate)}">${changeText}</span>`, priceText);
  setHtmlWithTitle(
    "priceSub",
    market.current_price === undefined
      ? trendText
      : `<span class="badge ${trendBadgeClass(trendStreak.trend)}">${market.market_state_label || "박스권"}</span>${rangeText}`,
    trendText
  );
  const investment = deriveInvestmentValue(summary, market);
  setFlipTextWithTitle("capitalMetric", `${number(investment.total, 0)} KRW`);
  setLinesWithTitle("capitalSub", investment.lines);
  document.getElementById("learningProgressMetric").textContent = `${progress}%`;
  document.getElementById("learningProgressBar").style.width = `${progress}%`;
  setLinesWithTitle("learningProgressSub", readinessProgress.lines);
  document.getElementById("winRateMetric").textContent = percent(winRate);
  document.getElementById("winRateSub").textContent = winRate === null ? "완료된 거래 손익 기록이 쌓이면 표시됩니다." : "현재 기록 기준 수익 거래 비율입니다.";
  setFlipTextWithTitle("pnlMetric", `${number(summary.realized_pnl, 2)} KRW`);
  document.getElementById("pnlSub").textContent = `미실현 손익 ${number(summary.unrealized_pnl, 2)} KRW, 매수 ${summary.buy_count || 0}건, 매도 ${summary.sell_count || 0}건`;
  renderProfitRateChart(summary.profit_rate_series_24h || [], executions.history || [], market);
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
    row("최근 이벤트", number(totalEvents)),
    row("모델학습 총 이벤트", readiness.metrics ? `${number(readiness.metrics.total_events || 0)} / ${number(readiness.required.total_events || 0)}` : "데이터 없음"),
    row("누적 학습 로그 체결", readiness.metrics ? `${number(readiness.metrics.fill_events || 0)} / ${number(readiness.required.fill_events || 0)}` : "데이터 없음"),
    row("투자성향", summary.trading_profile_label || summary.trading_profile || "단타"),
    row("최근 이벤트명", learning.last_event_name || "없음"),
    row("최근 기록 시각", learning.last_recorded_at || learningHealth.last_recorded_at || "없음"),
    row("신호/체결/포지션", `${number(categories.signals || 0)} / ${number(categories.fills || 0)} / ${number(categories.positions || 0)}`),
    row("학습 로그 경로", learningLogDir || "없음"),
    row("상태", learning.state_message || learningHealth.state_message || "학습 데이터가 아직 없습니다.")
  ].join("");

  const history = executions.history || [];
  document.getElementById("executionsTable").innerHTML = history.length
    ? history.slice(-8).reverse().map((item) => `
        <tr><td>${formatDateTime(item.recorded_at)}</td><td>${item.side_label || item.side}</td><td>${item.status_label || item.status}</td><td>${number(item.filled_price, 4)}</td><td>${number(item.filled_quantity, 6)}</td></tr>
      `).join("")
    : '<tr><td colspan="5" class="empty">현재 서버 실행 중 체결 기록이 없습니다.</td></tr>';

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
setInterval(refreshDashboard, DASHBOARD_REFRESH_INTERVAL_MS);
</script>
</body>
</html>
"""
