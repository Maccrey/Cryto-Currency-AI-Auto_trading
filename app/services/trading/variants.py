from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from app.services.portfolio.sync import PortfolioState
from app.services.trading.decision import TradeDecisionResult


@dataclass(frozen=True)
class DemoRuleVariant:
    key: str
    label: str
    description: str
    buy_multiplier: float
    sell_multiplier: float
    take_profit_pct: float
    stop_loss_pct: float

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ShadowPortfolio:
    cash_balance: float
    asset_balance: float
    avg_buy_price: float
    realized_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    last_action: str = "hold"


class DemoRuleVariantShadowTester:
    """Run A/B/C rule candidates on the same live tick stream without touching real orders."""

    DEFAULT_VARIANTS = (
        DemoRuleVariant(
            key="A",
            label="룰 A 안정형",
            description="기본 신호와 기본 익절/손절 폭으로 추적합니다.",
            buy_multiplier=1.0,
            sell_multiplier=1.0,
            take_profit_pct=0.006,
            stop_loss_pct=0.004,
        ),
        DemoRuleVariant(
            key="B",
            label="룰 B 추세형",
            description="상승장에서만 진입을 키우고 익절 폭을 넓힙니다.",
            buy_multiplier=1.18,
            sell_multiplier=0.82,
            take_profit_pct=0.009,
            stop_loss_pct=0.005,
        ),
        DemoRuleVariant(
            key="C",
            label="룰 C 방어형",
            description="하락장과 박스권에서 작게 진입하고 빠르게 줄입니다.",
            buy_multiplier=0.72,
            sell_multiplier=1.3,
            take_profit_pct=0.004,
            stop_loss_pct=0.003,
        ),
    )

    def __init__(
        self,
        *,
        variants: Iterable[DemoRuleVariant] | None = None,
        trading_fee_rate: float = 0.0005,
    ) -> None:
        self._variants = tuple(variants or self.DEFAULT_VARIANTS)
        self._trading_fee_rate = trading_fee_rate
        self._portfolios: dict[str, ShadowPortfolio] = {}
        self._initial_equity: float | None = None

    def evaluate(
        self,
        *,
        decision: TradeDecisionResult,
        current_price: float,
        portfolio: PortfolioState,
    ) -> dict[str, object]:
        if current_price <= 0:
            return self._empty_report()
        self._ensure_started(portfolio=portfolio, current_price=current_price)
        results = [
            self._evaluate_variant(
                variant=variant,
                decision=decision,
                current_price=current_price,
            )
            for variant in self._variants
        ]
        leader = max(results, key=lambda item: (float(item["profit_rate"]), item["variant_key"] == "A"))
        return {
            "leader_key": leader["variant_key"],
            "leader_label": leader["variant_label"],
            "leader_reason": self._leader_reason(leader),
            "results": results,
        }

    def _ensure_started(self, *, portfolio: PortfolioState, current_price: float) -> None:
        if self._initial_equity is None:
            self._initial_equity = max(
                portfolio.cash_balance + (portfolio.asset_balance * current_price),
                1.0,
            )
        for variant in self._variants:
            self._portfolios.setdefault(
                variant.key,
                ShadowPortfolio(
                    cash_balance=portfolio.cash_balance,
                    asset_balance=portfolio.asset_balance,
                    avg_buy_price=portfolio.avg_buy_price,
                ),
            )

    def _evaluate_variant(
        self,
        *,
        variant: DemoRuleVariant,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> dict[str, object]:
        shadow = self._portfolios[variant.key]
        action = "hold"
        if shadow.asset_balance > 0:
            action = self._maybe_shadow_sell(
                shadow=shadow,
                variant=variant,
                decision=decision,
                current_price=current_price,
            )
        elif decision.sizing.allowed and decision.signal.level != "weak":
            action = self._maybe_shadow_buy(
                shadow=shadow,
                variant=variant,
                decision=decision,
                current_price=current_price,
            )
        shadow.last_action = action
        equity = shadow.cash_balance + (shadow.asset_balance * current_price)
        profit_rate = 0.0 if self._initial_equity is None else (equity - self._initial_equity) / self._initial_equity
        win_rate = None if shadow.trade_count <= 0 else shadow.win_count / shadow.trade_count
        return {
            "variant_key": variant.key,
            "variant_label": variant.label,
            "description": variant.description,
            "profit_rate": round(profit_rate, 6),
            "equity": round(equity, 2),
            "cash_balance": round(shadow.cash_balance, 2),
            "asset_balance": round(shadow.asset_balance, 8),
            "avg_buy_price": round(shadow.avg_buy_price, 8),
            "realized_pnl": round(shadow.realized_pnl, 2),
            "trade_count": shadow.trade_count,
            "win_rate": None if win_rate is None else round(win_rate, 4),
            "last_action": action,
            "buy_multiplier": variant.buy_multiplier,
            "sell_multiplier": variant.sell_multiplier,
            "take_profit_pct": variant.take_profit_pct,
            "stop_loss_pct": variant.stop_loss_pct,
        }

    def _maybe_shadow_buy(
        self,
        *,
        shadow: ShadowPortfolio,
        variant: DemoRuleVariant,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> str:
        if variant.key == "B" and decision.regime.market_state != "bull":
            return "hold"
        buy_amount = min(
            max(decision.sizing.buy_amount * variant.buy_multiplier, 0.0),
            shadow.cash_balance / (1 + self._trading_fee_rate),
        )
        if buy_amount <= 0:
            return "hold"
        quantity = round(buy_amount / current_price, 8)
        fee = buy_amount * self._trading_fee_rate
        total_cost = (shadow.avg_buy_price * shadow.asset_balance) + buy_amount + fee
        shadow.asset_balance = round(shadow.asset_balance + quantity, 8)
        shadow.cash_balance = round(shadow.cash_balance - buy_amount - fee, 2)
        shadow.avg_buy_price = 0.0 if shadow.asset_balance <= 0 else total_cost / shadow.asset_balance
        return "buy"

    def _maybe_shadow_sell(
        self,
        *,
        shadow: ShadowPortfolio,
        variant: DemoRuleVariant,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> str:
        if shadow.avg_buy_price <= 0:
            return "hold"
        profit_pct = (current_price - shadow.avg_buy_price) / shadow.avg_buy_price
        should_exit = (
            profit_pct >= variant.take_profit_pct
            or profit_pct <= -variant.stop_loss_pct
            or decision.regime.market_state == "bear"
        )
        if not should_exit:
            return "hold"
        base_sell_ratio = decision.sizing.sell_ratio if decision.sizing.sell_ratio > 0 else 0.35
        sell_ratio = min(max(base_sell_ratio * variant.sell_multiplier, 0.1), 1.0)
        quantity = round(shadow.asset_balance * sell_ratio, 8)
        if quantity <= 0:
            return "hold"
        proceeds = quantity * current_price
        fee = proceeds * self._trading_fee_rate
        cost_basis = shadow.avg_buy_price * quantity
        pnl = proceeds - fee - cost_basis
        shadow.cash_balance = round(shadow.cash_balance + proceeds - fee, 2)
        shadow.asset_balance = round(max(shadow.asset_balance - quantity, 0.0), 8)
        if shadow.asset_balance <= 0:
            shadow.asset_balance = 0.0
            shadow.avg_buy_price = 0.0
        shadow.realized_pnl = round(shadow.realized_pnl + pnl, 2)
        shadow.trade_count += 1
        if pnl > 0:
            shadow.win_count += 1
        return "sell"

    @staticmethod
    def _leader_reason(leader: dict[str, object]) -> str:
        return (
            f"{leader['variant_label']}이 같은 시세 흐름에서 현재 수익률 "
            f"{float(leader['profit_rate']):.2%}로 가장 높습니다."
        )

    @staticmethod
    def _empty_report() -> dict[str, object]:
        return {
            "leader_key": None,
            "leader_label": None,
            "leader_reason": "현재가가 없어 A/B/C 동시 테스트를 실행하지 못했습니다.",
            "results": [],
        }
