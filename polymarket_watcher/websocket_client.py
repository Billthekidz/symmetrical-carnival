"""Auto-reconnecting WebSocket client for the Polymarket CLOB market channel.

Subscribes to one or more outcome tokens and dispatches decoded JSON events
to an async callback.  Reconnects automatically with a configurable delay on
any connection error.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, List

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Type alias for the event-dispatch callback.
EventCallback = Callable[[dict], Awaitable[None]]


class PolymarketWebSocketClient:
    """Connects to the Polymarket CLOB market channel and dispatches events.

    Parameters
    ----------
    asset_ids:
        List of CLOB token IDs to subscribe to.
    on_event:
        Async callback invoked for every decoded JSON event received from the
        WebSocket channel.
    reconnect_delay:
        Seconds to wait before reconnecting after a connection error.
    """

    def __init__(
        self,
        asset_ids: List[str],
        on_event: EventCallback,
        reconnect_delay: float = 5.0,
    ) -> None:
        self._asset_ids = asset_ids
        self._on_event = on_event
        self._reconnect_delay = reconnect_delay

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Connect, subscribe, and consume events — reconnecting as needed."""
        while True:
            try:
                await self._connect_and_consume()
            except asyncio.CancelledError:
                logger.info("WebSocket client received cancellation; shutting down.")
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "WebSocket error: %s.  Reconnecting in %.0f s…",
                    exc,
                    self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _connect_and_consume(self) -> None:
        async with websockets.connect(WS_URL) as ws:
            logger.info("Connected to %s", WS_URL)

            subscribe_msg = {
                "type": "market",
                "assets_ids": self._asset_ids,
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info("Subscribed to %d asset(s).", len(self._asset_ids))

            async for raw_msg in ws:
                await self._handle_raw(raw_msg)

    async def _handle_raw(self, raw_msg: str) -> None:
        """Parse *raw_msg* and forward each event to the callback."""
        try:
            payload = json.loads(raw_msg)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON message; skipping.  Raw: %r", raw_msg)
            return

        # The API may send a single object or a list of objects in one frame.
        events = payload if isinstance(payload, list) else [payload]
        for event in events:
            try:
                await self._on_event(event)
            except Exception:  # noqa: BLE001
                logger.exception("Unhandled error in event callback.")
