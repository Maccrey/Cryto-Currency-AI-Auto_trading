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


@dataclass(frozen=True)
class DemoRuleVariantPolicy:
    buy_multiplier: float
    sell_multiplier: float
    take_profit_pct: float
    stop_loss_pct: float
    entry_allowed: bool
    action_reason: str
    market_state: str
    market_pressure: float
    box_position: float | None


@dataclass
class ShadowPortfolio:
    cash_balance: float
    asset_balance: float
    avg_buy_price: float
    realized_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    stop_loss_count: int = 0
    loss_count: int = 0
    peak_equity: float | None = None
    max_drawdown_pct: float = 0.0
    last_action: str = "hold"


class DemoRuleVariantShadowTester:
    """Run A/B/C rule candidates on the same live tick stream without touching real orders."""

    DEFAULT_VARIANTS = (
        DemoRuleVariant(
            key="A",
            label="룰 A 안정형",
            description="기본 신호에 장세 민감 배수를 더해 균형 있게 추적합니다.",
            buy_multiplier=1.0,
            sell_multiplier=1.0,
            take_profit_pct=0.006,
            stop_loss_pct=0.004,
        ),
        DemoRuleVariant(
            key="B",
            label="룰 B 추세형",
            description="상승장 강도에만 진입을 키우고 추세 지속 시 익절 폭을 넓힙니다.",
            buy_multiplier=1.85,
            sell_multiplier=0.45,
            take_profit_pct=0.014,
            stop_loss_pct=0.0065,
        ),
        DemoRuleVariant(
            key="C",
            label="룰 C 방어형",
            description="하락장 노출을 빠르게 줄이고 박스권 하단에서만 작게 진입합니다.",
            buy_multiplier=0.38,
            sell_multiplier=2.0,
            take_profit_pct=0.0032,
            stop_loss_pct=0.002,
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
        leader = max(results, key=self._leader_score)
        return {
            "leader_key": leader["variant_key"],
            "leader_label": leader["variant_label"],
            "leader_reason": self._leader_reason(leader),
            "market_state": leader["market_state"],
            "market_state_label": leader["market_state_label"],
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
                    peak_equity=portfolio.cash_balance + (portfolio.asset_balance * current_price),
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
        policy = self._market_sensitive_policy(
            variant=variant,
            decision=decision,
            current_price=current_price,
        )
        action = "hold"
        if shadow.asset_balance > 0:
            action = self._maybe_shadow_sell(
                shadow=shadow,
                policy=policy,
                decision=decision,
                current_price=current_price,
            )
        elif decision.sizing.allowed:
            action = self._maybe_shadow_buy(
                shadow=shadow,
                policy=policy,
                decision=decision,
                current_price=current_price,
            )
        shadow.last_action = action
        equity = shadow.cash_balance + (shadow.asset_balance * current_price)
        self._update_drawdown(shadow=shadow, equity=equity)
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
            "stop_loss_count": shadow.stop_loss_count,
            "loss_count": shadow.loss_count,
            "win_rate": None if win_rate is None else round(win_rate, 4),
            "max_drawdown_pct": round(shadow.max_drawdown_pct, 6),
            "last_action": action,
            "action_reason": policy.action_reason,
            "entry_allowed_by_variant": policy.entry_allowed,
            "market_state": policy.market_state,
            "market_state_label": decision.regime.market_state_label,
            "market_pressure": policy.market_pressure,
            "box_position": policy.box_position,
            "buy_multiplier": variant.buy_multiplier,
            "sell_multiplier": variant.sell_multiplier,
            "take_profit_pct": variant.take_profit_pct,
            "stop_loss_pct": variant.stop_loss_pct,
            "effective_buy_multiplier": policy.buy_multiplier,
            "effective_sell_multiplier": policy.sell_multiplier,
            "effective_take_profit_pct": policy.take_profit_pct,
            "effective_stop_loss_pct": policy.stop_loss_pct,
        }

    def _market_sensitive_policy(
        self,
        *,
        variant: DemoRuleVariant,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> DemoRuleVariantPolicy:
        market_state = decision.regime.market_state if decision.regime.market_state in {"bull", "bear", "box"} else "box"
        market_pressure = self._market_pressure(decision)
        box_position = self._box_position(decision=decision, current_price=current_price)
        buy_multiplier = variant.buy_multiplier
        sell_multiplier = variant.sell_multiplier
        take_profit_pct = variant.take_profit_pct
        stop_loss_pct = variant.stop_loss_pct
        entry_allowed = True
        action_reason = f"{market_state}_neutral"

        if variant.key == "A":
            if market_state == "bull":
                buy_multiplier *= 1.0 + (max(market_pressure, 0.0) * 0.28)
                sell_multiplier *= 0.88
                take_profit_pct *= 1.12
                stop_loss_pct *= 1.04
                action_reason = "bull_balance_boost"
            elif market_state == "bear":
                buy_multiplier *= 0.35
                sell_multiplier *= 1.65
                take_profit_pct *= 0.72
                stop_loss_pct *= 0.65
                action_reason = "bear_balance_defense"
            else:
                lower_zone = box_position is None or box_position <= 0.45
                buy_multiplier *= 0.82 if lower_zone else 0.42
                sell_multiplier *= 1.08
                take_profit_pct *= 0.9
                stop_loss_pct *= 0.88
                entry_allowed = lower_zone
                action_reason = "box_lower_balance" if lower_zone else "box_upper_entry_block"

        if variant.key == "B":
            if market_state == "bull":
                buy_multiplier *= 1.28 + (max(market_pressure, 0.0) * 0.45)
                sell_multiplier *= 0.52
                take_profit_pct *= 1.35 + (max(market_pressure, 0.0) * 0.28)
                stop_loss_pct *= 1.18
                action_reason = "bull_trend_expansion"
            else:
                entry_allowed = False
                buy_multiplier = 0.0
                sell_multiplier *= 2.2 if market_state == "bear" else 1.55
                take_profit_pct *= 0.62 if market_state == "bear" else 0.78
                stop_loss_pct *= 0.55 if market_state == "bear" else 0.76
                action_reason = f"{market_state}_trend_entry_block"

        if variant.key == "C":
            if market_state == "bear":
                entry_allowed = False
                buy_multiplier = 0.0
                sell_multiplier *= 2.4
                take_profit_pct *= 0.58
                stop_loss_pct *= 0.55
                action_reason = "bear_defensive_exit"
            elif market_state == "box":
                lower_zone = box_position is not None and box_position <= 0.30
                entry_allowed = lower_zone
                buy_multiplier *= 0.72 if lower_zone else 0.0
                sell_multiplier *= 1.55 if lower_zone else 2.0
                take_profit_pct *= 0.72
                stop_loss_pct *= 0.70
                action_reason = "box_low_defensive_entry" if lower_zone else "box_mid_high_entry_block"
            else:
                buy_multiplier *= 0.42 + (max(market_pressure, 0.0) * 0.06)
                sell_multiplier *= 1.35
                take_profit_pct *= 0.82
                stop_loss_pct *= 0.72
                action_reason = "bull_defensive_participation"

        volatility_penalty = min(max(decision.features.short_volatility / 0.02, 0.0), 1.0)
        if volatility_penalty > 0.5:
            buy_multiplier *= 1.0 - ((volatility_penalty - 0.5) * 0.35)
            sell_multiplier *= 1.0 + ((volatility_penalty - 0.5) * 0.28)
            stop_loss_pct *= 0.88

        if decision.signal.level == "weak":
            if variant.key == "B":
                entry_allowed = entry_allowed and market_state == "bull" and market_pressure >= 0.15
                buy_multiplier *= 0.62
            elif variant.key == "C":
                buy_multiplier *= 0.55
            else:
                buy_multiplier *= 0.75

        return DemoRuleVariantPolicy(
            buy_multiplier=round(max(buy_multiplier, 0.0), 4),
            sell_multiplier=round(max(sell_multiplier, 0.0), 4),
            take_profit_pct=round(max(take_profit_pct, self._trading_fee_rate * 2), 6),
            stop_loss_pct=round(max(stop_loss_pct, self._trading_fee_rate * 2), 6),
            entry_allowed=entry_allowed,
            action_reason=action_reason,
            market_state=market_state,
            market_pressure=round(market_pressure, 4),
            box_position=None if box_position is None else round(box_position, 4),
        )

    def _maybe_shadow_buy(
        self,
        *,
        shadow: ShadowPortfolio,
        policy: DemoRuleVariantPolicy,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> str:
        if not policy.entry_allowed:
            return "hold"
        buy_amount = min(
            max(decision.sizing.buy_amount * policy.buy_multiplier, 0.0),
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
        policy: DemoRuleVariantPolicy,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> str:
        if shadow.avg_buy_price <= 0:
            return "hold"
        profit_pct = (current_price - shadow.avg_buy_price) / shadow.avg_buy_price
        stop_loss_triggered = profit_pct <= -policy.stop_loss_pct
        should_exit = (
            profit_pct >= policy.take_profit_pct
            or stop_loss_triggered
            or decision.regime.market_state == "bear"
            or self._box_high_exit(decision=decision, current_price=current_price)
        )
        if not should_exit:
            return "hold"
        base_sell_ratio = decision.sizing.sell_ratio if decision.sizing.sell_ratio > 0 else 0.35
        sell_ratio = min(max(base_sell_ratio * policy.sell_multiplier, 0.1), 1.0)
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
        if pnl < 0:
            shadow.loss_count += 1
        if stop_loss_triggered:
            shadow.stop_loss_count += 1
        if pnl > 0:
            shadow.win_count += 1
        return "sell"

    @staticmethod
    def _update_drawdown(*, shadow: ShadowPortfolio, equity: float) -> None:
        if shadow.peak_equity is None or equity > shadow.peak_equity:
            shadow.peak_equity = equity
            return
        if shadow.peak_equity <= 0:
            return
        drawdown = (shadow.peak_equity - equity) / shadow.peak_equity
        shadow.max_drawdown_pct = max(shadow.max_drawdown_pct, drawdown)

    @staticmethod
    def _market_pressure(decision: TradeDecisionResult) -> float:
        momentum = max(min(decision.features.ret_30s / 0.02, 1.0), -1.0)
        imbalance = max(min(decision.features.orderbook_imbalance / 0.35, 1.0), -1.0)
        ma_trend = max(min(decision.features.ma_trend / 0.01, 1.0), -1.0)
        return max(min((momentum * 0.5) + (imbalance * 0.35) + (ma_trend * 0.15), 1.0), -1.0)

    @staticmethod
    def _box_position(*, decision: TradeDecisionResult, current_price: float) -> float | None:
        low = decision.regime.box_range_low
        high = decision.regime.box_range_high
        if low is None or high is None or high <= low:
            return None
        return max(min((current_price - low) / (high - low), 1.0), 0.0)

    @staticmethod
    def _box_high_exit(*, decision: TradeDecisionResult, current_price: float) -> bool:
        if decision.regime.market_state != "box":
            return False
        position = DemoRuleVariantShadowTester._box_position(decision=decision, current_price=current_price)
        return position is not None and position >= 0.82

    @staticmethod
    def _leader_score(item: dict[str, object]) -> tuple[float, float, int]:
        profit_rate = float(item.get("profit_rate") or 0.0)
        trade_count = int(item.get("trade_count") or 0)
        stop_loss_count = int(item.get("stop_loss_count") or 0)
        loss_count = int(item.get("loss_count") or 0)
        max_drawdown_pct = float(item.get("max_drawdown_pct") or 0.0)
        market_state = str(item.get("market_state") or "box")
        market_pressure = float(item.get("market_pressure") or 0.0)
        variant_key = str(item.get("variant_key") or "")
        suitability = 0.0
        if market_state == "bull":
            suitability = {"B": 0.12, "A": 0.08, "C": 0.03}.get(variant_key, 0.0)
            suitability += max(market_pressure, 0.0) * (0.08 if variant_key == "B" else 0.03)
        elif market_state == "bear":
            suitability = {"C": 0.12, "A": 0.05, "B": -0.04}.get(variant_key, 0.0)
            suitability += abs(min(market_pressure, 0.0)) * (0.06 if variant_key == "C" else 0.02)
        else:
            suitability = {"C": 0.09, "A": 0.07, "B": -0.02}.get(variant_key, 0.0)
        risk_penalty = (max_drawdown_pct * 0.75) + (stop_loss_count * 0.004) + (loss_count * 0.0015)
        risk_adjusted_profit = profit_rate - risk_penalty
        return risk_adjusted_profit, suitability, trade_count

    @staticmethod
    def _leader_reason(leader: dict[str, object]) -> str:
        return (
            f"{leader['variant_label']}이 {leader['market_state_label']} 흐름에서 "
            f"현재 수익률 {float(leader['profit_rate']):.2%}로 가장 높습니다. "
            f"적용 사유는 {leader['action_reason']}입니다."
        )

    @staticmethod
    def _empty_report() -> dict[str, object]:
        return {
            "leader_key": None,
            "leader_label": None,
            "leader_reason": "현재가가 없어 A/B/C 동시 테스트를 실행하지 못했습니다.",
            "market_state": None,
            "market_state_label": None,
            "results": [],
        }
