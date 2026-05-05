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
    assert 'postJson("/api/v1/rules/review"' in DASHBOARD_HTML
    assert 'fetchJson("/api/v1/rules/proposals"' in DASHBOARD_HTML
    assert "renderLatestRuleProposal" in DASHBOARD_HTML


def test_settings_includes_rule_review_pipeline_panel() -> None:
    assert "룰 개선 분석 실행" in SETTINGS_HTML
    assert "룰 변경안 생성" in SETTINGS_HTML
    assert "replay 검증" in SETTINGS_HTML
    assert "demo 적용" in SETTINGS_HTML
    assert "live 승인 적용" in SETTINGS_HTML
    assert 'postJson("/api/v1/rules/review"' in SETTINGS_HTML
    assert 'fetchJson("/api/v1/rules/proposals"' in SETTINGS_HTML
    assert "renderLatestRuleProposal" in SETTINGS_HTML
