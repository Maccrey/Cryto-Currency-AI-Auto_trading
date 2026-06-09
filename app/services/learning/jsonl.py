from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Iterator


def iter_jsonl_objects(path: Path) -> Iterator[dict[str, Any]]:
    """Yield valid JSON object rows without loading the whole JSONL file."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def tail_jsonl_objects(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=limit)
    for payload in iter_jsonl_objects(path):
        rows.append(payload)
    return list(rows)
