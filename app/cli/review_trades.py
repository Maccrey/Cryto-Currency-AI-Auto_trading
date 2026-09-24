"""Read-only, fee-aware review of recorded fills (no exchange requests)."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def review(path: Path) -> dict:
    counts = Counter()
    groups = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    quantity = cost = realized = fees = 0.0
    first = last = None
    entry_level = "unknown"
    unmatched = 0
    for line in path.open(encoding="utf-8"):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            counts["invalid_json"] += 1
            continue
        first = first or row.get("recorded_at")
        last = row.get("recorded_at")
        event, p = row.get("event_name"), row.get("payload", {})
        counts[event] += 1
        if event == "position_opened":
            entry_level = p.get("signal_level", "unknown")
        if event != "fill_result":
            continue
        q, price, fee = (float(p.get(k, 0)) for k in ("filled_quantity", "filled_price", "fee"))
        fees += fee
        if p.get("side") == "buy":
            quantity += q
            cost += q * price + fee
            counts["buys"] += 1
        elif p.get("side") == "sell":
            counts["sells"] += 1
            if q > quantity + 1e-6 or quantity <= 0:
                unmatched += 1
                continue
            basis = cost * min(q / quantity, 1)
            pnl = q * price - fee - basis
            realized += pnl
            quantity = max(0, quantity - q)
            cost = max(0, cost - basis)
            key = f"{entry_level}/{'stop' if p.get('is_stop_loss') else 'regular'}"
            groups[key]["count"] += 1
            groups[key]["pnl"] += pnl
            counts["profitable_sells" if pnl > 0 else "losing_sells"] += 1
    return {"path": str(path), "first": first, "last": last,
            "counts": dict(counts), "realized_pnl": round(realized, 2),
            "fees": round(fees, 2), "remaining_quantity": quantity,
            "remaining_cost": round(cost, 2), "unmatched_sells": unmatched,
            "groups": dict(groups)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    print(json.dumps(review(parser.parse_args().path), ensure_ascii=False, indent=2))
