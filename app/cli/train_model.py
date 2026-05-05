from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.learning.offline_trainer import (
    OfflineModelTrainer,
    OfflineTrainingConfig,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run gated offline TensorFlow training from learning logs.",
    )
    parser.add_argument("--log-dir", default="./logs/learning/scalping")
    parser.add_argument("--report-dir", default="./data/learning/model-reports")
    parser.add_argument("--min-total-events", type=int, default=10_000)
    parser.add_argument("--min-signal-events", type=int, default=2_000)
    parser.add_argument("--min-fill-events", type=int, default=300)
    parser.add_argument("--min-exit-events", type=int, default=100)
    parser.add_argument("--min-blocked-cycles", type=int, default=300)
    parser.add_argument(
        "--skip-tensorflow-check",
        action="store_true",
        help="Run gates and write a shadow report without requiring tensorflow import.",
    )
    args = parser.parse_args(argv)

    report = OfflineModelTrainer(
        config=OfflineTrainingConfig(
            min_total_events=args.min_total_events,
            min_signal_events=args.min_signal_events,
            min_fill_events=args.min_fill_events,
            min_exit_events=args.min_exit_events,
            min_blocked_cycles=args.min_blocked_cycles,
            require_tensorflow=not args.skip_tensorflow_check,
        ),
    ).run(
        log_dir=Path(args.log_dir),
        report_dir=Path(args.report_dir),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "trained" else 2


if __name__ == "__main__":
    raise SystemExit(main())
