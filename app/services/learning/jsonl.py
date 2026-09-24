from __future__ import annotations

import json
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
    # Read backwards so dashboard diagnostics stay proportional to the requested
    # tail instead of the lifetime size of an append-only learning log.
    chunks: list[bytes] = []
    newline_count = 0
    with path.open("rb") as handle:
        position = handle.seek(0, 2)
        while position > 0 and newline_count <= limit:
            chunk_start = max(0, position - 64 * 1024)
            handle.seek(chunk_start)
            chunk = handle.read(position - chunk_start)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
            position = chunk_start

    lines = b"".join(reversed(chunks)).splitlines()[-limit:]
    rows: list[dict[str, Any]] = []
    for raw_line in lines:
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows
