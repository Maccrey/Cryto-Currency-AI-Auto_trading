"""Demo rule variants (A – F) with market-state-aware policies.

Improvements over the previous version
---------------------------------------
1. **Transition detection integrated**: Every variant now uses
   ``TransitionState`` (bear→bull / bull→bear scores) to boost or
   suppress entries at regime-change inflection points.

2. **Dynamic box range**: Variants use ``regime.dynamic_box_low/high``
   (computed from 100-200 tick history) rather than the single-tick
   static range, so box-position signals are far more stable.

3. **Forced sell on bull→bear**: When a confirmed bull→bear transition
   is detected the sell multiplier is amplified and the take-profit
   threshold is lowered so the position is exited quickly.

4. **Per-variant box thresholds adjusted**:
   - A: lower-zone threshold loosened to 50% (was 45%)
   - C: lower-zone threshold loosened to 40% (was 30%)
   - E: lower-zone threshold loosened to 38% (was 25%)

5. **Transition-boosted buy multiplier**: bear→bull score ≥ 0.60 adds a
   configurable boost (default ×1.35) to entry size across all variants.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Iterable

from app.services.portfolio.sync import PortfolioState
from app.services.trading.decision import TradeDecisionResult
from app.services.trading.market_transition import MarketTransitionDetector, TransitionState


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
    # Transition metadata
    bear_to_bull_score: float
    bull_to_bear_score: float
    transition_buy_boost: float
    forced_sell: bool


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
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    peak_equity: float | None = None
    max_drawdown_pct: float = 0.0
    last_action: str = "hold"


class DemoRuleVariantShadowTester:
    """Run diversified rule candidates on the same tick stream without touching real orders.

    Key additions:
    - Embeds a ``MarketTransitionDetector`` shared across all variants so
      transition signals are consistent.
    - Provides ``_resolve_box_position()`` which prefers the dynamic box range
      over the legacy static range.
    - All per-variant policies respect transition state for entry boosts and
      forced exits.
    """

    MIN_PROMOTION_TRADES = 20

    # Bear-to-bull confirmed → buy multiplier is boosted by this factor
    BEAR_TO_BULL_BUY_BOOST = 1.35
    # Bull-to-bear confirmed → sell multiplier is boosted by this factor
    BULL_TO_BEAR_SELL_BOOST = 1.80

    DEFAULT_VARIANTS = (
        DemoRuleVariant(
            key="A",
            label="룰 A 안정형",
            description="기본 신호에 장세 민감 배수와 전환 감지를 더해 균형 있게 추적합니다.",
            buy_multiplier=1.0,
            sell_multiplier=1.0,
            take_profit_pct=0.006,
            stop_loss_pct=0.004,
        ),
        DemoRuleVariant(
            key="B",
            label="룰 B 추세형",
            description="상승장 강도와 하락→상승 전환에만 진입을 키우고 추세 지속 시 익절 폭을 넓힙니다.",
            buy_multiplier=1.85,
            sell_multiplier=0.45,
            take_profit_pct=0.014,
            stop_loss_pct=0.0065,
        ),
        DemoRuleVariant(
            key="C",
            label="룰 C 방어형",
            description="하락장 노출을 빠르게 줄이고 박스권 하단(40%이하)과 전환 구간에서만 작게 진입합니다.",
            buy_multiplier=0.38,
            sell_multiplier=2.0,
            take_profit_pct=0.0032,
            stop_loss_pct=0.002,
        ),
        DemoRuleVariant(
            key="D",
            label="룰 D 돌파확인형",
            description="전환 확인 또는 상승장 돌파가 모멘텀과 호가로 확인될 때만 진입하고 추세를 길게 보유합니다.",
            buy_multiplier=1.25,
            sell_multiplier=0.7,
            take_profit_pct=0.010,
            stop_loss_pct=0.0045,
        ),
        DemoRuleVariant(
            key="E",
            label="룰 E 박스저점형",
            description="박스권 하단(38%이하) 반등 또는 전환 구간을 거래하고 상단 접근 시 빠르게 청산합니다.",
            buy_multiplier=0.72,
            sell_multiplier=1.7,
            take_profit_pct=0.0048,
            stop_loss_pct=0.0028,
        ),
        DemoRuleVariant(
            key="F",
            label="룰 F 자본보전형",
            description="강한 상승 신호·전환 구간에서만 작게 진입해 손절 빈도와 낙폭 억제를 우선합니다.",
            buy_multiplier=0.32,
            sell_multiplier=2.2,
            take_profit_pct=0.0075,
            stop_loss_pct=0.003,
        ),
    )

    def __init__(
        self,
        *,
        variants: Iterable[DemoRuleVariant] | None = None,
        trading_fee_rate: float = 0.0005,
        transition_detector: MarketTransitionDetector | None = None,
    ) -> None:
        self._variants = tuple(variants or self.DEFAULT_VARIANTS)
        self._trading_fee_rate = trading_fee_rate
        self._portfolios: dict[str, ShadowPortfolio] = {}
        self._initial_equity: float | None = None
        self._applied_variant_key: str | None = None
        self._transition_detector = transition_detector or MarketTransitionDetector()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

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

        # Evaluate transition state once for all variants
        transition = self._transition_detector.evaluate(
            decision.features,
            current_price=current_price,
            current_market_state=decision.regime.market_state,
        )

        results = [
            self._evaluate_variant(
                variant=variant,
                decision=decision,
                current_price=current_price,
                transition=transition,
            )
            for variant in self._variants
        ]
        candidate = max(results, key=self._candidate_score)
        promotable = [item for item in results if self._promotion_eligible(item)]
        leader = max(promotable, key=self._leader_score) if promotable else None
        selection_changed = leader is not None and leader["variant_key"] != self._applied_variant_key
        if selection_changed:
            self._applied_variant_key = str(leader["variant_key"])
        applied = next(
            (item for item in results if item["variant_key"] == self._applied_variant_key),
            None,
        )
        return {
            "leader_key": None if applied is None else applied["variant_key"],
            "leader_label": None if applied is None else applied["variant_label"],
            "leader_reason": (
                self._leader_reason(leader)
                if leader is not None
                else self._no_positive_leader_reason(candidate, applied)
            ),
            "candidate_leader_key": candidate["variant_key"],
            "candidate_leader_label": candidate["variant_label"],
            "candidate_leader_profit_rate": candidate["profit_rate"],
            "promotion_eligible": applied is not None,
            "selection_changed": selection_changed,
            "applied_variant_key": None if applied is None else applied["variant_key"],
            "applied_variant_label": None if applied is None else applied["variant_label"],
            "market_state": candidate["market_state"],
            "market_state_label": candidate["market_state_label"],
            "bear_to_bull_score": transition.bear_to_bull_score,
            "bull_to_bear_score": transition.bull_to_bear_score,
            "bear_to_bull_confirmed": transition.bear_to_bull_confirmed,
            "bull_to_bear_confirmed": transition.bull_to_bear_confirmed,
            "dynamic_box_low": transition.dynamic_box_low,
            "dynamic_box_high": transition.dynamic_box_high,
            "dynamic_box_position": transition.dynamic_box_position,
            "results": results,
        }

    def reset(self) -> None:
        self._portfolios.clear()
        self._initial_equity = None
        self._applied_variant_key = None
        self._transition_detector.reset()

    def apply_selected_variant(
        self,
        *,
        decision: TradeDecisionResult,
        current_price: float,
    ) -> TradeDecisionResult:
        variant = next(
            (item for item in self._variants if item.key == self._applied_variant_key),
            None,
        )
        if variant is None or current_price <= 0:
            return decision

        # Re-evaluate transition for real-time apply (uses cached state)
        transition = self._transition_detector.evaluate(
            decision.features,
            current_price=current_price,
            current_market_state=decision.regime.market_state,
        )
        policy = self._market_sensitive_policy(
            variant=variant,
            decision=decision,
            current_price=current_price,
            transition=transition,
        )
        if not policy.entry_allowed or policy.buy_multiplier <= 0:
            return replace(
                decision,
                sizing=replace(
                    decision.sizing,
                    allowed=False,
                    buy_ratio=0.0,
                    buy_amount=0.0,
                    buy_quantity=0.0,
                    blocked_reason="RULE_VARIANT_ENTRY_BLOCK",
                ),
            )
        sizing = decision.sizing
        if not sizing.allowed or sizing.buy_amount <= 0:
            return decision
        buy_ratio = round(min(sizing.buy_ratio * policy.buy_multiplier, 1.0), 3)
        buy_amount = round(sizing.buy_amount * policy.buy_multiplier, 1)
        return replace(
            decision,
            sizing=replace(
                sizing,
                buy_ratio=buy_ratio,
                buy_amount=buy_amount,
                buy_quantity=round(buy_amount / current_price, 4),
            ),
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

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
        transition: TransitionState,
    ) -> dict[str, object]:
        shadow = self._portfolios[variant.key]
        policy = self._market_sensitive_policy(
            variant=variant,
            decision=decision,
            current_price=current_price,
            transition=transition,
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
        profit_factor = (
            999.0
            if shadow.gross_profit > 0 and shadow.gross_loss <= 0
            else None if shadow.gross_loss <= 0 else shadow.gross_profit / shadow.gross_loss
        )
        stop_loss_rate = None if shadow.trade_count <= 0 else shadow.stop_loss_count / shadow.trade_count
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
            "profit_factor": None if profit_factor is None else round(profit_factor, 4),
            "stop_loss_rate": None if stop_loss_rate is None else round(stop_loss_rate, 4),
            "promotion_eligible": False,
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
            "bear_to_bull_score": policy.bear_to_bull_score,
            "bull_to_bear_score": policy.bull_to_bear_score,
            "transition_buy_boost": policy.transition_buy_boost,
            "forced_sell": policy.forced_sell,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Market-sensitive policy computation (all rule logic lives here)
    # ──────────────────────────────────────────────────────────────────────────

    def _market_sensitive_policy(
        self,
        *,
        variant: DemoRuleVariant,
        decision: TradeDecisionResult,
        current_price: float,
        transition: TransitionState,
    ) -> DemoRuleVariantPolicy:
        market_state = decision.regime.market_state if decision.regime.market_state in {"bull", "bear", "box"} else "box"
        market_pressure = self._market_pressure(decision)
        # Prefer dynamic box position (history-based) over static single-tick range
        box_position = self._resolve_box_position(
            decision=decision,
            current_price=current_price,
            transition=transition,
        )
        buy_multiplier = variant.buy_multiplier
        sell_multiplier = variant.sell_multiplier
        take_profit_pct = variant.take_profit_pct
        stop_loss_pct = variant.stop_loss_pct
        entry_allowed = True
        action_reason = f"{market_state}_neutral"
        b2b = transition.bear_to_bull_score
        bu2be = transition.bull_to_bear_score
        b2b_confirmed = transition.bear_to_bull_confirmed
        bu2be_confirmed = transition.bull_to_bear_confirmed

        # ── Forced sell flag: apply to all variants when bull→bear is confirmed ─
        forced_sell = bu2be_confirmed and market_state in {"bull", "box"}

        # ── Transition buy boost (shared across variants) ──────────────────────
        # Applied *after* per-variant logic so it stacks on top
        transition_buy_boost = 1.0
        if b2b_confirmed and market_state in {"bear", "box"}:
            transition_buy_boost = self.BEAR_TO_BULL_BUY_BOOST
        elif b2b >= 0.40 and market_state == "box":
            # Partial boost when score is approaching threshold
            transition_buy_boost = 1.0 + (b2b - 0.40) * 1.0  # linear 1.0→1.60

        # ════════════════════════════════════════════════════════════════════════
        # Rule A – Balanced tracker (improved)
        # ════════════════════════════════════════════════════════════════════════
        if variant.key == "A":
            if market_state == "bull":
                buy_multiplier *= 1.0 + (max(market_pressure, 0.0) * 0.30)
                sell_multiplier *= 0.85
                take_profit_pct *= 1.15
                stop_loss_pct *= 1.05
                action_reason = "bull_balance_boost"
            elif market_state == "bear":
                if b2b_confirmed:
                    # Bear→bull transition confirmed: enter cautiously
                    buy_multiplier *= 0.65
                    sell_multiplier *= 1.10
                    take_profit_pct *= 0.90
                    stop_loss_pct *= 0.80
                    entry_allowed = True
                    action_reason = "bear_to_bull_transition_entry"
                else:
                    buy_multiplier *= 0.30
                    sell_multiplier *= 1.70
                    take_profit_pct *= 0.70
                    stop_loss_pct *= 0.65
                    entry_allowed = b2b >= 0.45  # allow if transition building
                    action_reason = "bear_balance_defense" if not entry_allowed else "bear_transition_watch"
            else:  # box
                # Loosened lower-zone threshold: 50% (was 45%)
                lower_zone = box_position is None or box_position <= 0.50
                mid_zone = box_position is not None and 0.50 < box_position <= 0.68
                buy_multiplier *= (0.90 if lower_zone else (0.55 if mid_zone else 0.38))
                sell_multiplier *= 1.08
                take_profit_pct *= 0.92
                stop_loss_pct *= 0.88
                entry_allowed = lower_zone or mid_zone
                action_reason = (
                    "box_lower_balance" if lower_zone
                    else ("box_mid_balance" if mid_zone else "box_upper_entry_block")
                )

        # ════════════════════════════════════════════════════════════════════════
        # Rule B – Trend follower (improved)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "B":
            if market_state == "bull":
                buy_multiplier *= 1.30 + (max(market_pressure, 0.0) * 0.48)
                sell_multiplier *= 0.50
                take_profit_pct *= 1.38 + (max(market_pressure, 0.0) * 0.30)
                stop_loss_pct *= 1.20
                action_reason = "bull_trend_expansion"
            elif b2b_confirmed:
                # Bear-to-bull confirmed: enter on transition even in bear/box
                buy_multiplier *= 1.05 + (b2b - 0.60) * 0.80
                sell_multiplier *= 0.70
                take_profit_pct *= 1.10
                stop_loss_pct *= 1.10
                entry_allowed = True
                action_reason = "bear_to_bull_trend_entry"
            else:
                entry_allowed = False
                buy_multiplier = 0.0
                sell_multiplier *= 2.20 if market_state == "bear" else 1.55
                take_profit_pct *= 0.60 if market_state == "bear" else 0.78
                stop_loss_pct *= 0.55 if market_state == "bear" else 0.76
                action_reason = f"{market_state}_trend_entry_block"

        # ════════════════════════════════════════════════════════════════════════
        # Rule C – Defensive (improved)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "C":
            if market_state == "bear":
                if b2b_confirmed:
                    # Cautious entry at transition
                    entry_allowed = True
                    buy_multiplier *= 0.48
                    sell_multiplier *= 1.40
                    take_profit_pct *= 0.80
                    stop_loss_pct *= 0.65
                    action_reason = "bear_to_bull_defensive_entry"
                else:
                    entry_allowed = False
                    buy_multiplier = 0.0
                    sell_multiplier *= 2.40
                    take_profit_pct *= 0.58
                    stop_loss_pct *= 0.55
                    action_reason = "bear_defensive_exit"
            elif market_state == "box":
                # Loosened lower-zone: 40% (was 30%)
                lower_zone = box_position is not None and box_position <= 0.40
                transition_zone = b2b_confirmed and box_position is not None and box_position <= 0.55
                entry_allowed = lower_zone or transition_zone
                buy_multiplier *= (0.78 if lower_zone else (0.55 if transition_zone else 0.0))
                sell_multiplier *= (1.45 if lower_zone else (1.70 if transition_zone else 2.10))
                take_profit_pct *= 0.75
                stop_loss_pct *= 0.72
                action_reason = (
                    "box_low_defensive_entry" if lower_zone
                    else ("box_transition_entry" if transition_zone else "box_mid_high_entry_block")
                )
            else:  # bull
                buy_multiplier *= 0.45 + (max(market_pressure, 0.0) * 0.08)
                sell_multiplier *= 1.32
                take_profit_pct *= 0.85
                stop_loss_pct *= 0.74
                action_reason = "bull_defensive_participation"

        # ════════════════════════════════════════════════════════════════════════
        # Rule D – Breakout confirmation (improved)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "D":
            confirmed_breakout = (
                market_state == "bull"
                and market_pressure >= 0.18  # relaxed from 0.20
                and decision.signal.level in {"medium", "strong", "very_strong"}
            )
            transition_breakout = b2b_confirmed and decision.signal.level in {"medium", "strong", "very_strong"}
            box_bottom_entry = (
                market_state == "box"
                and box_position is not None
                and box_position <= 0.35
                and market_pressure >= 0.05
                and decision.signal.level != "weak"
            )
            entry_allowed = confirmed_breakout or transition_breakout or box_bottom_entry
            if confirmed_breakout:
                buy_multiplier *= 1.0 + max(market_pressure, 0.0) * 0.38
                sell_multiplier *= 0.70
                take_profit_pct *= 1.20
                stop_loss_pct *= 0.92
                action_reason = "bull_breakout_confirmed"
            elif transition_breakout:
                buy_multiplier *= 0.88 + (b2b - 0.60) * 0.60
                sell_multiplier *= 0.85
                take_profit_pct *= 1.05
                stop_loss_pct *= 1.00
                action_reason = "transition_breakout_entry"
            elif box_bottom_entry:
                buy_multiplier *= 0.72
                sell_multiplier *= 1.30
                take_profit_pct *= 0.88
                stop_loss_pct *= 0.90
                action_reason = "box_bottom_momentum_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.85
                take_profit_pct *= 0.75
                stop_loss_pct *= 0.90
                action_reason = "breakout_confirmation_required"

        # ════════════════════════════════════════════════════════════════════════
        # Rule E – Box low range (improved)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "E":
            # Loosened lower-zone: 38% (was 25%)
            lower_zone = market_state == "box" and box_position is not None and box_position <= 0.38
            rebound_confirmed = market_pressure >= -0.08 and decision.signal.level != "weak"
            transition_entry = b2b_confirmed and box_position is not None and box_position <= 0.55
            entry_allowed = (lower_zone and rebound_confirmed) or transition_entry
            if lower_zone and rebound_confirmed:
                buy_multiplier *= 0.88
                sell_multiplier *= 1.32
                take_profit_pct *= 0.92
                stop_loss_pct *= 0.84
                action_reason = "box_low_rebound_confirmed"
            elif transition_entry:
                buy_multiplier *= 0.70
                sell_multiplier *= 1.20
                take_profit_pct *= 1.00
                stop_loss_pct *= 0.90
                action_reason = "box_transition_rebound_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.60
                action_reason = "box_low_confirmation_required"

        # ════════════════════════════════════════════════════════════════════════
        # Rule F – Capital preservation (improved)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "F":
            capital_preservation_entry = (
                market_state == "bull"
                and market_pressure >= 0.08  # relaxed from 0.10
                and decision.signal.level in {"strong", "very_strong"}
            )
            transition_entry = (
                b2b_confirmed
                and decision.signal.level in {"medium", "strong", "very_strong"}
                and market_pressure >= -0.05
            )
            box_low_entry = (
                market_state == "box"
                and box_position is not None
                and box_position <= 0.32
                and decision.signal.level in {"medium", "strong", "very_strong"}
            )
            entry_allowed = capital_preservation_entry or transition_entry or box_low_entry
            if capital_preservation_entry:
                buy_multiplier *= 0.78
                sell_multiplier *= 1.22
                take_profit_pct *= 0.94
                stop_loss_pct *= 0.78
                action_reason = "capital_preservation_entry"
            elif transition_entry:
                buy_multiplier *= 0.55 + (b2b - 0.60) * 0.50
                sell_multiplier *= 1.10
                take_profit_pct *= 0.88
                stop_loss_pct *= 0.80
                action_reason = "capital_preservation_transition_entry"
            elif box_low_entry:
                buy_multiplier *= 0.48
                sell_multiplier *= 1.45
                take_profit_pct *= 0.85
                stop_loss_pct *= 0.78
                action_reason = "capital_preservation_box_low_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.30
                action_reason = "capital_preservation_hold"

        # ── Global: volatility penalty ─────────────────────────────────────────
        volatility_penalty = min(max(decision.features.short_volatility / 0.02, 0.0), 1.0)
        if volatility_penalty > 0.5:
            buy_multiplier *= 1.0 - ((volatility_penalty - 0.5) * 0.35)
            sell_multiplier *= 1.0 + ((volatility_penalty - 0.5) * 0.28)
            stop_loss_pct *= 0.88

        # ── Global: weak signal guard ──────────────────────────────────────────
        if decision.signal.level == "weak":
            if variant.key == "B":
                entry_allowed = entry_allowed and market_state == "bull" and market_pressure >= 0.12
                buy_multiplier *= 0.60
            elif variant.key == "C":
                buy_multiplier *= 0.55
            elif variant.key in {"D", "E", "F"}:
                if not b2b_confirmed:
                    entry_allowed = False
                    buy_multiplier = 0.0
            else:
                buy_multiplier *= 0.72

        # ── Apply transition buy boost (stacked on top of per-variant logic) ───
        if entry_allowed and transition_buy_boost > 1.0:
            buy_multiplier *= transition_buy_boost

        # ── Bull→bear forced sell: amplify sell multiplier ─────────────────────
        if forced_sell:
            sell_multiplier *= self.BULL_TO_BEAR_SELL_BOOST
            # Lower take-profit so any remaining profit is banked quickly
            take_profit_pct *= 0.55
            entry_allowed = False
            buy_multiplier = 0.0

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
            bear_to_bull_score=round(b2b, 4),
            bull_to_bear_score=round(bu2be, 4),
            transition_buy_boost=round(transition_buy_boost, 4),
            forced_sell=forced_sell,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Shadow portfolio simulation
    # ──────────────────────────────────────────────────────────────────────────

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
        # High box position exit: use resolved box_position
        box_high_exit = self._resolved_box_high_exit(policy=policy)
        should_exit = (
            profit_pct >= policy.take_profit_pct
            or stop_loss_triggered
            or decision.regime.market_state == "bear"
            or box_high_exit
            or policy.forced_sell  # bull→bear transition forced exit
        )
        if not should_exit:
            return "hold"
        base_sell_ratio = decision.sizing.sell_ratio if decision.sizing.sell_ratio > 0 else 0.35
        # Forced sell: use a higher sell ratio (80% minimum) to clear position
        if policy.forced_sell:
            base_sell_ratio = max(base_sell_ratio, 0.80)
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
            shadow.gross_loss = round(shadow.gross_loss + abs(pnl), 2)
        if stop_loss_triggered:
            shadow.stop_loss_count += 1
        if pnl > 0:
            shadow.win_count += 1
            shadow.gross_profit = round(shadow.gross_profit + pnl, 2)
        return "sell"

    # ──────────────────────────────────────────────────────────────────────────
    # Box position resolution (prefers dynamic range)
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve_box_position(
        self,
        *,
        decision: TradeDecisionResult,
        current_price: float,
        transition: TransitionState,
    ) -> float | None:
        """Return the best available box-position estimate.

        Priority:
        1. Dynamic box position from transition state (history-based) – most stable.
        2. Static box position from regime snapshot (single-tick based) – fallback.
        """
        if transition.dynamic_box_position is not None:
            return transition.dynamic_box_position
        return self._static_box_position(decision=decision, current_price=current_price)

    @staticmethod
    def _resolved_box_high_exit(*, policy: DemoRuleVariantPolicy) -> bool:
        """Trigger exit when price is near the top of the resolved box."""
        return policy.box_position is not None and policy.box_position >= 0.80

    @staticmethod
    def _static_box_position(*, decision: TradeDecisionResult, current_price: float) -> float | None:
        low = decision.regime.box_range_low
        high = decision.regime.box_range_high
        if low is None or high is None or high <= low:
            return None
        return max(min((current_price - low) / (high - low), 1.0), 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Score helpers
    # ──────────────────────────────────────────────────────────────────────────

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
    def _leader_score(item: dict[str, object]) -> tuple[float, float, int]:
        profit_rate = float(item.get("profit_rate") or 0.0)
        trade_count = int(item.get("trade_count") or 0)
        max_drawdown_pct = float(item.get("max_drawdown_pct") or 0.0)
        return profit_rate, -max_drawdown_pct, trade_count

    @staticmethod
    def _candidate_score(item: dict[str, object]) -> tuple[float, float, int]:
        return (
            float(item.get("profit_rate") or 0.0),
            -float(item.get("max_drawdown_pct") or 0.0),
            int(item.get("trade_count") or 0),
        )

    @classmethod
    def _promotion_eligible(cls, item: dict[str, object]) -> bool:
        profit_factor = item.get("profit_factor")
        stop_loss_rate = item.get("stop_loss_rate")
        eligible = (
            float(item.get("profit_rate") or 0.0) > 0.0
            and float(item.get("realized_pnl") or 0.0) > 0.0
            and int(item.get("trade_count") or 0) >= cls.MIN_PROMOTION_TRADES
            and profit_factor is not None
            and float(profit_factor) > 1.0
            and (stop_loss_rate is None or float(stop_loss_rate) <= 0.40)
        )
        item["promotion_eligible"] = eligible
        return eligible

    @staticmethod
    def _leader_reason(leader: dict[str, object]) -> str:
        b2b = float(leader.get("bear_to_bull_score") or 0.0)
        bu2be = float(leader.get("bull_to_bear_score") or 0.0)
        transition_note = ""
        if b2b >= 0.60:
            transition_note = f" (하락→상승 전환 점수: {b2b:.2f})"
        elif bu2be >= 0.60:
            transition_note = f" (상승→하락 전환 점수: {bu2be:.2f})"
        return (
            f"{leader['variant_label']}이 {leader['market_state_label']} 흐름에서 "
            f"현재 수익률 {float(leader['profit_rate']):.2%}로 가장 높습니다.{transition_note} "
            f"적용 사유는 {leader['action_reason']}입니다."
        )

    @classmethod
    def _no_positive_leader_reason(
        cls,
        candidate: dict[str, object],
        applied: dict[str, object] | None,
    ) -> str:
        applied_text = (
            "기존 적용 룰은 없습니다."
            if applied is None
            else f"기존 적용 룰 {applied['variant_label']}을 유지합니다."
        )
        return (
            f"현재 양수 수익과 최소 {cls.MIN_PROMOTION_TRADES}회 청산 조건을 함께 충족한 룰이 없어 "
            f"변경하지 않습니다. 수익률 기준 최고 후보는 {candidate['variant_label']}이며 "
            f"누적 수익률은 {float(candidate['profit_rate']):.2%}입니다. {applied_text}"
        )

    @staticmethod
    def _empty_report() -> dict[str, object]:
        return {
            "leader_key": None,
            "leader_label": None,
            "leader_reason": "현재가가 없어 다중 룰 동시 테스트를 실행하지 못했습니다.",
            "candidate_leader_key": None,
            "candidate_leader_label": None,
            "candidate_leader_profit_rate": None,
            "promotion_eligible": False,
            "selection_changed": False,
            "applied_variant_key": None,
            "applied_variant_label": None,
            "market_state": None,
            "market_state_label": None,
            "bear_to_bull_score": 0.0,
            "bull_to_bear_score": 0.0,
            "bear_to_bull_confirmed": False,
            "bull_to_bear_confirmed": False,
            "dynamic_box_low": None,
            "dynamic_box_high": None,
            "dynamic_box_position": None,
            "results": [],
        }
