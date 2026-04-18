from __future__ import annotations

import hashlib
from urllib.parse import urlencode, unquote

import jwt
import pytest

from app.integrations.upbit.auth import UpbitAuthSigner


def test_query_params_require_query_hash() -> None:
    signer = UpbitAuthSigner(access_key="access", secret_key="secret")

    header = signer.build_authorization_header(
        params={"market": "KRW-XRP", "states[]": ["wait", "watch"]},
    )

    token = header.removeprefix("Bearer ")
    payload = jwt.decode(token, "secret", algorithms=["HS512"])
    expected_query = unquote(
        urlencode({"market": "KRW-XRP", "states[]": ["wait", "watch"]}, doseq=True),
    )

    assert payload["access_key"] == "access"
    assert payload["query_hash_alg"] == "SHA512"
    assert payload["query_hash"] == hashlib.sha512(expected_query.encode()).hexdigest()


def test_query_hash_missing_for_params_is_rejected() -> None:
    signer = UpbitAuthSigner(access_key="access", secret_key="secret")

    with pytest.raises(ValueError, match="query_hash"):
        signer.build_payload(params={"market": "KRW-XRP"}, include_query_hash=False)


def test_empty_params_do_not_require_query_hash() -> None:
    signer = UpbitAuthSigner(access_key="access", secret_key="secret")

    payload = signer.build_payload(params=None)

    assert "query_hash" not in payload
    assert "query_hash_alg" not in payload

