from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import AsyncIterator, Iterable
from typing import Any

import websockets

from bos.config import ExchangeSettings
from bos.exchange.signing import sign_websocket


class DeltaPublicWebSocket:
    def __init__(self, settings: ExchangeSettings) -> None:
        self.settings = settings
        self._subscriptions: list[dict[str, Any]] = []

    def subscribe_message(self, channels: Iterable[dict[str, Any]]) -> dict[str, Any]:
        channel_list = list(channels)
        self._subscriptions = channel_list
        return {"type": "subscribe", "payload": {"channels": channel_list}}

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        delay = self.settings.reconnect_initial_seconds
        while True:
            try:
                async with websockets.connect(
                    self.settings.public_ws_url, ping_interval=20, ping_timeout=20
                ) as socket:
                    delay = self.settings.reconnect_initial_seconds
                    await socket.send(json.dumps({"type": "enable_heartbeat"}))
                    if self._subscriptions:
                        await socket.send(json.dumps(self.subscribe_message(self._subscriptions)))
                    async for raw in socket:
                        yield json.loads(raw)
            except asyncio.CancelledError:
                raise
            except (OSError, websockets.WebSocketException):
                await asyncio.sleep(delay + random.uniform(0, delay * 0.1))
                delay = min(delay * 2, self.settings.reconnect_max_seconds)


class DeltaPrivateWebSocket:
    def __init__(self, settings: ExchangeSettings) -> None:
        self.settings = settings
        self._subscriptions: list[dict[str, Any]] = []

    def authentication_message(self, timestamp: int | None = None) -> dict[str, Any]:
        key = self.settings.api_key
        secret = self.settings.api_secret
        if key is None or secret is None:
            raise RuntimeError("Private WebSocket requires environment-provided credentials")
        value = timestamp if timestamp is not None else int(time.time())
        stamp = str(value)
        return {
            "type": "key-auth",
            "payload": {
                "api-key": key.get_secret_value(),
                "timestamp": value,
                "signature": sign_websocket(secret.get_secret_value(), stamp),
            },
        }

    def subscribe_message(self, channels: Iterable[dict[str, Any]]) -> dict[str, Any]:
        channel_list = list(channels)
        self._subscriptions = channel_list
        return {"type": "subscribe", "payload": {"channels": channel_list}}

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        delay = self.settings.reconnect_initial_seconds
        while True:
            try:
                async with websockets.connect(
                    self.settings.private_ws_url, ping_interval=20, ping_timeout=20
                ) as socket:
                    delay = self.settings.reconnect_initial_seconds
                    await socket.send(json.dumps({"type": "enable_heartbeat"}))
                    await socket.send(json.dumps(self.authentication_message()))
                    authenticated = False
                    async for raw in socket:
                        event: dict[str, Any] = json.loads(raw)
                        if event.get("type") == "key-auth":
                            if not event.get("success", False):
                                status = event.get("status")
                                raise RuntimeError(
                                    f"Private WebSocket authentication failed: {status}"
                                )
                            authenticated = True
                            if self._subscriptions:
                                await socket.send(
                                    json.dumps(self.subscribe_message(self._subscriptions))
                                )
                        elif authenticated:
                            yield event
            except asyncio.CancelledError:
                raise
            except RuntimeError:
                raise
            except (OSError, websockets.WebSocketException):
                await asyncio.sleep(delay + random.uniform(0, delay * 0.1))
                delay = min(delay * 2, self.settings.reconnect_max_seconds)
