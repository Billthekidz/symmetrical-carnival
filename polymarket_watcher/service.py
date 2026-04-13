"""Service orchestrator — wires configuration, market resolution, watchers,
and the WebSocket client into a single runnable unit.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from .actions.log_action import LogAction
from .config import Config
from .market_resolver import get_token_ids_for_slug
from .position_fetcher import Position, fetch_positions
from .watchers.base_watcher import BaseWatcher
from .watchers.bid_floor_watcher import BidFloorWatcher
from .watchers.value_watcher import ValueWatcher
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
        self._watchers: list[BaseWatcher] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Resolve positions, build watchers, and start the event loop."""
        cfg = self._config
        actions = [LogAction()] if cfg.actions.log_enabled else []

        if cfg.account.proxy_wallet:
            # ── Primary path: auto-discover positions from the wallet ──
            logger.info(
                "Fetching positions for proxy wallet %s…",
                cfg.account.proxy_wallet,
            )
            positions = fetch_positions(cfg.account.proxy_wallet)

            if not positions:
                logger.warning(
                    "No open positions found for wallet %s. Nothing to watch.",
                    cfg.account.proxy_wallet,
                )
                return

            asset_ids = [p.asset_id for p in positions]
            self._watchers = self._build_watchers_for_positions(
                cfg, positions, actions
            )
        else:
            # ── Fallback: single-market manual config ──────────────────
            logger.warning(
                "No proxy_wallet configured — falling back to manual market config."
            )
            slug = cfg.market.slug
            direction = cfg.market.direction

            logger.info("Resolving token IDs for slug %r…", slug)
            yes_token_id, no_token_id = get_token_ids_for_slug(slug)

            asset_ids = [yes_token_id, no_token_id]
            self._watchers = self._build_watchers_for_manual(
                cfg, direction, yes_token_id, no_token_id, actions
            )

        client = PolymarketWebSocketClient(
            asset_ids=asset_ids,
            on_event=self._dispatch_event,
            reconnect_delay=cfg.service.reconnect_delay_sec,
        )
        await client.run()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_watchers_for_positions(
        self,
        cfg: Config,
        positions: list[Position],
        actions: list[Any],
    ) -> list[BaseWatcher]:
        """Build BidFloorWatcher + ValueWatcher for every open position."""
        watchers: list[BaseWatcher] = []
        bf_cfg = cfg.watcher.bid_floor
        val_cfg = cfg.watcher.value

        for pos in positions:
            logger.info(
                "Setting up watchers for %r (%s) — size=%s avg_price=%s",
                pos.slug or pos.asset_id[:12],
                pos.direction,
                pos.size,
                pos.avg_price,
            )

            if bf_cfg.enabled:
                watchers.append(
                    BidFloorWatcher(
                        asset_id=pos.asset_id,
                        slug=pos.slug,
                        direction=pos.direction,
                        entry_price=pos.avg_price,
                        position_size=pos.size,
                        safety_multiple=bf_cfg.safety_multiple,
                        actions=actions,
                    )
                )

            if val_cfg.enabled:
                watchers.append(
                    ValueWatcher(
                        asset_id=pos.asset_id,
                        slug=pos.slug,
                        direction=pos.direction,
                        entry_cost=pos.entry_cost,
                        position_size=pos.size,
                        avg_price=pos.avg_price,
                        alert_thresholds=val_cfg.alert_thresholds,
                        actions=actions,
                    )
                )

        return watchers

    def _build_watchers_for_manual(
        self,
        cfg: Config,
        direction: str,
        yes_token_id: str,
        no_token_id: str,
        actions: list[Any],
    ) -> list[BaseWatcher]:
        """Build watchers from the manual market config (fallback path)."""
        watchers: list[BaseWatcher] = []
        asset_id = yes_token_id if direction in ("yes", "long") else no_token_id
        slug = cfg.market.slug
        bf_cfg = cfg.watcher.bid_floor
        val_cfg = cfg.watcher.value

        entry_price = Decimal(str(cfg.market.entry_price))
        position_size = Decimal(str(cfg.market.position_size))
        entry_cost = entry_price * position_size

        # ── Bid-floor watcher ──────────────────────────────────────────
        if bf_cfg.enabled and position_size > Decimal("0"):
            logger.info(
                "Enabling BidFloorWatcher for direction '%s', asset %s…",
                direction,
                asset_id[:12],
            )
            watchers.append(
                BidFloorWatcher(
                    asset_id=asset_id,
                    slug=slug,
                    direction=direction,
                    entry_price=entry_price,
                    position_size=position_size,
                    safety_multiple=bf_cfg.safety_multiple,
                    actions=actions,
                )
            )

        # ── Value watcher ──────────────────────────────────────────────
        if val_cfg.enabled and entry_cost > Decimal("0"):
            logger.info(
                "Enabling ValueWatcher for direction '%s', asset %s…",
                direction,
                asset_id[:12],
            )
            watchers.append(
                ValueWatcher(
                    asset_id=asset_id,
                    slug=slug,
                    direction=direction,
                    entry_cost=entry_cost,
                    position_size=position_size,
                    avg_price=entry_price,
                    alert_thresholds=val_cfg.alert_thresholds,
                    actions=actions,
                )
            )

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
