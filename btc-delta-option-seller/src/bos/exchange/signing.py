from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode


def canonical_query(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""
    pairs = [(key, value) for key, value in params.items() if value is not None]
    return urlencode(pairs, doseq=True)


def canonical_json(payload: Any | None) -> str:
    if payload is None:
        return ""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def sign_rest(
    secret: str, method: str, timestamp: str, path: str, query: str = "", body: str = ""
) -> str:
    suffix = f"?{query}" if query else ""
    message = f"{method.upper()}{timestamp}{path}{suffix}{body}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def sign_websocket(secret: str, timestamp: str) -> str:
    return sign_rest(secret, "GET", timestamp, "/live")
