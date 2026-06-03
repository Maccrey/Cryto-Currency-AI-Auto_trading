from app.api.routes.dashboard import DASHBOARD_HTML
from app.api.routes.settings import SETTINGS_HTML


def test_dashboard_price_card_labels_market_state_and_box_range() -> None:
    assert "market.market_state === \"box\"" in DASHBOARD_HTML
    assert "${market.market_state_label || \"박스권\"}" in DASHBOARD_HTML
    assert "${price(market.box_range_low)}~${price(market.box_range_high)}" in DASHBOARD_HTML


def test_dashboard_includes_24h_profit_rate_chart() -> None:
    assert 'id="profitRateChart"' in DASHBOARD_HTML
    assert "renderProfitRateChart" in DASHBOARD_HTML
    assert "buildProfitTradeMarkers" in DASHBOARD_HTML
    assert "buildMarketPriceLine" in DASHBOARD_HTML
    assert "profitChartDomain" in DASHBOARD_HTML
    assert "marketPricePoints" in DASHBOARD_HTML
    assert "marketPriceDisplayDomain" in DASHBOARD_HTML
    assert "marketPriceSummary" in DASHBOARD_HTML
    assert "profitMarkerTitle" in DASHBOARD_HTML
    assert "formatSignalLevel" in DASHBOARD_HTML
    assert ".profit-chart .market-price-line" in DASHBOARD_HTML
    assert ".profit-chart .market-price-point" in DASHBOARD_HTML
    assert ".profit-chart .price-axis-label" in DASHBOARD_HTML
    assert ".profit-chart .price-axis-label { fill: #facc15;" in DASHBOARD_HTML
    assert ".profit-chart .trade-marker.stop-loss { fill: #facc15; }" in DASHBOARD_HTML
    assert "최근 24시간 수익률 데이터가 아직 없습니다.${priceSummary ? ` / 가격 ${priceSummary}` : \"\"}" in DASHBOARD_HTML
    assert "${profitLine}${marketPriceLine}${markers}" in DASHBOARD_HTML
    assert "observedSpan < timeSpan * 0.5" in DASHBOARD_HTML
    assert 'class="trade-marker ${markerClass}"' in DASHBOARD_HTML
    assert 'fetchJson("/dashboard/market?history_limit=288")' in DASHBOARD_HTML
    assert 'renderProfitRateChart(summary.profit_rate_series_24h || [], executions.history || [], market);' in DASHBOARD_HTML
    assert "`${market.market || marketLabel} <span" not in DASHBOARD_HTML


def test_dashboard_includes_exchange_simulation_and_demo_rule_variants() -> None:
    assert "코인거래소 시뮬레이션" in DASHBOARD_HTML
    assert "AI-A" in DASHBOARD_HTML
    assert "AI-R" in DASHBOARD_HTML
    assert "AI-X" in DASHBOARD_HTML
    assert "데모 룰 A/B/C 내부 테스트" in DASHBOARD_HTML
    assert 'id="ruleVariantBoard"' in DASHBOARD_HTML
    assert "function renderExchangeSimulation" in DASHBOARD_HTML
    assert "tradingStatus.last_cycle" in DASHBOARD_HTML
    assert "shadow.leader_key" in DASHBOARD_HTML
    assert "같은 실시간 데이터를 기준으로 A/B/C 가상 포트폴리오를 동시에 테스트" in DASHBOARD_HTML
    assert "formatKoreanLabel" in DASHBOARD_HTML
    assert "formatTradeAction(item.last_action)" in DASHBOARD_HTML
    assert 'AUTO_TRADING_DISABLED_OR_NOT_READY: "자동매매 비활성 또는 준비 안 됨"' in DASHBOARD_HTML
    assert 'return formatKoreanLabel(value, labels, "상태 확인 필요");' in DASHBOARD_HTML
    assert 'return formatKoreanLabel(value, labels, "기타 차단 사유");' in DASHBOARD_HTML


def test_dashboard_price_card_renders_change_on_separate_small_line() -> None:
    assert 'id="priceChange" class="price-change-line"' in DASHBOARD_HTML
    assert ".price-change-line { font-size: 11px;" in DASHBOARD_HTML
    assert 'setFlipTextWithTitle("priceMetric", market.current_price === undefined ? "데이터 없음" : price(market.current_price));' in DASHBOARD_HTML
    assert "const upbitChangeRate = market.signed_change_rate ?? market.recent_change_pct;" in DASHBOARD_HTML
    assert 'setHtmlWithTitle("priceChange", `<span class="${changeClass(upbitChangeRate)}">${changeText}</span>`, priceText);' in DASHBOARD_HTML
    assert '`${price(market.current_price)} <span' not in DASHBOARD_HTML


def test_dashboard_flips_changing_numeric_metrics() -> None:
    assert ".flip-slot" in DASHBOARD_HTML
    assert ".flip-unit" in DASHBOARD_HTML
    assert "flex-wrap: wrap" in DASHBOARD_HTML
    assert "white-space: nowrap" in DASHBOARD_HTML
    assert "function flipTextTokens(text)" in DASHBOARD_HTML
    assert "flex: 0 0 auto" in DASHBOARD_HTML
    assert ".flip-card-old" in DASHBOARD_HTML
    assert ".flip-card-new" in DASHBOARD_HTML
    assert "@keyframes flip-clock-old" in DASHBOARD_HTML
    assert "@keyframes flip-clock-new" in DASHBOARD_HTML
    assert "function setFlipTextWithTitle(elementId, text, title = text)" in DASHBOARD_HTML
    assert "function renderFlipText(element, previous, next)" in DASHBOARD_HTML
    assert "function fitFlipTextToContainer(element)" in DASHBOARD_HTML
    assert "element.scrollWidth" in DASHBOARD_HTML
    assert "Math.max(Math.floor(currentFontSize * (availableWidth / contentWidth) * 0.96), 14)" in DASHBOARD_HTML
    assert "function flipDigit(oldChar, newChar)" in DASHBOARD_HTML
    assert '/[A-Za-z]/.test(char) ? "flip-char flip-unit" : "flip-char"' in DASHBOARD_HTML
    assert 'if (char !== oldChar && /\\d/.test(char))' in DASHBOARD_HTML
    assert 'setFlipTextWithTitle("priceMetric"' in DASHBOARD_HTML
    assert 'setFlipTextWithTitle("capitalMetric"' in DASHBOARD_HTML
    assert 'setFlipTextWithTitle("pnlMetric"' in DASHBOARD_HTML


def test_dashboard_includes_rule_review_pipeline_panel() -> None:
    assert "룰 개선" in DASHBOARD_HTML
    assert "Codex 자동 룰 개선 시작" in DASHBOARD_HTML
    assert "Codex 자동 룰 개선 진행" in DASHBOARD_HTML
    assert "다시 룰 개선" in DASHBOARD_HTML
    assert "진행 내용이 길면" in DASHBOARD_HTML
    assert 'postJson("/api/v1/rules/auto-improve"' in DASHBOARD_HTML
    assert "runCodexRuleAutomation" in DASHBOARD_HTML
    assert "renderRuleAutomationResult" in DASHBOARD_HTML
    assert "function maybeRunAutoRuleImprove(progress)" in DASHBOARD_HTML
    assert "학습완료율 100% 도달로 학습 데이터, 온체인 데이터, ETF 상태를 함께 분석합니다." in DASHBOARD_HTML
    assert 'sessionStorage.getItem(AUTO_RULE_READY_KEY) === "done"' in DASHBOARD_HTML
    assert "replay 결과" in DASHBOARD_HTML
    assert "demo 적용" in DASHBOARD_HTML
    assert "live 승인 적용" in DASHBOARD_HTML
    assert "커밋 해시 연결" in DASHBOARD_HTML
    assert "히스토리 보정" in DASHBOARD_HTML
    assert "룰 변경 롤백" in DASHBOARD_HTML
    assert 'postJson("/api/v1/rules/review"' in DASHBOARD_HTML
    assert 'fetchJson("/api/v1/rules/proposals"' in DASHBOARD_HTML
    assert 'fetchJson("/api/v1/rules/history"' in DASHBOARD_HTML
    assert "/commit-hash" in DASHBOARD_HTML
    assert "/history-corrections" in DASHBOARD_HTML
    assert "/rollback" in DASHBOARD_HTML
    assert "refreshRuleHistory" in DASHBOARD_HTML
    assert "renderLatestRuleProposal" in DASHBOARD_HTML
    assert "renderRuleHistory" in DASHBOARD_HTML
    assert 'id="ruleDataQuality"' in DASHBOARD_HTML
    assert 'id="ruleReplayProfit"' in DASHBOARD_HTML
    assert "formatMarketDataQuality" in DASHBOARD_HTML
    assert "formatReplayProfit" in DASHBOARD_HTML


def test_settings_includes_server_name_field() -> None:
    assert 'id="serverName"' in SETTINGS_HTML
    assert "SERVER_NAME" in SETTINGS_HTML
    assert "텔레그램 테스트 메시지 전송" in SETTINGS_HTML
    assert "sendTelegramTest" in SETTINGS_HTML
    assert "/settings/telegram/test" in SETTINGS_HTML


def test_settings_rule_improvement_layout_wraps_long_text() -> None:
    assert ".rule-result { width: 100%; margin-top: 10px; border-collapse: collapse; table-layout: fixed;" in SETTINGS_HTML
    assert "overflow-wrap: anywhere; word-break: break-word;" in SETTINGS_HTML
    assert ".rule-final { margin-top: 14px;" in SETTINGS_HTML
    assert "white-space: pre-wrap" in SETTINGS_HTML
    assert ".rule-actions { display: grid; grid-template-columns: 1fr; }" in SETTINGS_HTML


def test_dashboard_includes_external_market_context_panel() -> None:
    assert "온체인/ETF 상황" in DASHBOARD_HTML
    assert 'fetchJson(force ? "/dashboard/external-context?force=true" : "/dashboard/external-context")' in DASHBOARD_HTML
    assert "renderExternalContext" in DASHBOARD_HTML
    assert 'id="onchainSource"' not in DASHBOARD_HTML
    assert 'id="etfSource"' not in DASHBOARD_HTML
    assert 'id="contextUsdPrice"' in DASHBOARD_HTML
    assert 'id="contextUsdPrice" class="context-value usd-price"' in DASHBOARD_HTML
    assert 'class="card market-context-card"' in DASHBOARD_HTML
    assert 'class="context-grid market-context-grid"' in DASHBOARD_HTML
    assert ".market-context-card .context-grid { grid-template-columns: repeat(2, minmax(0, 1fr));" in DASHBOARD_HTML
    assert ".market-context-card .market-context-detail { grid-column: 1 / -1; }" in DASHBOARD_HTML
    assert ".context-value.usd-price { font-size: 26px;" in DASHBOARD_HTML
    assert ".context-value.usd-price span { font-size: 13px;" in DASHBOARD_HTML
    assert ".context-value.usd-price .krw-price" in DASHBOARD_HTML
    assert "온체인 데이터" in DASHBOARD_HTML
    assert "온체인 상태" not in DASHBOARD_HTML
    assert 'id="onchainState" class="context-value compact"' in DASHBOARD_HTML
    assert 'id="etfState" class="context-value compact"' in DASHBOARD_HTML
    assert 'id="onchainDetails"' not in DASHBOARD_HTML
    assert 'id="contextStatus"' in DASHBOARD_HTML
    assert 'id="contextRecordedAt"' in DASHBOARD_HTML
    assert 'context-item half"><div class="context-label">수집 상태' in DASHBOARD_HTML
    assert 'context-item half"><div class="context-label">기록 시각' in DASHBOARD_HTML
    assert ".context-item.half { grid-column: span 2; }" in DASHBOARD_HTML
    assert "formatExternalContextSource" not in DASHBOARD_HTML
    assert "formatContextState" in DASHBOARD_HTML
    assert 'neutral: "중립"' in DASHBOARD_HTML
    assert 'not_applicable: "해당 없음"' in DASHBOARD_HTML
    assert 'unknown: "데이터 없음"' in DASHBOARD_HTML
    assert "순유입" in DASHBOARD_HTML
    assert "순유출" in DASHBOARD_HTML
    assert "function formatEtfFlowLine(etf)" in DASHBOARD_HTML
    assert 'if (flow > 0) return `순유입 ${number(flow, 0)} USD`;' in DASHBOARD_HTML
    assert 'if (flow < 0) return `순유출 ${number(Math.abs(flow), 0)} USD`;' in DASHBOARD_HTML
    assert '"순흐름 데이터 없음"' in DASHBOARD_HTML
    assert "`순유입 ${number(etf.inflow_usd || 0, 0)} USD`" not in DASHBOARD_HTML
    assert "`순유출 ${number(etf.outflow_usd || 0, 0)} USD`" not in DASHBOARD_HTML
    assert "function formatEtfFlowLines(etf)" in DASHBOARD_HTML
    assert "const lines = [];" in DASHBOARD_HTML
    assert 'if (inflow > 0) lines.push(formatEtfMetricLine("순유입", inflow, "USD", etf.inflow_usd_change, 0));' in DASHBOARD_HTML
    assert 'if (outflow > 0) lines.push(formatEtfMetricLine("순유출", outflow, "USD", etf.outflow_usd_change, 0));' in DASHBOARD_HTML
    assert "if (lines.length) return lines;" in DASHBOARD_HTML
    assert 'formatEtfMetricLine("보유수량 변화", holdingChange, `${tradeCoin}`, holdingChange, 0)' in DASHBOARD_HTML
    assert 'formatEtfMetricLine("총 AUM", etf.total_aum_usd, "USD", etf.total_aum_usd_change, 0, false)' in DASHBOARD_HTML
    assert 'formatEtfMetricLine("총 보유", etf.total_holding_coin, tradeCoin, etf.total_holding_coin_change, 0, false)' in DASHBOARD_HTML
    assert "showValueSign = true" in DASHBOARD_HTML
    assert 'const formattedValue = showValueSign ? signedNumber(numericValue, digits) : number(numericValue, digits);' in DASHBOARD_HTML
    assert 'signedNumber(numericChange, digits)' not in DASHBOARD_HTML
    assert "총 AUM" in DASHBOARD_HTML
    assert "총 보유" in DASHBOARD_HTML
    assert "거래소 순유입·순유출" in DASHBOARD_HTML
    assert "고래 지갑 움직임" in DASHBOARD_HTML
    assert "MVRV/SOPR" in DASHBOARD_HTML
    assert "formatContextBasis" in DASHBOARD_HTML
    assert 'activity_volume_proxy: " (활동·거래량 대체)"' in DASHBOARD_HTML
    assert 'price_change_proxy: " (가격변화 대체)"' in DASHBOARD_HTML
    assert "renderExternalContext(cachedExternalContextResponse.context || {}, marketResponse.summary || {});" in DASHBOARD_HTML
    assert "function renderExternalContext(context, market)" in DASHBOARD_HTML
    assert 'const upbitChangeRate = market.signed_change_rate ?? market.recent_change_pct;' in DASHBOARD_HTML
    assert 'class="krw-price">${price(market.current_price)} <span class="${changeClass(upbitChangeRate)}">' in DASHBOARD_HTML
    assert '${usd(marketData.usd_price)}<br><span class="${changeClass(usdChange)}">24시간 ${percent(usdChange)}</span><br>${krwPriceLine}' in DASHBOARD_HTML
    assert '].join("\\n");' in DASHBOARD_HTML


def test_dashboard_includes_no_trade_diagnostics_panel() -> None:
    assert "무거래 진단" in DASHBOARD_HTML
    assert 'fetchJson("/learning/diagnostics")' in DASHBOARD_HTML
    assert "renderNoTradeDiagnostics" in DASHBOARD_HTML
    assert 'id="noTradeDiagnosis" class="context-value compact"' in DASHBOARD_HTML
    assert 'id="noTradeMitigation" class="context-value compact"' in DASHBOARD_HTML
    assert 'id="noTradeBlockedReasons" class="context-value compact"' in DASHBOARD_HTML
    assert 'id="noTradeExternalContext" class="context-value compact"' in DASHBOARD_HTML
    assert 'id="noTradeEventsScanned" class="context-value compact"' in DASHBOARD_HTML
    assert "formatDiagnosticsExternalContext" in DASHBOARD_HTML
    assert "formatDiagnosisState" in DASHBOARD_HTML
    assert "formatMitigationAction" in DASHBOARD_HTML
    assert "formatBlockedReason" in DASHBOARD_HTML
    assert "formatCycleStatus" in DASHBOARD_HTML
    assert 'blocked: "매매 차단"' in DASHBOARD_HTML
    assert 'position_checked: "포지션 점검"' in DASHBOARD_HTML
    assert 'waiting: "대기 중"' in DASHBOARD_HTML
    assert 'filled: "체결 완료"' in DASHBOARD_HTML
    assert '${formatCycleStatus(lastCycle.status)}${lastCycle.reason ? " / " + formatBlockedReason(lastCycle.reason) : ""}' in DASHBOARD_HTML
    assert "white-space: pre-line" in DASHBOARD_HTML
    assert ".context-value.compact { font-size: 13px;" in DASHBOARD_HTML
    assert 'TRADES_FOUND: "체결 이벤트 확인"' in DASHBOARD_HTML
    assert 'NO_LEARNING_LOG: "학습 로그 없음"' in DASHBOARD_HTML
    assert 'AUTO_TRADING_NOT_RUNNING: "자동매매 미실행"' in DASHBOARD_HTML
    assert 'WAITING_FOR_SIGNAL: "신호 대기 중"' in DASHBOARD_HTML
    assert 'TRADE_BLOCKED_BY_RULES: "매매 규칙 차단"' in DASHBOARD_HTML
    assert 'NONE: "조치 불필요"' in DASHBOARD_HTML
    assert 'MONITOR: "추가 관찰"' in DASHBOARD_HTML
    assert 'RELAX_ENTRY_RULES_FOR_DEMO: "데모 진입 규칙 완화 검토"' in DASHBOARD_HTML
    assert 'MARKET_HISTORY_WARMING_UP: "시세 이력 준비 중"' in DASHBOARD_HTML
    assert 'POSITION_HELD: "포지션 보유 중"' in DASHBOARD_HTML
    assert 'POSITION_EXIT_TRIGGERED: "포지션 청산 실행"' in DASHBOARD_HTML
    assert 'LIVE_ORDER_PENDING: "실거래 주문 처리 대기"' in DASHBOARD_HTML
    assert 'DEMO_ASSET_WITHOUT_ACTIVE_POSITION: "데모 보유자산과 포지션 불일치"' in DASHBOARD_HTML
    assert 'LIVE_ASSET_WITHOUT_ACTIVE_POSITION: "실거래 보유자산과 포지션 불일치"' in DASHBOARD_HTML
    assert 'REENTRY_BLOCK_AFTER_SELL: "매도 후 재진입 대기"' in DASHBOARD_HTML
    assert 'MARKET_STATE_BEAR_ENTRY_BLOCK: "하락장 약한 진입 차단"' in DASHBOARD_HTML
    assert 'MARKET_STATE_BEAR_SCALE_IN_BLOCK: "하락장 추가매수 차단"' in DASHBOARD_HTML
    assert 'AUTO_MIN_SIGNAL_LEVEL: "최소 신호 점수 미달"' in DASHBOARD_HTML
    assert 'FEE_ADJUSTED_EDGE_LIMIT: "수수료 반영 기대수익 부족"' in DASHBOARD_HTML
    assert 'MIN_ORDER_AMOUNT: "최소 주문 금액 미달"' in DASHBOARD_HTML
    assert 'STOP_LOSS_PRICE_HIT: "손절가 도달"' in DASHBOARD_HTML
    assert 'TAKE_PROFIT_TARGET_HIT: "익절 목표 도달"' in DASHBOARD_HTML
    assert 'BOX_RANGE_HIGH_TAKE_PROFIT: "박스권 고점 익절"' in DASHBOARD_HTML
    assert "표본 ${number(summary.sample_count || 0)}건" in DASHBOARD_HTML
    assert "온체인 ${onchain}" in DASHBOARD_HTML
    assert "ETF ${etf}" in DASHBOARD_HTML
    assert "평균 가중치 ${number(summary.avg_learning_weight || 1, 3)}" in DASHBOARD_HTML


def test_dashboard_displays_learning_log_context() -> None:
    assert "학습 로그 경로" in DASHBOARD_HTML
    assert "learningResponse.learning_log_dir" in DASHBOARD_HTML
    assert "학습 로그 체결" in DASHBOARD_HTML
    assert "최근 체결 표와 다를 수 있습니다." in DASHBOARD_HTML


def test_dashboard_derives_win_rate_from_closed_execution_pnl() -> None:
    assert "function deriveExecutionWinRate(executions)" in DASHBOARD_HTML
    assert 'if (execution.side === "buy") {' in DASHBOARD_HTML
    assert "sellPnl += (priceValue * matched) - allocatedFee - (lot.costPerUnit * matched);" in DASHBOARD_HTML
    assert "return closedSells > 0 ? wins / closedSells : null;" in DASHBOARD_HTML
    assert 'fetchJson("/dashboard/executions?limit=1000")' in DASHBOARD_HTML
    assert "if (summary.realized_pnl > 0) return 1;" not in DASHBOARD_HTML
    assert "if (summary.realized_pnl < 0) return 0;" not in DASHBOARD_HTML


def test_dashboard_refresh_throttles_overlapping_requests() -> None:
    assert "let dashboardRefreshInFlight = false;" in DASHBOARD_HTML
    assert "let dashboardSlowRefreshInFlight = false;" in DASHBOARD_HTML
    assert "const DASHBOARD_REFRESH_INTERVAL_MS = 3000;" in DASHBOARD_HTML
    assert "const DASHBOARD_SLOW_REFRESH_INTERVAL_MS = 10000;" in DASHBOARD_HTML
    assert "if (dashboardRefreshInFlight) return;" in DASHBOARD_HTML
    assert "dashboardRefreshInFlight = false;" in DASHBOARD_HTML
    assert "function refreshSlowDashboardData" in DASHBOARD_HTML
    assert "return dashboardSlowRefreshInFlight;" in DASHBOARD_HTML
    assert 'console.warn(`느린 대시보드 데이터 갱신 실패: ${error.message}`);' in DASHBOARD_HTML
    assert "lastSlowDashboardRefreshAt = startedAt;" in DASHBOARD_HTML
    assert "setInterval(refreshDashboard, DASHBOARD_REFRESH_INTERVAL_MS);" in DASHBOARD_HTML


def test_dashboard_displays_trading_runtime_only_when_running() -> None:
    assert 'id="tradingRuntime" class="runtime-pill"' in DASHBOARD_HTML
    assert 'href="/health" target="_blank" rel="noreferrer">상태 API</a>\n        <span id="tradingRuntime"' in DASHBOARD_HTML
    assert "트레이딩 운영시간 : ${formatTradingRuntime(status.uptime_sec)}" in DASHBOARD_HTML
    assert "fetchJson(\"/settings/trading/status\")" in DASHBOARD_HTML
    assert "runtime.classList.remove(\"visible\")" in DASHBOARD_HTML
    assert "runtime.classList.add(\"visible\")" in DASHBOARD_HTML
    assert ".runtime-pill { display: none;" in DASHBOARD_HTML
    assert "width: 258px;" in DASHBOARD_HTML
    assert "font-variant-numeric: tabular-nums;" in DASHBOARD_HTML
    assert "flex: 0 0 258px;" in DASHBOARD_HTML
    assert "background: #f97316; color: #ffffff;" in DASHBOARD_HTML


def test_dashboard_displays_rule_review_coin_context() -> None:
    assert 'row("대상 코인"' in DASHBOARD_HTML
    assert 'row("룰 로그 경로"' in DASHBOARD_HTML
    assert 'row("외부 컨텍스트"' in DASHBOARD_HTML
    assert 'row("히스토리 경고"' in DASHBOARD_HTML
    assert "formatRuleExternalContext" in DASHBOARD_HTML
    assert "formatRuleHistoryWarnings" in DASHBOARD_HTML
    assert "commit_hash" in DASHBOARD_HTML
    assert "commit ${item.commit_hash}" in DASHBOARD_HTML


def test_settings_includes_rule_review_pipeline_panel() -> None:
    assert "Codex 자동 룰 개선 시작" in SETTINGS_HTML
    assert "Codex 자동 룰 개선 진행" in SETTINGS_HTML
    assert "다시 룰 개선" in SETTINGS_HTML
    assert "진행 내용이 길면" in SETTINGS_HTML
    assert 'postJson("/api/v1/rules/auto-improve"' in SETTINGS_HTML
    assert "runCodexRuleAutomation" in SETTINGS_HTML
    assert "renderRuleAutomationResult" in SETTINGS_HTML
    assert "replay 결과" in SETTINGS_HTML
    assert "demo 적용" in SETTINGS_HTML
    assert "live 승인 적용" in SETTINGS_HTML
    assert "커밋 해시 연결" in SETTINGS_HTML
    assert "히스토리 보정" in SETTINGS_HTML
    assert "룰 변경 롤백" in SETTINGS_HTML
    assert 'postJson("/api/v1/rules/review"' in SETTINGS_HTML
    assert 'fetchJson("/api/v1/rules/proposals"' in SETTINGS_HTML
    assert 'fetchJson("/api/v1/rules/history"' in SETTINGS_HTML
    assert "/commit-hash" in SETTINGS_HTML
    assert "/history-corrections" in SETTINGS_HTML
    assert "/rollback" in SETTINGS_HTML
    assert "refreshRuleHistory" in SETTINGS_HTML
    assert "renderLatestRuleProposal" in SETTINGS_HTML
    assert "renderRuleHistory" in SETTINGS_HTML
    assert 'row("대상 코인"' in SETTINGS_HTML
    assert 'row("룰 로그 경로"' in SETTINGS_HTML
    assert 'row("외부 컨텍스트"' in SETTINGS_HTML
    assert 'row("히스토리 경고"' in SETTINGS_HTML
    assert "formatRuleExternalContext" in SETTINGS_HTML
    assert "formatRuleHistoryWarnings" in SETTINGS_HTML
    assert "formatContextState" in SETTINGS_HTML
    assert 'neutral: "중립"' in SETTINGS_HTML
    assert 'not_applicable: "해당 없음"' in SETTINGS_HTML
    assert "commit_hash" in SETTINGS_HTML
    assert "commit ${item.commit_hash}" in SETTINGS_HTML


def test_settings_includes_external_context_and_no_trade_controls() -> None:
    assert "온체인/ETF 컨텍스트" in SETTINGS_HTML
    assert 'id="externalContextEnabled"' in SETTINGS_HTML
    assert 'id="externalContextCacheTtlSec"' in SETTINGS_HTML
    assert 'id="onchainContextUrl"' in SETTINGS_HTML
    assert 'id="onchainState"' in SETTINGS_HTML
    assert 'id="onchainActiveAddressesChangePct"' in SETTINGS_HTML
    assert 'id="onchainExchangeNetflowState"' in SETTINGS_HTML
    assert 'id="etfState"' in SETTINGS_HTML
    assert 'id="etfContextUrl"' in SETTINGS_HTML
    assert 'id="etfFlowUsd"' in SETTINGS_HTML
    assert "무거래 완화 정책" in SETTINGS_HTML
    assert 'id="noTradeAdaptiveEnabled"' in SETTINGS_HTML
    assert 'id="noTradeRelaxAfterCycles"' in SETTINGS_HTML
    assert 'id="noTradeRelaxMinScore"' in SETTINGS_HTML
    assert "syncTradeMarketFromCoin" in SETTINGS_HTML
    assert "EXTERNAL_CONTEXT_ENABLED" in SETTINGS_HTML
    assert "EXTERNAL_CONTEXT_CACHE_TTL_SEC" in SETTINGS_HTML
    assert "ONCHAIN_CONTEXT_URL" in SETTINGS_HTML
    assert "ONCHAIN_STATE" in SETTINGS_HTML
    assert "ETF_CONTEXT_URL" in SETTINGS_HTML
    assert 'ETF_CONTEXT_SOURCE: document.getElementById("etfContextUrl").value ? "http" : "web"' in SETTINGS_HTML
    assert "웹 공개 데이터 소스" in SETTINGS_HTML
    assert "Blockchain.com" in SETTINGS_HTML
    assert "XRPSCAN" in SETTINGS_HTML
    assert "NO_TRADE_RELAX_AFTER_CYCLES" in SETTINGS_HTML
