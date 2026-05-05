import json
from pathlib import Path

from app.cli.link_rule_commit import main
from app.services.rules.review import RuleReviewConfig, RuleReviewService


def test_link_rule_commit_cli_appends_commit_linked_event(tmp_path: Path, capsys) -> None:
    service = RuleReviewService(
        market="KRW-BTC",
        trade_coin="BTC",
        trading_mode="demo",
        learning_log_dir=tmp_path,
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
    proposal = service.create_proposal()["proposal"]

    exit_code = main(
        [
            "--proposal-id",
            str(proposal["id"]),
            "--learning-log-dir",
            str(tmp_path),
            "--market",
            "KRW-BTC",
            "--trade-coin",
            "BTC",
            "--commit-hash",
            "abc1234",
        ],
    )

    output = json.loads(capsys.readouterr().out)
    rows = [
        json.loads(line)
        for line in (tmp_path / "rule-change-history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert exit_code == 0
    assert output["proposal"]["commit_hash"] == "abc1234"
    assert rows[-1]["event_type"] == "commit_linked"
    assert rows[-1]["trade_coin"] == "BTC"
    assert rows[-1]["commit_hash"] == "abc1234"
