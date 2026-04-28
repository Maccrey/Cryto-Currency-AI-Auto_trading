from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.integrations.upbit.auth import UpbitAuthSigner


class UpbitRestClient:
    """Thin REST client that separates signing from transport concerns."""

    def __init__(
        self,
        *,
        base_url: str,
        auth_signer: UpbitAuthSigner,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._auth_signer = auth_signer
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=timeout,
        )

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        response = self._client.get(
            path,
            params=params,
            headers={
                "Authorization": self._auth_signer.build_authorization_header(params=params),
            },
        )
        response.raise_for_status()
        return response.json()

    def post(
        self,
        path: str,
        *,
        json_payload: Mapping[str, Any] | None = None,
    ) -> Any:
        response = self._client.post(
            path,
            json=json_payload,
            headers={
                "Authorization": self._auth_signer.build_authorization_header(
                    params=json_payload,
                ),
            },
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
