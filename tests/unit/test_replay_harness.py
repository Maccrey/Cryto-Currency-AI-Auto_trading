from __future__ import annotations

from pathlib import Path

from app.services.replay.harness import ReplayHarness
from app.services.replay.loader import ReplayFixtureLoader


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


def test_replay_fixture_loader_reads_ticks_from_json() -> None:
    fixture_path = Path("fixtures/replay_ticks.json")
    loader = ReplayFixtureLoader()

    ticks = loader.load(fixture_path)

    assert len(ticks) == 4
    assert ticks[0].price == 800.0
    assert ticks[-1].orderbook_imbalance == 0.38
