"""Service orchestrator — wires configuration, market resolution, watchers,
and the WebSocket client into a single runnable unit.
"""

from __future__ import annotations

import logging
from typing import Any, List

from .actions.log_action import LogAction
from .config import Config
from .market_resolver import get_token_ids_for_slug
from .watchers.base_watcher import BaseWatcher
from .watchers.price_support_watcher import PriceSupportWatcher
from .websocket_client import PolymarketWebSocketClient

logger = logging.getLogger(__name__)


class WatcherService:
    """Top-level service that owns the watcher registry and event dispatch.

    Extending the service
    ---------------------
    *  To add a new watcher, instantiate it inside ``_build_watchers`` and
       append it to the returned list.
    *  To add a new action, instantiate it and include it in the ``actions``
       list passed to each watcher that should use it.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._watchers: List[BaseWatcher] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Resolve the market, build watchers, and start the event loop."""
        cfg = self._config
        slug = cfg.market.slug
        direction = cfg.market.direction.lower()

        logger.info("Resolving token IDs for slug %r…", slug)
        yes_token_id, no_token_id = get_token_ids_for_slug(slug)

        self._watchers = self._build_watchers(
            cfg, direction, yes_token_id, no_token_id
        )

        client = PolymarketWebSocketClient(
            asset_ids=[yes_token_id, no_token_id],
            on_event=self._dispatch_event,
            reconnect_delay=cfg.service.reconnect_delay_sec,
        )
        await client.run()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_watchers(
        self,
        cfg: Config,
        direction: str,
        yes_token_id: str,
        no_token_id: str,
    ) -> List[BaseWatcher]:
        """Instantiate and return all configured watchers.

        Add future watchers here.
        """
        watchers: List[BaseWatcher] = []

        # ── Price-support watcher ──────────────────────────────────────
        ps_cfg = cfg.watcher.price_support
        if ps_cfg.enabled:
            asset_id = (
                yes_token_id if direction in ("yes", "long") else no_token_id
            )
            logger.info(
                "Enabling PriceSupportWatcher for direction '%s', asset %s…",
                direction,
                asset_id[:12],
            )
            actions = [LogAction()] if cfg.actions.log_enabled else []
            watchers.append(
                PriceSupportWatcher(
                    asset_id=asset_id,
                    direction=direction,
                    threshold_pct=ps_cfg.threshold_pct,
                    alert_drop_pct=ps_cfg.alert_drop_pct,
                    actions=actions,
                )
            )

        # ── Add future watchers below this line ───────────────────────
        # Example:
        #   if cfg.watcher.smart_money.enabled:
        #       watchers.append(SmartMoneyWatcher(...))

        return watchers

    async def _dispatch_event(self, event: dict[str, Any]) -> None:
        """Fan out one WebSocket event to every interested watcher."""
        event_type = event.get("event_type")
        for watcher in self._watchers:
            supported = watcher.supported_event_types
            if supported is not None and event_type not in supported:
                continue
            try:
                watcher.on_event(event)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Watcher %s raised an unhandled exception.", watcher.name
                )
