"""Demo rule variants (A – R) with market-state-aware policies.

18-variant simultaneous shadow portfolio testing system.

Variant overview
-----------------
A  안정형    – 기본 신호 + 장세 민감 배수 + 전환 감지, 균형 추적
B  추세형    – 상승장·전환 구간에서만 진입 크기 확대, 익절 폭 넓힘
C  방어형    – 하락장 노출 최소화, 박스권 하단·전환 구간 소량 진입
D  돌파확인형 – 돌파/전환 확인 시에만 진입, 추세 장기 보유
E  박스저점형 – 박스권 하단 반등, 상단 접근 시 빠른 청산
F  자본보전형 – 강한 신호·전환 구간 소량 진입, 낙폭 억제 최우선
G  스캘핑형  – 매우 짧은 익절/손절, 강한 신호에만 소량 고빈도 진입
H  모멘텀형  – 최강 상승 모멘텀 + 압력 공격 진입, 높은 TP 목표
I  분할매수형 – 하락 지속 시 분할 진입, 반등 구간 분할 청산
J  역추세형  – 과매도(box 하단) 반등 특화, 빠른 손절 + 중간 TP
K  변동성형  – 변동성 급등 구간 소량 진입, 빠른 손절 보호
L  하이브리드형– B(추세) + C(방어) 혼합, 장세별 비중 자동 조절
M  돌파추격형 – 상승장 강력 모멘텀 확인 시 빠르게 진입, 단기 추세 극대화
N  역변동성형 – 변동성+박스권 극단 영역 단기 역추세 반등 진입
O  공격추세형 – 상승 확정 시 최대 비중 공격적 진입, 하락 전환 시 강력 청산
P  추세장기형 – 넓은 손절선으로 큰 상승 추세를 길게 보유하여 복리 수익 극대화
Q  변동적응형 – 단기 변동성에 따라 TP/SL을 실시간 조율, 불필요한 청산 방지
R  반등돌파형 – 하락세 진정 및 상승 반전 초입에 공격 진입, 큰 반등 수익 포착

Shared mechanisms
------------------
1. Transition detection (bear→bull / bull→bear) integrated across all variants.
2. Dynamic box range (100-200 tick history) preferred over static single-tick range.
3. Forced sell on bull→bear confirmation; take-profit threshold lowered immediately.
4. Global volatility penalty applied on top of per-variant logic.
5. Bear-to-bull boost (×1.35) stacked on per-variant buy multiplier when confirmed.
6. Early Promotion: on first server start (_applied_variant_key is None),
   MIN_PROMOTION_TRADES is relaxed to 1 to prevent indefinite wait state.
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
    # ── 연속 손절 쿨다운 ─────────────────────────────────────────────────
    consecutive_stop_loss_count: int = 0   # 연속 손절 횟수 (수익 발생 시 리셋)
    cooling_off_ticks_remaining: int = 0   # 남은 쿨다운 틱 수


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

    MIN_PROMOTION_TRADES = 5  # 20→10→5: 하락장에서도 더 빠른 승격 가능

    # Bear-to-bull confirmed → buy multiplier is boosted by this factor
    BEAR_TO_BULL_BUY_BOOST = 1.35
    # Bull-to-bear confirmed → sell multiplier is boosted by this factor
    BULL_TO_BEAR_SELL_BOOST = 1.80

    # 비상 전환 발동 기준: 현재 룰의 손절 횟수가 이 값 이상이고
    # 정상 승격 후보가 없을 때, 최저 낙폭/손절율 룰로 긴급 전환
    # ↓ 2회로 완화: 연속 3회→대형 손실(-50원+) 전에 2회만 되어도 방어 룰 즉시 전환
    EMERGENCY_FALLBACK_STOP_LOSS_COUNT = 2
    # 비상 전환 시 현재 룰보다 낙폭이 이 배율 이하인 룰만 후보로 고려
    EMERGENCY_FALLBACK_MAX_DRAWDOWN_RATIO = 0.80
    # 연속 손절 쿨다운: 연속 N회 손절 시 이 틱 수만큼 신규 매수를 차단
    CONSECUTIVE_STOP_LOSS_COOLDOWN_TRIGGER = 2   # 2회 연속 손절 시 쿨다운 발동
    CONSECUTIVE_STOP_LOSS_COOLDOWN_TICKS = 200   # 약 10분(3초 간격) 쿨다운

    # ── Fallback Leader (전체 음수 시 임시 리더) ────────────────────────────────
    # 정상 승격 조건을 충족하는 룰이 없을 때 최고 성과 룰을 임시 리더로 사용.
    # 이를 통해 NO_POSITIVE_RULE_LEADER_YET로 인한 영구 매매 정지를 방지한다.
    FALLBACK_LEADER_MIN_TRADES = 1     # 리셋 직후 1거래 이상이면 fallback 후보 (신속 선발)
    FALLBACK_LEADER_MAX_SL_RATE = 0.60  # 손절률 60% 이하인 룰만 fallback 후보
    FALLBACK_LEADER_BUY_SCALE = 0.40   # fallback 시 매수 크기 40% 축소 (더 보수적 운용)

    DEFAULT_VARIANTS = (
        DemoRuleVariant(
            key="A",
            label="룰 A 안정형",
            description="기본 신호에 장세 민감 배수와 전환 감지를 더해 균형 있게 추적합니다.",
            buy_multiplier=1.0,
            sell_multiplier=1.0,
            take_profit_pct=0.0150,
            stop_loss_pct=0.0080,
        ),
        DemoRuleVariant(
            key="B",
            label="룰 B 추세형",
            description="상승장 강도와 하락→상승 전환에만 진입을 키우고 추세 지속 시 익절 폭을 넓힙니다.",
            buy_multiplier=1.85,
            sell_multiplier=0.45,
            take_profit_pct=0.0320,
            stop_loss_pct=0.0120,
        ),
        DemoRuleVariant(
            key="C",
            label="룰 C 방어형",
            description="하락장 노출을 빠르게 줄이고 박스권 하단(40%이하)과 전환 구간에서만 작게 진입합니다.",
            buy_multiplier=0.38,
            sell_multiplier=2.0,
            take_profit_pct=0.0100,
            stop_loss_pct=0.0060,
        ),
        DemoRuleVariant(
            key="D",
            label="룰 D 돌파확인형",
            description="전환 확인 또는 상승장 돌파가 모멘텀과 호가로 확인될 때만 진입하고 추세를 길게 보유합니다.",
            buy_multiplier=1.25,
            sell_multiplier=0.7,
            take_profit_pct=0.0250,
            stop_loss_pct=0.0100,
        ),
        DemoRuleVariant(
            key="E",
            label="룰 E 박스저점형",
            description="박스권 하단(38%이하) 반등 또는 전환 구간을 거래하고 상단 접근 시 빠르게 청산합니다.",
            buy_multiplier=0.72,
            sell_multiplier=1.7,
            take_profit_pct=0.0120,
            stop_loss_pct=0.0070,
        ),
        DemoRuleVariant(
            key="F",
            label="룰 F 자본보전형",
            description="강한 상승 신호·전환 구간에서만 작게 진입해 손절 빈도와 낙폭 억제를 우선합니다.",
            buy_multiplier=0.32,
            sell_multiplier=2.2,
            take_profit_pct=0.0180,
            stop_loss_pct=0.0080,
        ),
        DemoRuleVariant(
            key="G",
            label="룰 G 스캘핑형",
            description="중간 이상 신호에 소량 진입하고 수수료를 충분히 넘는 익절선·타이트 손절로 누적 소폭 수익을 노립니다.",
            buy_multiplier=0.70,   # 0.55→0.70: 중간 신호에도 진입 가능하도록 상향
            sell_multiplier=1.50,
            take_profit_pct=0.0120,  # 0.8%→1.2%: 수수료 0.1% 포함 실질 수익 확보
            stop_loss_pct=0.0040,   # 0.5%→0.4%: 더 타이트한 손절로 낙폭 제한
        ),
        DemoRuleVariant(
            key="H",
            label="룰 H 모멘텀형",
            description="최강 상승 모멘텀과 시장 압력이 동시에 높을 때 공격적으로 진입해 큰 추세 수익을 추구합니다.",
            buy_multiplier=2.20,
            sell_multiplier=0.35,
            take_profit_pct=0.0380,
            stop_loss_pct=0.0140,
        ),
        DemoRuleVariant(
            key="I",
            label="룰 I 분할매수형",
            description="하락 지속 구간에서 분할 진입하고 반등·전환 시 분할 청산해 평균 단가를 낮춥니다.",
            buy_multiplier=0.65,
            sell_multiplier=1.35,
            take_profit_pct=0.0140,
            stop_loss_pct=0.0080,
        ),
        DemoRuleVariant(
            key="J",
            label="룰 J 역추세형",
            description="과매도 박스 하단에서 강한 반등을 노리고 빠른 손절로 리스크를 제한합니다.",
            buy_multiplier=0.90,
            sell_multiplier=1.80,
            take_profit_pct=0.0160,
            stop_loss_pct=0.0070,
        ),
        DemoRuleVariant(
            key="K",
            label="룰 K 변동성형",
            description="변동성 급등 구간에서 소량 역방향 진입 후 매우 타이트한 손절 보호로 수익을 추구합니다.",
            buy_multiplier=0.48,
            sell_multiplier=1.95,
            take_profit_pct=0.0110,
            stop_loss_pct=0.0040,   # 0.6%→0.4%: 변동성 구간 손절 더 타이트하게
        ),
        DemoRuleVariant(
            key="L",
            label="룰 L 하이브리드형",
            description="추세형(B)과 방어형(C)을 장세별로 자동 혼합해 상황에 따라 비중을 조절합니다.",
            buy_multiplier=1.10,
            sell_multiplier=1.15,
            take_profit_pct=0.0200,
            stop_loss_pct=0.0090,
        ),
        DemoRuleVariant(
            key="M",
            label="룰 M 돌파추격형",
            description="상승장 강력 모멘텀 확인 시 빠르게 진입하여 단기 상승 추세 수익을 극대화합니다.",
            buy_multiplier=1.50,
            sell_multiplier=0.80,
            take_profit_pct=0.0280,
            stop_loss_pct=0.0110,
        ),
        DemoRuleVariant(
            key="N",
            label="룰 N 역변동성형",
            description="변동성이 높고 가격이 박스권 극단 영역에 도달했을 때 단기 역추세 반등을 노립니다.",
            buy_multiplier=0.60,
            sell_multiplier=1.50,
            take_profit_pct=0.0130,
            stop_loss_pct=0.0080,
        ),
        DemoRuleVariant(
            key="O",
            label="룰 O 공격추세형",
            description="상승 확정 구간에서 가중치를 대폭 늘려 진입하고, 하락 전환 시 강력하게 빠져나옵니다.",
            buy_multiplier=2.00,
            sell_multiplier=0.40,
            take_profit_pct=0.0450,
            stop_loss_pct=0.0160,
        ),
        DemoRuleVariant(
            key="P",
            label="룰 P 추세장기형",
            description="상승 흐름을 넓은 손절선으로 견디며 큰 폭의 추세 이익을 길게 확보합니다.",
            buy_multiplier=2.20,
            sell_multiplier=0.30,
            take_profit_pct=0.0550,
            stop_loss_pct=0.0180,
        ),
        DemoRuleVariant(
            key="Q",
            label="룰 Q 변동적응형",
            description="변동성 크기에 조율해 무리한 손절을 피하고 유연하게 진입 단가를 유지합니다.",
            buy_multiplier=0.85,
            sell_multiplier=1.20,
            take_profit_pct=0.0260,
            stop_loss_pct=0.0120,
        ),
        DemoRuleVariant(
            key="R",
            label="룰 R 반등돌파형",
            description="하락세 진정 및 상승 반전 확정 초입에 강하게 진입해 큰 반등을 취합니다.",
            buy_multiplier=1.70,
            sell_multiplier=0.55,
            take_profit_pct=0.0320,
            stop_loss_pct=0.0100,
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
        # 조기 승격(Early Promotion): 서버 초기 기동 시 적용 룰이 없는 상태면
        # MIN_PROMOTION_TRADES를 1로 완화하여 영구 대기 상태를 방지합니다.
        is_initial_start = self._applied_variant_key is None
        promotable = [
            item for item in results
            if self._promotion_eligible(item, early=is_initial_start)
        ]
        leader = max(promotable, key=self._leader_score) if promotable else None
        
        applied = next(
            (item for item in results if item["variant_key"] == self._applied_variant_key),
            None,
        )
        previous_applied = applied
        # ── 손절 시 즉시 리더 스위칭 (Bypass Promotion) ──
        applied_stop_loss = (
            applied is not None
            and applied.get("last_action") == "sell"
            and applied.get("stop_loss_triggered_this_tick") is True
        )
        forced_switch_active = False
        old_variant_label = applied["variant_label"] if applied else ""

        if applied_stop_loss:
            positive_other_results = [
                r for r in results 
                if r["variant_key"] != applied["variant_key"] 
                and int(r.get("trade_count") or 0) >= 1
                and float(r.get("realized_pnl") or 0.0) > 0.0
            ]
            if positive_other_results:
                new_leader = max(positive_other_results, key=lambda x: float(x.get("profit_rate") or 0.0))
                self._applied_variant_key = str(new_leader["variant_key"])
                applied = new_leader
                forced_switch_active = True
                selection_changed = True
            else:
                selection_changed = leader is not None and leader["variant_key"] != self._applied_variant_key
                if selection_changed:
                    self._applied_variant_key = str(leader["variant_key"])
                    applied = next((item for item in results if item["variant_key"] == self._applied_variant_key), None)
        else:
            selection_changed = leader is not None and leader["variant_key"] != self._applied_variant_key
            if selection_changed:
                self._applied_variant_key = str(leader["variant_key"])
                applied = next((item for item in results if item["variant_key"] == self._applied_variant_key), None)
            elif applied is None and leader is not None:
                # ── 버그 픽스: leader가 존재하는데 applied가 None이면 즉시 leader를 설정 ──
                # (서버 재기동 후 조기 승격이 안 됐거나, 최초 설정 후 리셋된 경우)
                self._applied_variant_key = str(leader["variant_key"])
                applied = next((item for item in results if item["variant_key"] == self._applied_variant_key), None)
                selection_changed = True
        emergency_fallback_active = False
        # ── 비상 전환 (Emergency Fallback) ────────────────────────────────────────
        # 정상 승격 룰 없음 + 현재 룰 손절 과다 → 최저 낙폭 방어 룰로 강제 이탈
        if (
            not selection_changed
            and not forced_switch_active
            and applied is not None
            and not promotable  # 정상 승격 후보가 전혀 없음
            and int(applied.get("stop_loss_count") or 0) >= self.EMERGENCY_FALLBACK_STOP_LOSS_COUNT
        ):
            current_drawdown = float(applied.get("max_drawdown_pct") or 0.0)
            current_sl_rate = float(applied.get("stop_loss_rate") or 0.0)
            # 현재 룰보다 낙폭+손절율이 낮은 룰 중 최적 선택
            safer_candidates = [
                r for r in results
                if r["variant_key"] != applied["variant_key"]
                and float(r.get("max_drawdown_pct") or 0.0) <= current_drawdown * self.EMERGENCY_FALLBACK_MAX_DRAWDOWN_RATIO
                and (r.get("stop_loss_rate") is None or float(r.get("stop_loss_rate") or 0.0) <= current_sl_rate)
            ]
            if safer_candidates:
                # 낙폭 최소 + 손절율 최소 + 수익률 최고 순으로 정렬
                safest = min(
                    safer_candidates,
                    key=lambda r: (
                        float(r.get("max_drawdown_pct") or 0.0),
                        float(r.get("stop_loss_rate") or 0.0),
                        -float(r.get("profit_rate") or 0.0),
                    ),
                )
                old_variant_label = applied["variant_label"]
                self._applied_variant_key = str(safest["variant_key"])
                applied = next((item for item in results if item["variant_key"] == self._applied_variant_key), None)
                selection_changed = True
                emergency_fallback_active = True

        # ── Fallback Leader: 정상 승격 불가 시 최고 성과 룰을 임시 리더로 ─────────
        # NO_POSITIVE_RULE_LEADER_YET 영구 정지 방지.
        # promotable이 없고 applied도 없으면(또는 applied가 None이면) 임시 리더 선발.
        fallback_leader_active = False
        if not promotable and applied is None and not selection_changed:
            # 초기 기동(is_initial_start=True) 시: 섀도 포트폴리오가 모두 0거래
            # → min_trades=0으로 완화하여 즉시 안전한 룰 선발
            # 정상 운용 중: FALLBACK_LEADER_MIN_TRADES(3) 이상 거래한 룰만 후보
            fallback_min_trades = 0 if is_initial_start else self.FALLBACK_LEADER_MIN_TRADES
            fallback_candidates = [
                r for r in results
                if int(r.get("trade_count") or 0) >= fallback_min_trades
                and (
                    r.get("stop_loss_rate") is None
                    or float(r.get("stop_loss_rate") or 0.0) <= self.FALLBACK_LEADER_MAX_SL_RATE
                )
            ]
            if not fallback_candidates:
                # 모든 룰이 손절률 초과 시 손절률 조건 제외하고 재탐색
                fallback_candidates = results  # 최후 수단: 전체 후보
            if fallback_candidates:
                # 초기 기동 시: 낙폭 최소 + 손절률 최소 우선(안전한 룰)
                # 정상 운용 시: 수익률 최고 + 낙폭 최소
                if is_initial_start:
                    fallback_leader = min(
                        fallback_candidates,
                        key=lambda r: (
                            float(r.get("max_drawdown_pct") or 0.0),  # 낙폭 최소 우선
                            float(r.get("stop_loss_rate") or 0.0),    # 손절률 최소 차선
                        ),
                    )
                else:
                    fallback_leader = max(
                        fallback_candidates,
                        key=lambda r: (
                            float(r.get("profit_rate") or -999.0),   # 수익률 최고 우선
                            -float(r.get("max_drawdown_pct") or 0.0),  # 낙폭 최소 차선
                        ),
                    )
                self._applied_variant_key = str(fallback_leader["variant_key"])
                applied = next(
                    (item for item in results if item["variant_key"] == self._applied_variant_key),
                    None,
                )
                selection_changed = True
                fallback_leader_active = True

        selection_type = (
            "stop_loss_forced_switch"
            if forced_switch_active
            else "emergency_fallback"
            if emergency_fallback_active
            else "fallback_leader"             # 신규: 전체 음수 시 임시 리더 모드
            if fallback_leader_active
            else "performance_promotion"
            if selection_changed
            else None
        )
        _report = {
            "leader_key": None if applied is None else applied["variant_key"],
            "leader_label": None if applied is None else applied["variant_label"],
            "leader_reason": (
                f"기존 적용 룰 {old_variant_label}에서 손절이 발생하여, 현재 수익률 {applied['profit_rate']:.2%}로 가장 우수한 {applied['variant_label']}로 즉시 강제 전환(스위칭)되었습니다."
                if forced_switch_active and applied is not None
                else (
                    f"비상 전환(Emergency Fallback): {old_variant_label}에서 손절 과다 발생. "
                    f"최저 낙폭 방어 룰 {applied['variant_label']}(낙폭 {float(applied.get('max_drawdown_pct', 0)):.2%})으로 긴급 전환."
                    if emergency_fallback_active and applied is not None
                    else (
                        f"임시 리더 모드(Fallback Leader): 정상 승격 가능 룰 없음. "
                        f"가장 손실이 적은 {applied['variant_label']}(수익률 {float(applied.get('profit_rate', 0)):.2%})을 "
                        f"임시 리더로 선발. 매수 크기 {int(self.FALLBACK_LEADER_BUY_SCALE*100)}% 축소 적용."
                        if fallback_leader_active and applied is not None
                        else self._leader_reason(leader)
                        if leader is not None
                        else self._no_positive_leader_reason(candidate, applied)
                    )
                )
            ),
            "candidate_leader_key": candidate["variant_key"],
            "candidate_leader_label": candidate["variant_label"],
            "candidate_leader_profit_rate": candidate["profit_rate"],
            "promotion_eligible": applied is not None and not forced_switch_active,
            "selection_changed": selection_changed,
            "selection_type": selection_type,
            "is_fallback_leader": fallback_leader_active,   # 신규: fallback 모드 여부
            "previous_variant_key": (
                None if previous_applied is None else previous_applied["variant_key"]
            ),
            "previous_variant_label": (
                None if previous_applied is None else previous_applied["variant_label"]
            ),
            "previous_variant_profit_rate": (
                None if previous_applied is None else previous_applied["profit_rate"]
            ),
            "applied_variant_key": None if applied is None else applied["variant_key"],
            "applied_variant_label": None if applied is None else applied["variant_label"],
            "applied_variant_profit_rate": (
                None if applied is None else applied["profit_rate"]
            ),
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
        self._last_report = _report  # 일일 요약 등 외부 접근용 캐시
        return _report

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
        available_cash: float = 1_000_000.0,
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
        
        # 룰 배수를 적용한 매수 금액 계산 후 가용 현금(수수료 감안)으로 캡핑
        raw_buy_amount = sizing.buy_amount * policy.buy_multiplier
        max_allowed = available_cash / (1 + self._trading_fee_rate)
        buy_amount = round(min(raw_buy_amount, max_allowed), 1)

        buy_ratio = round(min(sizing.buy_ratio * policy.buy_multiplier, 1.0), 3)
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
        stop_loss_triggered_this_tick = False
        if shadow.asset_balance > 0:
            stop_loss_triggered_this_tick = (
                shadow.avg_buy_price > 0
                and (
                    (current_price - shadow.avg_buy_price) / shadow.avg_buy_price
                    <= -policy.stop_loss_pct
                )
            )
            action = self._maybe_shadow_sell(
                shadow=shadow,
                policy=policy,
                decision=decision,
                current_price=current_price,
            )
            stop_loss_triggered_this_tick = (
                action == "sell" and stop_loss_triggered_this_tick
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
            "stop_loss_triggered_this_tick": stop_loss_triggered_this_tick,
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
                    # 강화: 전환 확정(b2b_confirmed) 없이는 bear 진입 완전 차단
                    # 이전: b2b >= 0.45 (기대만으로 진입) → 손절 반복 원인
                    entry_allowed = False
                    action_reason = "bear_balance_defense"
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

        # ════════════════════════════════════════════════════════════════════════
        # Rule G – Scalping (고빈도 소량, 빠른 익절/손절)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "G":
            strong_signal = decision.signal.level in {"strong", "very_strong"}
            medium_signal = decision.signal.level == "medium"
            bull_scalp = market_state == "bull" and strong_signal and market_pressure >= 0.10
            box_scalp = (
                market_state == "box"
                and box_position is not None
                and box_position <= 0.45
                and (strong_signal or (medium_signal and market_pressure >= 0.08))
            )
            transition_scalp = b2b_confirmed and strong_signal
            entry_allowed = bull_scalp or box_scalp or transition_scalp
            if bull_scalp:
                buy_multiplier *= 0.92
                sell_multiplier *= 1.10
                take_profit_pct *= 0.88  # 빠른 익절
                stop_loss_pct *= 0.82
                action_reason = "scalp_bull_entry"
            elif box_scalp:
                buy_multiplier *= 0.80
                sell_multiplier *= 1.25
                take_profit_pct *= 0.85
                stop_loss_pct *= 0.78
                action_reason = "scalp_box_entry"
            elif transition_scalp:
                buy_multiplier *= 0.85
                sell_multiplier *= 1.15
                take_profit_pct *= 0.90
                stop_loss_pct *= 0.80
                action_reason = "scalp_transition_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.40
                action_reason = "scalp_no_signal"

        # ════════════════════════════════════════════════════════════════════════
        # Rule H – Momentum (최강 모멘텀 공격 추종)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "H":
            high_pressure = market_pressure >= 0.22
            very_strong = decision.signal.level == "very_strong"
            strong_bull = market_state == "bull" and decision.signal.level in {"strong", "very_strong"}
            momentum_entry = strong_bull and high_pressure
            transition_momentum = b2b_confirmed and very_strong and market_pressure >= 0.15
            entry_allowed = momentum_entry or transition_momentum
            if momentum_entry:
                # 압력·신호 강도에 비례한 공격적 배수
                pressure_boost = 1.0 + max(market_pressure - 0.22, 0.0) * 1.80
                buy_multiplier *= 1.30 * pressure_boost
                sell_multiplier *= 0.45
                take_profit_pct *= 1.50 + max(market_pressure - 0.22, 0.0) * 0.80
                stop_loss_pct *= 1.30
                action_reason = "momentum_bull_surge"
            elif transition_momentum:
                boost = 1.0 + (b2b - 0.60) * 1.20
                buy_multiplier *= boost
                sell_multiplier *= 0.55
                take_profit_pct *= 1.30
                stop_loss_pct *= 1.20
                action_reason = "momentum_transition_surge"
            else:
                entry_allowed = False
                buy_multiplier = 0.0
                sell_multiplier *= 2.50 if market_state == "bear" else 1.80
                take_profit_pct *= 0.55
                stop_loss_pct *= 0.60
                action_reason = f"{market_state}_momentum_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule I – Scaling-in (분할매수, 반등 분할청산)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "I":
            # 하락 지속 구간 진입: bear or box 하단
            bear_scale = market_state == "bear" and b2b >= 0.30 and decision.signal.level != "weak"
            box_scale = (
                market_state == "box"
                and box_position is not None
                and box_position <= 0.48
                and market_pressure >= -0.10
                and decision.signal.level != "weak"
            )
            transition_scale = b2b_confirmed and box_position is not None and box_position <= 0.60
            entry_allowed = bear_scale or box_scale or transition_scale
            if bear_scale:
                buy_multiplier *= 0.75  # 분할 소량
                sell_multiplier *= 1.20
                take_profit_pct *= 0.88
                stop_loss_pct *= 0.85
                action_reason = "scale_in_bear"
            elif box_scale:
                buy_multiplier *= 0.85
                sell_multiplier *= 1.28
                take_profit_pct *= 0.92
                stop_loss_pct *= 0.88
                action_reason = "scale_in_box"
            elif transition_scale:
                buy_multiplier *= 0.90
                sell_multiplier *= 1.15
                take_profit_pct *= 1.00
                stop_loss_pct *= 0.92
                action_reason = "scale_in_transition"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.50
                action_reason = "scale_in_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule J – Counter-trend (역추세, 과매도 반등 특화)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "J":
            oversold_bounce = (
                box_position is not None
                and box_position <= 0.28
                and market_pressure >= -0.05
                and decision.signal.level in {"medium", "strong", "very_strong"}
            )
            bear_reversal = (
                market_state == "bear"
                and b2b >= 0.50
                and decision.signal.level in {"medium", "strong", "very_strong"}
            )
            entry_allowed = oversold_bounce or bear_reversal or b2b_confirmed
            if oversold_bounce:
                buy_multiplier *= 1.05
                sell_multiplier *= 1.55
                take_profit_pct *= 0.95  # 중간 TP
                stop_loss_pct *= 0.72  # 빠른 손절
                action_reason = "counter_oversold_bounce"
            elif bear_reversal:
                buy_multiplier *= 0.85
                sell_multiplier *= 1.45
                take_profit_pct *= 0.90
                stop_loss_pct *= 0.78
                action_reason = "counter_bear_reversal"
            elif b2b_confirmed:
                buy_multiplier *= 0.78
                sell_multiplier *= 1.30
                take_profit_pct *= 0.88
                stop_loss_pct *= 0.80
                action_reason = "counter_transition_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.60
                action_reason = "counter_trend_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule K – Volatility (변동성 급등 구간 소량 진입)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "K":
            high_vol = decision.features.short_volatility >= 0.012
            very_high_vol = decision.features.short_volatility >= 0.020
            vol_entry = (
                high_vol
                and market_state in {"bull", "box"}
                and decision.signal.level in {"medium", "strong", "very_strong"}
                and market_pressure >= 0.05
            )
            vol_transition = b2b_confirmed and high_vol and market_pressure >= 0.00
            entry_allowed = vol_entry or vol_transition
            if vol_entry:
                # 변동성 클수록 진입 크기 축소, 손절 강화
                vol_scale = 1.0 - min((decision.features.short_volatility - 0.012) / 0.020, 0.40)
                buy_multiplier *= 0.70 * vol_scale
                sell_multiplier *= 1.55
                take_profit_pct *= 0.88  # 빠른 TP
                stop_loss_pct *= 0.72  # 타이트 손절
                action_reason = "volatility_spike_entry"
            elif vol_transition:
                vol_scale = 1.0 - min((decision.features.short_volatility - 0.012) / 0.025, 0.35)
                buy_multiplier *= 0.62 * vol_scale
                sell_multiplier *= 1.45
                take_profit_pct *= 0.85
                stop_loss_pct *= 0.70
                action_reason = "volatility_transition_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.80 if very_high_vol else 1.40
                action_reason = "volatility_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule L – Hybrid (추세형 B + 방어형 C 자동 혼합)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "L":
            if market_state == "bull":
                # 상승장: 추세형에 가깝게
                pressure_weight = max(market_pressure, 0.0)
                buy_multiplier *= 1.20 + pressure_weight * 0.40
                sell_multiplier *= 0.60
                take_profit_pct *= 1.25 + pressure_weight * 0.20
                stop_loss_pct *= 1.10
                action_reason = "hybrid_bull_trend"
            elif market_state == "bear":
                if b2b_confirmed:
                    buy_multiplier *= 0.55
                    sell_multiplier *= 1.30
                    take_profit_pct *= 0.85
                    stop_loss_pct *= 0.75
                    entry_allowed = True
                    action_reason = "hybrid_bear_transition"
                else:
                    # 하락장: 방어형에 가깝게
                    entry_allowed = b2b >= 0.35
                    buy_multiplier *= 0.35 if b2b >= 0.35 else 0.0
                    sell_multiplier *= 1.85
                    take_profit_pct *= 0.72
                    stop_loss_pct *= 0.68
                    action_reason = "hybrid_bear_defense" if not entry_allowed else "hybrid_bear_watch"
            else:  # box
                # 박스권: 위치에 따라 추세/방어 비중 조절
                lower_zone = box_position is None or box_position <= 0.45
                mid_zone = box_position is not None and 0.45 < box_position <= 0.68
                if lower_zone:
                    buy_multiplier *= 0.85  # 방어형 쪽 비중
                    sell_multiplier *= 1.20
                    take_profit_pct *= 0.90
                    stop_loss_pct *= 0.85
                    action_reason = "hybrid_box_lower_balanced"
                elif mid_zone:
                    buy_multiplier *= 0.60
                    sell_multiplier *= 1.30
                    take_profit_pct *= 0.88
                    stop_loss_pct *= 0.88
                    action_reason = "hybrid_box_mid_balanced"
                else:
                    entry_allowed = False
                    buy_multiplier = 0.0
                    sell_multiplier *= 1.55
                    action_reason = "hybrid_box_upper_block"
                if b2b_confirmed and entry_allowed:
                    buy_multiplier *= 1.15
                    action_reason += "_transition_boost"

        # ════════════════════════════════════════════════════════════════════════
        # Rule M – Breakout Chaser (돌파추격형)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "M":
            strong_momentum = market_state == "bull" and market_pressure >= 0.15 and decision.signal.level in {"strong", "very_strong"}
            entry_allowed = strong_momentum
            if strong_momentum:
                pressure_boost = 1.0 + (market_pressure - 0.15) * 1.20
                buy_multiplier *= 1.25 * pressure_boost
                sell_multiplier *= 0.80
                take_profit_pct *= 1.15
                stop_loss_pct *= 1.05
                action_reason = "breakout_chase_surge"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.50
                action_reason = "breakout_chase_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule N – Contrarian Volatility (역변동성형)
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "N":
            high_vol = decision.features.short_volatility >= 0.010
            extreme_position = box_position is not None and (box_position <= 0.18 or box_position >= 0.82)
            entry_allowed = market_state == "box" and high_vol and extreme_position and decision.signal.level != "weak"
            if entry_allowed:
                is_bottom = box_position <= 0.18
                buy_multiplier *= 0.85 if is_bottom else 0.40
                sell_multiplier *= 1.35 if is_bottom else 1.65
                take_profit_pct *= 0.90
                stop_loss_pct *= 0.80
                action_reason = "contrarian_vol_bottom" if is_bottom else "contrarian_vol_top"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.50
                action_reason = "contrarian_vol_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule O – Aggressive Trend (공격추세형)
        # 실제 market_pressure 분포(평균 0.019, 최대 ~0.05)에 맞춰
        # 임계값을 0.02로 현실화. 상승장에서 weak 신호도 보수적 스케일(0.60x)로 허용.
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "O":
            strong_bull = market_state == "bull" and decision.signal.level in {"medium", "strong", "very_strong"}
            weak_bull = market_state == "bull" and decision.signal.level == "weak"
            # 실제 압력 분포(평균 0.019, 최대 0.05) 기준: 0.02면 약 36% 허용
            entry_allowed = (strong_bull or weak_bull) and market_pressure >= 0.02
            if strong_bull and market_pressure >= 0.02:
                # medium 이상 신호 + 압력 충분: 공격적 진입
                pressure_boost = 1.0 + max(market_pressure - 0.02, 0.0) * 1.50
                buy_multiplier *= 1.45 * pressure_boost
                sell_multiplier *= 0.40
                take_profit_pct *= 1.30
                stop_loss_pct *= 1.10
                action_reason = "aggressive_trend_bull"
            elif weak_bull and market_pressure >= 0.02:
                # weak 신호지만 압력이 양수: 축소 진입 (60% 스케일)
                buy_multiplier *= 0.60
                sell_multiplier *= 0.70
                take_profit_pct *= 0.90
                stop_loss_pct *= 0.95
                action_reason = "aggressive_trend_bull_weak"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 2.00
                action_reason = "aggressive_trend_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule P – Long-term Trend (추세장기형)
        # 넓은 SL로 변동성을 견디며 상승 추세를 길게 보유해 복리 수익을 극대화합니다.
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "P":
            bull_trend = market_state == "bull" and decision.signal.level in {"medium", "strong", "very_strong"}
            transition_entry = b2b_confirmed and decision.signal.level in {"medium", "strong", "very_strong"}
            entry_allowed = bull_trend or transition_entry
            if bull_trend:
                # 압력이 높을수록 더 공격적으로 진입, 넓은 TP/SL 유지
                pressure_boost = 1.0 + max(market_pressure - 0.05, 0.0) * 1.20
                buy_multiplier *= 1.60 * pressure_boost
                sell_multiplier *= 0.35
                take_profit_pct *= 1.35  # 기본 TP 5.5% 유지하여 큰 추세 포착
                stop_loss_pct *= 1.20   # 넓은 SL로 중간 되돌림 버팀
                action_reason = "long_trend_bull_entry"
            elif transition_entry:
                boost = 1.0 + (b2b - 0.60) * 1.00
                buy_multiplier *= 1.20 * boost
                sell_multiplier *= 0.50
                take_profit_pct *= 1.20
                stop_loss_pct *= 1.10
                action_reason = "long_trend_transition_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 2.20 if market_state == "bear" else 1.60
                action_reason = "long_trend_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule Q – Volatility-Adaptive (변동적응형)
        # 단기 변동성에 맞춰 TP/SL을 실시간 조율하여 불필요한 청산을 방지합니다.
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "Q":
            short_vol = decision.features.short_volatility
            # 변동성이 낮을수록 더 적극적, 높을수록 방어적
            vol_adjustment = max(1.0 - (short_vol / 0.04), 0.50)  # 0.50 ~ 1.0 범위
            vol_inverse = min(1.0 + (short_vol / 0.04), 1.80)     # 1.0 ~ 1.8 범위

            bull_entry = market_state == "bull" and decision.signal.level in {"medium", "strong", "very_strong"}
            box_entry = (
                market_state == "box"
                and box_position is not None
                and box_position <= 0.50
                and decision.signal.level != "weak"
            )
            transition_entry = b2b_confirmed and market_pressure >= -0.05
            entry_allowed = bull_entry or box_entry or transition_entry

            if bull_entry:
                buy_multiplier *= 1.05 * vol_adjustment  # 변동성 높으면 진입 축소
                sell_multiplier *= 1.00
                take_profit_pct *= vol_inverse            # 변동성 높으면 TP 확대 (빠져나오기)
                stop_loss_pct *= vol_inverse              # 변동성 높으면 SL 확대 (휩소 방지)
                action_reason = "vol_adaptive_bull_entry"
            elif box_entry:
                buy_multiplier *= 0.90 * vol_adjustment
                sell_multiplier *= 1.15
                take_profit_pct *= vol_inverse
                stop_loss_pct *= vol_inverse
                action_reason = "vol_adaptive_box_entry"
            elif transition_entry:
                buy_multiplier *= 0.80 * vol_adjustment
                sell_multiplier *= 1.10
                take_profit_pct *= vol_inverse
                stop_loss_pct *= vol_inverse
                action_reason = "vol_adaptive_transition_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 1.60 if market_state == "bear" else 1.20
                action_reason = "vol_adaptive_hold"

        # ════════════════════════════════════════════════════════════════════════
        # Rule R – Rebound Breakout (반등돌파형)
        # 하락세 진정 및 상승 반전 초입에 공격적으로 진입하여 큰 반등 수익을 포착합니다.
        # ════════════════════════════════════════════════════════════════════════
        elif variant.key == "R":
            # 하락→상승 전환 확인이 핵심 조건
            reversal_confirmed = b2b_confirmed and decision.signal.level in {"medium", "strong", "very_strong"}
            # 박스 하단 반등: 극단 하단(30% 이하)에서 반등 신호
            box_reversal = (
                market_state == "box"
                and box_position is not None
                and box_position <= 0.30
                and market_pressure >= 0.00
                and decision.signal.level in {"medium", "strong", "very_strong"}
            )
            # bear 시장에서 전환 임박 (b2b 점수 높을 때)
            bear_reversal = (
                market_state == "bear"
                and b2b >= 0.55
                and decision.signal.level in {"strong", "very_strong"}
            )
            entry_allowed = reversal_confirmed or box_reversal or bear_reversal

            if reversal_confirmed:
                # 전환 확인 시 가장 공격적으로 진입
                boost = 1.0 + (b2b - 0.60) * 1.50
                buy_multiplier *= 1.80 * boost
                sell_multiplier *= 0.45
                take_profit_pct *= 1.25  # 반등의 큰 폭을 길게 가져감
                stop_loss_pct *= 1.05
                action_reason = "reversal_breakout_confirmed"
            elif box_reversal:
                buy_multiplier *= 1.40
                sell_multiplier *= 0.65
                take_profit_pct *= 1.10
                stop_loss_pct *= 0.95
                action_reason = "reversal_box_bottom_entry"
            elif bear_reversal:
                buy_multiplier *= 1.20
                sell_multiplier *= 0.70
                take_profit_pct *= 1.15
                stop_loss_pct *= 1.00
                action_reason = "reversal_bear_bottom_entry"
            else:
                buy_multiplier = 0.0
                sell_multiplier *= 2.00 if market_state == "bear" else 1.50
                action_reason = "reversal_hold"

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
            if variant.key == "O":
                sell_multiplier *= 2.50
            else:
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
        # ── 연속 손절 쿨다운: 쿨다운 남아있으면 신규 매수 차단 ────────────
        if shadow.cooling_off_ticks_remaining > 0:
            shadow.cooling_off_ticks_remaining = max(shadow.cooling_off_ticks_remaining - 1, 0)
            return "hold"
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
        # ── 하락장 즘시 전량 매도: bear 진입 시 최소 80% 이상 신속 철수 ─────
        is_bear_market = decision.regime.market_state == "bear"
        should_exit = (
            profit_pct >= policy.take_profit_pct
            or stop_loss_triggered
            or is_bear_market
            or box_high_exit
            or policy.forced_sell  # bull→bear transition forced exit
        )
        if not should_exit:
            return "hold"
        base_sell_ratio = decision.sizing.sell_ratio if decision.sizing.sell_ratio > 0 else 0.35
        # Forced sell / bear market: use a higher sell ratio (80% minimum) to clear position
        if policy.forced_sell or is_bear_market:
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
            # ── 연속 손절 카운터 업데이트 ─────────────────────────────────
            shadow.consecutive_stop_loss_count += 1
            if shadow.consecutive_stop_loss_count >= self.CONSECUTIVE_STOP_LOSS_COOLDOWN_TRIGGER:
                shadow.cooling_off_ticks_remaining = self.CONSECUTIVE_STOP_LOSS_COOLDOWN_TICKS
        if pnl > 0:
            shadow.win_count += 1
            shadow.gross_profit = round(shadow.gross_profit + pnl, 2)
            # ── 수익 발생 시 연속 손절 카운터 리셋 ──────────────────────
            shadow.consecutive_stop_loss_count = 0
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
    def _promotion_eligible(cls, item: dict[str, object], *, early: bool = False) -> bool:
        """승격 조건 평가.

        Args:
            item: 섀도 테스트 결과 딕셔너리.
            early: True이면 서버 초기 기동(최초 룰 미적용) 상태로, 최소 거래 횟수를
                   ``MIN_PROMOTION_TRADES`` 대신 ``1``로 완화한 조기 승격 모드를 사용합니다.
        """
        min_trades = 1 if early else cls.MIN_PROMOTION_TRADES
        profit_factor = item.get("profit_factor")
        stop_loss_rate = item.get("stop_loss_rate")
        eligible = (
            float(item.get("profit_rate") or 0.0) > 0.0
            and float(item.get("realized_pnl") or 0.0) > 0.0
            and int(item.get("trade_count") or 0) >= min_trades
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
            "selection_type": None,
            "previous_variant_key": None,
            "previous_variant_label": None,
            "previous_variant_profit_rate": None,
            "applied_variant_key": None,
            "applied_variant_label": None,
            "applied_variant_profit_rate": None,
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
