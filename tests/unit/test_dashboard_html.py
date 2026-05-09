from app.api.routes.dashboard import DASHBOARD_HTML
from app.api.routes.settings import SETTINGS_HTML


def test_dashboard_price_card_labels_trend_as_volume() -> None:
    assert "`거래량 ${trendStreak.trend}(${trendStreak.count})`" in DASHBOARD_HTML
    assert "`거래량 <span class=\"badge ${trendBadgeClass(trendStreak.trend)}\">" in DASHBOARD_HTML
    assert "`${market.market || marketLabel} <span" not in DASHBOARD_HTML


def test_dashboard_price_card_renders_change_on_separate_small_line() -> None:
    assert 'id="priceChange" class="price-change-line"' in DASHBOARD_HTML
    assert ".price-change-line { font-size: 11px;" in DASHBOARD_HTML
    assert 'setTextWithTitle("priceMetric", market.current_price === undefined ? "데이터 없음" : price(market.current_price));' in DASHBOARD_HTML
    assert "const upbitChangeRate = market.signed_change_rate ?? market.recent_change_pct;" in DASHBOARD_HTML
    assert 'setHtmlWithTitle("priceChange", `<span class="${changeClass(upbitChangeRate)}">${changeText}</span>`, priceText);' in DASHBOARD_HTML
    assert '`${price(market.current_price)} <span' not in DASHBOARD_HTML


def test_dashboard_includes_rule_review_pipeline_panel() -> None:
    assert "룰 개선" in DASHBOARD_HTML
    assert "Codex 자동 룰 개선 시작" in DASHBOARD_HTML
    assert "Codex 자동 룰 개선 진행" in DASHBOARD_HTML
    assert "다시 룰 개선" in DASHBOARD_HTML
    assert "진행 내용이 길면" in DASHBOARD_HTML
    assert 'postJson("/api/v1/rules/auto-improve"' in DASHBOARD_HTML
    assert "runCodexRuleAutomation" in DASHBOARD_HTML
    assert "renderRuleAutomationResult" in DASHBOARD_HTML
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


def test_dashboard_includes_external_market_context_panel() -> None:
    assert "온체인/ETF 상황" in DASHBOARD_HTML
    assert 'fetchJson("/dashboard/external-context")' in DASHBOARD_HTML
    assert "renderExternalContext" in DASHBOARD_HTML
    assert 'id="onchainSource"' not in DASHBOARD_HTML
    assert 'id="etfSource"' not in DASHBOARD_HTML
    assert 'id="contextUsdPrice"' in DASHBOARD_HTML
    assert 'id="contextUsdPrice" class="context-value usd-price"' in DASHBOARD_HTML
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
    assert 'formatEtfMetricLine("순유입", inflow, "USD", etf.inflow_usd_change, 0)' in DASHBOARD_HTML
    assert 'formatEtfMetricLine("순유출", outflow, "USD", etf.outflow_usd_change, 0)' in DASHBOARD_HTML
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
    assert "renderExternalContext(externalContextResponse.context || {}, marketResponse.summary || {});" in DASHBOARD_HTML
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
    assert 'AUTO_MIN_SIGNAL_LEVEL: "최소 신호 점수 미달"' in DASHBOARD_HTML
    assert 'FEE_ADJUSTED_EDGE_LIMIT: "수수료 반영 기대수익 부족"' in DASHBOARD_HTML
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
    assert "웹 공개 데이터 소스" in SETTINGS_HTML
    assert "Blockchain.com" in SETTINGS_HTML
    assert "XRPSCAN" in SETTINGS_HTML
    assert "NO_TRADE_RELAX_AFTER_CYCLES" in SETTINGS_HTML
