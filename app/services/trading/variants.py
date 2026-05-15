from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from app.services.learning.service import LearningEvent
from app.services.trading.decision import TradeDecisionResult


@dataclass(frozen=True)
class DemoRuleVariant:
    key: str
    label: str
    description: str
    buy_multiplier: float
    sell_multiplier: float

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DemoRuleVariantScore:
    variant: DemoRuleVariant
    score: float
    expected_return_hint: float
    reason: str

    def to_payload(self) -> dict[str, object]:
        return {
            "variant": self.variant.to_payload(),
            "score": round(self.score, 4),
            "expected_return_hint": round(self.expected_return_hint, 4),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DemoRuleVariantSelection:
    selected: DemoRuleVariant
    scores: list[DemoRuleVariantScore]
    reason: str

    def to_payload(self) -> dict[str, object]:
        return {
            "selected_key": self.selected.key,
            "selected_label": self.selected.label,
            "reason": self.reason,
            "scores": [score.to_payload() for score in self.scores],
        }


class DemoRuleVariantSelector:
    """Select an A/B/C rule candidate for demo-only shadow learning."""

    DEFAULT_VARIANTS = (
        DemoRuleVariant(
            key="A",
            label="룰 A 안정형",
            description="기본 신호를 그대로 쓰고 과열 구간에서 무리하지 않습니다.",
            buy_multiplier=1.0,
            sell_multiplier=1.0,
        ),
        DemoRuleVariant(
            key="B",
            label="룰 B 추세형",
            description="상승장과 강한 신호에서 주문 크기를 조금 키웁니다.",
            buy_multiplier=1.12,
            sell_multiplier=0.88,
        ),
        DemoRuleVariant(
            key="C",
            label="룰 C 방어형",
            description="하락장과 박스권에서 보수적으로 진입하고 매도 대응을 빠르게 합니다.",
            buy_multiplier=0.78,
            sell_multiplier=1.18,
        ),
    )

    def __init__(self, variants: Iterable[DemoRuleVariant] | None = None) -> None:
        self._variants = tuple(variants or self.DEFAULT_VARIANTS)

    def select(
        self,
        *,
        decision: TradeDecisionResult,
        recent_events: Iterable[LearningEvent],
    ) -> DemoRuleVariantSelection:
        scores = [
            self._score_variant(variant, decision=decision, recent_events=recent_events)
            for variant in self._variants
        ]
        selected_score = max(scores, key=lambda item: (item.score, item.variant.key == "A"))
        reason = (
            f"{selected_score.variant.label} 선택: "
            f"{selected_score.reason}, 기대수익 힌트 {selected_score.expected_return_hint:.2%}"
        )
        return DemoRuleVariantSelection(
            selected=selected_score.variant,
            scores=scores,
            reason=reason,
        )

    def _score_variant(
        self,
        variant: DemoRuleVariant,
        *,
        decision: TradeDecisionResult,
        recent_events: Iterable[LearningEvent],
    ) -> DemoRuleVariantScore:
        base = float(decision.signal.score)
        market_bonus = self._market_bonus(variant.key, decision.regime.market_state)
        signal_bonus = self._signal_bonus(variant.key, decision.signal.level)
        history_bonus = self._history_bonus(variant.key, recent_events)
        expected_return_hint = max(
            (base * 0.006) + market_bonus + signal_bonus + history_bonus,
            -0.02,
        )
        score = base + (market_bonus * 12) + (signal_bonus * 10) + (history_bonus * 8)
        reason = self._reason_for(variant.key, decision.regime.market_state, decision.signal.level, history_bonus)
        return DemoRuleVariantScore(
            variant=variant,
            score=score,
            expected_return_hint=expected_return_hint,
            reason=reason,
        )

    @staticmethod
    def _market_bonus(variant_key: str, market_state: str) -> float:
        bonuses = {
            "A": {"box": 0.0016, "bull": 0.0005, "bear": 0.0008},
            "B": {"box": -0.0004, "bull": 0.0025, "bear": -0.0018},
            "C": {"box": 0.0011, "bull": -0.0002, "bear": 0.0022},
        }
        return bonuses.get(variant_key, {}).get(market_state, 0.0)

    @staticmethod
    def _signal_bonus(variant_key: str, signal_level: str) -> float:
        if variant_key == "B" and signal_level in {"strong", "very_strong"}:
            return 0.0015
        if variant_key == "C" and signal_level == "weak":
            return 0.0008
        if variant_key == "A" and signal_level == "medium":
            return 0.0006
        return 0.0

    @staticmethod
    def _history_bonus(variant_key: str, recent_events: Iterable[LearningEvent]) -> float:
        bonus = 0.0
        for event in recent_events:
            if event.event_name not in {"auto_trade_cycle", "rule_variant_result", "position_exit_completed"}:
                continue
            payload = event.payload
            if payload.get("rule_variant_key") != variant_key:
                continue
            pnl = payload.get("realized_pnl", payload.get("pnl"))
            if isinstance(pnl, (int, float)):
                bonus += max(min(float(pnl) / 100_000, 0.006), -0.006)
            if payload.get("status") == "filled":
                bonus += 0.0004
            if payload.get("reason") in {"DEMO_CASH_LIMIT", "AUTO_MIN_SIGNAL_LEVEL"}:
                bonus -= 0.0002
            profit_hint = payload.get("rule_variant_expected_return_hint")
            if isinstance(profit_hint, (int, float)):
                bonus += max(min(float(profit_hint), 0.01), -0.01) * 0.08
        return max(min(bonus, 0.004), -0.004)

    @staticmethod
    def _reason_for(variant_key: str, market_state: str, signal_level: str, history_bonus: float) -> str:
        market_labels = {"bull": "상승장", "bear": "하락장", "box": "박스권"}
        if variant_key == "B":
            core = "추세 추종 점수가 높음"
        elif variant_key == "C":
            core = "방어적 대응 점수가 높음"
        else:
            core = "기본 안정 점수가 높음"
        history = "최근 데모 학습 결과 반영" if abs(history_bonus) > 0.0001 else "최근 데모 표본 부족"
        return f"{market_labels.get(market_state, market_state)} / {signal_level} 신호 / {core} / {history}"
