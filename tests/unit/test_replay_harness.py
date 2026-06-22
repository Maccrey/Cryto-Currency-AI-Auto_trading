from __future__ import annotations

import json
from pathlib import Path

from app.services.replay.harness import ReplayHarness
from app.services.replay.loader import ReplayFixtureLoader, ReplayTick


def test_replay_harness_replays_fixture_and_produces_signal_results() -> None:
    fixture_path = Path("fixtures/replay_ticks.json")
    loader = ReplayFixtureLoader()
    harness = ReplayHarness()

    results = harness.run(loader.load(fixture_path))

    assert len(results) == 2
    assert results[0].timestamp == "2026-04-18T09:00:02+09:00"
    assert results[0].signal_level == "medium"
    assert round(results[0].signal_score, 2) == 0.53
    assert results[1].timestamp == "2026-04-18T09:00:03+09:00"
    assert results[1].signal_level == "strong"
    assert round(results[1].signal_score, 2) == 0.71
    summary = harness.summarize(results)
    assert summary.signal_count == 2
    assert summary.profit_guard_status == "passed"


def test_replay_fixture_loader_reads_ticks_from_json() -> None:
    fixture_path = Path("fixtures/replay_ticks.json")
    loader = ReplayFixtureLoader()

    ticks = loader.load(fixture_path)

    assert len(ticks) == 4
    assert ticks[0].price == 800.0
    assert ticks[-1].orderbook_imbalance == 0.38


def test_replay_harness_deducts_round_trip_fees() -> None:
    ticks = [
        ReplayTick(
            timestamp=f"2026-01-01T00:00:0{index}+09:00",
            price=price,
            traded_value=1_000_000.0,
            spread_bps=5.0,
            orderbook_imbalance=0.3,
            liquidity_score=0.9,
            regime_score=0.8,
        )
        for index, price in enumerate((100.0, 101.0, 102.0, 102.0))
    ]

    fee_results = ReplayHarness(
        initial_cash=100_000.0,
        trading_fee_rate=0.0005,
    ).run(ticks)
    zero_fee_results = ReplayHarness(
        initial_cash=100_000.0,
        trading_fee_rate=0.0,
    ).run(ticks)

    assert fee_results
    assert fee_results[-1].equity < zero_fee_results[-1].equity


def test_replay_loader_reads_market_observation_jsonl(tmp_path: Path) -> None:
    observation_path = tmp_path / "market-observations.jsonl"
    observation_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "recorded_at": "2026-05-22T09:00:00+09:00",
                        "trade_price": 800.0,
                        "traded_value": 1000000.0,
                        "spread_bps": 8.0,
                        "orderbook_imbalance": 0.2,
                        "liquidity_score": 0.9,
                        "regime_score": 0.7,
                    },
                ),
            ],
        ),
        encoding="utf-8",
    )

    ticks = ReplayFixtureLoader().load_market_observations(observation_path)

    assert len(ticks) == 1
    assert ticks[0].timestamp == "2026-05-22T09:00:00+09:00"
    assert ticks[0].price == 800.0
