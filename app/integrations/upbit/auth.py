from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode, unquote

import jwt


class UpbitAuthSigner:
    """Generate Upbit-compatible JWT authorization headers."""

    def __init__(self, access_key: str, secret_key: str) -> None:
        self.access_key = access_key
        self.secret_key = secret_key

    def build_authorization_header(
        self,
        params: Mapping[str, Any] | None = None,
    ) -> str:
        payload = self.build_payload(params=params)
        token = jwt.encode(payload, self.secret_key, algorithm="HS512")
        return f"Bearer {token}"

    def build_payload(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        include_query_hash: bool = True,
    ) -> dict[str, str]:
        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }

        query_string = _build_query_string(params)
        if query_string:
            if not include_query_hash:
                raise ValueError("query_hash is required when params are present")
            payload["query_hash"] = hashlib.sha512(query_string.encode()).hexdigest()
            payload["query_hash_alg"] = "SHA512"

        return payload


def _build_query_string(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""

    normalized: list[tuple[str, Any]] = []
    for key, value in params.items():
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                normalized.append((key, item))
            continue
        normalized.append((key, value))

    return unquote(urlencode(normalized, doseq=True))

