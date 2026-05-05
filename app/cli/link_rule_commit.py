from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from app.services.rules.review import RuleReviewConfig, RuleReviewService


def _current_git_commit_hash() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Link the current Git commit hash to a rule proposal history ledger.",
    )
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--learning-log-dir", default="./logs/learning/scalping")
    parser.add_argument("--market", default="KRW-XRP")
    parser.add_argument("--trade-coin", default="XRP")
    parser.add_argument("--trading-mode", default="demo", choices=["demo", "live"])
    parser.add_argument("--commit-hash", default="")
    args = parser.parse_args(argv)

    commit_hash = args.commit_hash.strip() or _current_git_commit_hash()
    service = RuleReviewService(
        market=args.market,
        trade_coin=args.trade_coin,
        trading_mode=args.trading_mode,
        learning_log_dir=Path(args.learning_log_dir),
        config=RuleReviewConfig(
            enabled=True,
            window_days=14,
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )
    result = service.attach_commit_hash(
        args.proposal_id,
        commit_hash=commit_hash,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["proposal"].get("commit_hash") == commit_hash else 2


if __name__ == "__main__":
    raise SystemExit(main())
