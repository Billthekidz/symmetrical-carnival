"""Watcher that monitors bid-side price support for an outcome token.

"Price support" is defined here as the total resting bid volume within a
configurable depth window (e.g. 5 %) of the best bid price.  A significant
drop in that figure — beyond ``alert_drop_pct`` — is treated as a weakening
of directional support and triggers all registered actions.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, FrozenSet, List, Optional

from ..actions.base_action import BaseAction
from ..order_book import OrderBook
from .base_watcher import BaseWatcher

logger = logging.getLogger(__name__)


class PriceSupportWatcher(BaseWatcher):
    """Detects significant drops in bid-side price support.

    Parameters
    ----------
    asset_id:
        The CLOB token ID to monitor (YES or NO token of the market).
    direction:
        Human-readable label such as ``"yes"`` / ``"no"`` used in alert
        payloads.
    threshold_pct:
        Bids within this percentage of the best bid are counted as
        "supporting" the price level.
    alert_drop_pct:
        Fire actions when support drops by at least this percentage compared
        to the previous measurement.
    actions:
        List of :class:`~polymarket_watcher.actions.base_action.BaseAction`
        instances to invoke when an alert is triggered.
    """

    supported_event_types: FrozenSet[str] = frozenset({"book", "price_change"})

    def __init__(
        self,
        asset_id: str,
        direction: str,
        threshold_pct: float,
        alert_drop_pct: float,
        actions: List[BaseAction],
    ) -> None:
        self._asset_id = asset_id
        self._direction = direction
        self._threshold_pct = threshold_pct
        self._alert_drop_pct = alert_drop_pct
        self._actions = actions
        self._order_book = OrderBook(asset_id=asset_id)
        self._last_support: Optional[Decimal] = None

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return f"PriceSupportWatcher({self._direction})"

    def on_event(self, event: dict[str, Any]) -> None:  # noqa: D102
        event_type = event.get("event_type")

        if event_type == "book":
            if event.get("asset_id") == self._asset_id:
                self._order_book.apply_book_snapshot(
                    event.get("bids", []),
                    event.get("asks", []),
                )
                self._check_support()

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
                self._check_support()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_support(self) -> None:
        support = self._order_book.bid_support_within_pct(self._threshold_pct)
        best_bid = self._order_book.best_bid()

        logger.debug(
            "%s: best_bid=%s  support=%s",
            self.name,
            best_bid,
            support,
        )

        if self._last_support is not None and self._last_support > Decimal("0"):
            change_pct = float(
                (support - self._last_support) / self._last_support * Decimal("100")
            )
            if change_pct <= -self._alert_drop_pct:
                self._fire_alert(support, best_bid, change_pct)

        self._last_support = support

    def _fire_alert(
        self,
        support_after: Decimal,
        best_bid: Optional[Decimal],
        change_pct: float,
    ) -> None:
        event_data: dict[str, Any] = {
            "watcher": self.name,
            "direction": self._direction,
            "asset_id": self._asset_id,
            "support_before": float(self._last_support),  # type: ignore[arg-type]
            "support_after": float(support_after),
            "change_pct": round(change_pct, 2),
            "best_bid": float(best_bid) if best_bid is not None else None,
        }
        logger.warning(
            "Price support drop of %.1f %% detected for direction '%s'.",
            change_pct,
            self._direction,
        )
        for action in self._actions:
            try:
                action.execute(event_data)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Action %s raised an unhandled exception.", action.name
                )
