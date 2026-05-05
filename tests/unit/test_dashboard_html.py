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
    assert 'setHtmlWithTitle("priceChange", `<span class="${changeClass(market.recent_change_pct)}">${changeText}</span>`, priceText);' in DASHBOARD_HTML
    assert '`${price(market.current_price)} <span' not in DASHBOARD_HTML


def test_dashboard_includes_rule_review_pipeline_panel() -> None:
    assert "룰 개선" in DASHBOARD_HTML
    assert "룰 개선 분석 실행" in DASHBOARD_HTML
    assert "룰 변경안 생성" in DASHBOARD_HTML
    assert "replay 검증" in DASHBOARD_HTML
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
    assert 'id="onchainSource"' in DASHBOARD_HTML
    assert 'id="etfSource"' in DASHBOARD_HTML
    assert 'id="contextStatus"' in DASHBOARD_HTML
    assert 'id="contextRecordedAt"' in DASHBOARD_HTML
    assert "formatExternalContextSource" in DASHBOARD_HTML
    assert "formatContextState" in DASHBOARD_HTML
    assert 'neutral: "중립"' in DASHBOARD_HTML
    assert 'not_applicable: "해당 없음"' in DASHBOARD_HTML


def test_dashboard_includes_no_trade_diagnostics_panel() -> None:
    assert "무거래 진단" in DASHBOARD_HTML
    assert 'fetchJson("/learning/diagnostics")' in DASHBOARD_HTML
    assert "renderNoTradeDiagnostics" in DASHBOARD_HTML
    assert 'id="noTradeDiagnosis"' in DASHBOARD_HTML
    assert 'id="noTradeMitigation"' in DASHBOARD_HTML
    assert 'id="noTradeBlockedReasons"' in DASHBOARD_HTML
    assert 'id="noTradeExternalContext"' in DASHBOARD_HTML
    assert "formatDiagnosticsExternalContext" in DASHBOARD_HTML
    assert "formatDiagnosisState" in DASHBOARD_HTML
    assert "formatMitigationAction" in DASHBOARD_HTML
    assert "formatBlockedReason" in DASHBOARD_HTML
    assert 'TRADE_BLOCKED_BY_RULES: "매매 규칙 차단"' in DASHBOARD_HTML
    assert 'RELAX_ENTRY_RULES_FOR_DEMO: "데모 진입 규칙 완화 검토"' in DASHBOARD_HTML
    assert 'MARKET_HISTORY_WARMING_UP: "시세 이력 준비 중"' in DASHBOARD_HTML
    assert 'AUTO_MIN_SIGNAL_LEVEL: "최소 신호 점수 미달"' in DASHBOARD_HTML
    assert 'FEE_ADJUSTED_EDGE_LIMIT: "수수료 반영 기대수익 부족"' in DASHBOARD_HTML


def test_dashboard_displays_learning_log_context() -> None:
    assert "학습 로그 경로" in DASHBOARD_HTML
    assert "learningResponse.learning_log_dir" in DASHBOARD_HTML


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
    assert "룰 개선 분석 실행" in SETTINGS_HTML
    assert "룰 변경안 생성" in SETTINGS_HTML
    assert "replay 검증" in SETTINGS_HTML
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
    assert "NO_TRADE_RELAX_AFTER_CYCLES" in SETTINGS_HTML
