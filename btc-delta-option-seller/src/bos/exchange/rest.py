from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, TypeVar

import httpx
from pydantic import TypeAdapter

from bos.config import ExchangeSettings
from bos.exchange.models import ApiEnvelope, DeltaApiError
from bos.exchange.signing import canonical_json, canonical_query, sign_rest

T = TypeVar("T")


class DeltaRestClient:
    def __init__(
        self, settings: ExchangeSettings, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.rest_url,
            timeout=settings.request_timeout_seconds,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": settings.user_agent},
        )

    async def __aenter__(self) -> DeltaRestClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        response_type: Any,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        authenticated: bool = False,
    ) -> Any:
        envelope = await self.request_envelope(
            method,
            path,
            response_type,
            params=params,
            json_body=json_body,
            authenticated=authenticated,
        )
        return envelope.result

    async def request_envelope(
        self,
        method: str,
        path: str,
        response_type: Any,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        authenticated: bool = False,
    ) -> ApiEnvelope[Any]:
        query = canonical_query(params)
        body = canonical_json(json_body)
        headers: dict[str, str] = {}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            key = self.settings.api_key
            secret = self.settings.api_secret
            if key is None or secret is None:
                raise RuntimeError(
                    "Authenticated request requires environment-provided credentials"
                )
            timestamp = str(int(time.time()))
            headers.update(
                {
                    "api-key": key.get_secret_value(),
                    "timestamp": timestamp,
                    "signature": sign_rest(
                        secret.get_secret_value(), method, timestamp, path, query, body
                    ),
                }
            )
        response = await self._client.request(
            method, f"{path}?{query}" if query else path, content=body or None, headers=headers
        )
        payload = response.json()
        if response.is_error or not payload.get("success", False):
            error = payload.get("error") or {}
            raise DeltaApiError(
                response.status_code,
                str(error.get("code", "unknown")),
                str(error.get("message", response.reason_phrase)),
            )
        return TypeAdapter(ApiEnvelope[response_type]).validate_python(payload)
