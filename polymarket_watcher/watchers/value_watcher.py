"""Watcher that tracks a position's current market value as a percentage of
its entry cost and fires one-shot alerts as it crosses downward thresholds.

The current value is estimated as ``best_bid × position_size``.  Each
configured threshold (e.g. 90 %, 80 %, 70 %, 60 % of entry cost) fires
exactly once per session when ``value_pct`` first drops to or below it.
Thresholds do not re-arm; they are intended as escalating panic-level signals.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, FrozenSet, List, Set

from ..actions.base_action import BaseAction
from ..order_book import OrderBook
from .base_watcher import BaseWatcher

logger = logging.getLogger(__name__)


class ValueWatcher(BaseWatcher):
    """Fires descending value alerts as a position loses a percentage of cost.

    Parameters
    ----------
    asset_id:
        The CLOB token ID to monitor.
    slug:
        Market slug used in alert payloads and log messages.
    direction:
        ``"YES"`` or ``"NO"`` — which side the position is on.
    entry_cost:
        Total capital deployed (``avg_price × position_size``).
    position_size:
        Number of shares in the position.
    avg_price:
        Average entry price (0–1 scale), stored for payload context.
    alert_thresholds:
        Sorted list of value-retention percentages at which to alert,
        e.g. ``[90.0, 80.0, 70.0, 60.0]``.  May be provided in any order —
        the watcher sorts them internally.
    actions:
        Actions to invoke when an alert is triggered.
    """

    supported_event_types: FrozenSet[str] = frozenset({"book", "price_change"})

    def __init__(
        self,
        asset_id: str,
        slug: str,
        direction: str,
        entry_cost: Decimal,
        position_size: Decimal,
        avg_price: Decimal,
        alert_thresholds: List[float],
        actions: List[BaseAction],
    ) -> None:
        self._asset_id = asset_id
        self._slug = slug
        self._direction = direction
        self._entry_cost = entry_cost
        self._position_size = position_size
        self._avg_price = avg_price
        # Sort descending so we check the highest threshold first.
        self._thresholds: List[float] = sorted(alert_thresholds, reverse=True)
        self._actions = actions
        self._order_book = OrderBook(asset_id=asset_id)
        self._fired_thresholds: Set[float] = set()

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return f"ValueWatcher({self._slug!r}, {self._direction})"

    def on_event(self, event: dict[str, Any]) -> None:  # noqa: D102
        event_type = event.get("event_type")

        if event_type == "book":
            if event.get("asset_id") == self._asset_id:
                self._order_book.apply_book_snapshot(
                    event.get("bids", []),
                    event.get("asks", []),
                )
                self._check_value()

        elif event_type == "price_change":
            affected = False
            for change in event.get("price_changes", []):
                if change.get("asset_id") == self._asset_id:
                    self._order_book.apply_price_change(
                        change["price"],
                        change["size"],
                        change["side"],
                    )
                    affected = True
            if affected:
                self._check_value()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_value(self) -> None:
        if self._entry_cost <= Decimal("0") or self._position_size <= Decimal("0"):
            return

        best_bid = self._order_book.best_bid()
        if best_bid is None:
            return

        current_value = best_bid * self._position_size
        value_pct = float(current_value / self._entry_cost * Decimal("100"))

        logger.debug(
            "%s: best_bid=%s  current_value=%s  value_pct=%.1f%%",
            self.name,
            best_bid,
            current_value,
            value_pct,
        )

        for threshold in self._thresholds:
            if value_pct <= threshold and threshold not in self._fired_thresholds:
                self._fired_thresholds.add(threshold)
                self._fire_alert(threshold, value_pct, current_value, best_bid)

    def _fire_alert(
        self,
        threshold: float,
        value_pct: float,
        current_value: Decimal,
        best_bid: Decimal,
    ) -> None:
        event_data: dict[str, Any] = {
            "watcher": self.name,
            "slug": self._slug,
            "direction": self._direction,
            "asset_id": self._asset_id,
            "entry_price": float(self._avg_price),
            "position_size": float(self._position_size),
            "entry_cost": float(self._entry_cost),
            "current_value": float(current_value),
            "value_pct": round(value_pct, 2),
            "threshold_crossed": threshold,
            "best_bid": float(best_bid),
        }
        logger.warning(
            "%s: position value at %.1f%% of cost — crossed the %.0f%% threshold "
            "(current_value=%s, entry_cost=%s).",
            self.name,
            value_pct,
            threshold,
            current_value,
            self._entry_cost,
        )
        for action in self._actions:
            try:
                action.execute(event_data)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Action %s raised an unhandled exception.", action.name
                )
