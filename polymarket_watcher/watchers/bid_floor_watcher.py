"""Watcher that checks whether bid-side liquidity beneath a position's entry
price remains a safe multiple of the position size.

The "platform" is defined as the total resting bid volume at prices ≤ the
position's average entry price.  When the platform drops below
``safety_multiple × position_size`` the position's entry level no longer has
adequate structural support and an alert is fired.

The alert re-arms once the ratio recovers above the safety multiple, so
repeated alerts are only generated when the situation deteriorates, recovers,
and deteriorates again — not on every book update.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from ..actions.base_action import BaseAction
from ..order_book import OrderBook
from .base_watcher import BaseWatcher

logger = logging.getLogger(__name__)


class BidFloorWatcher(BaseWatcher):
    """Alerts when bid-floor volume beneath the entry price is insufficient.

    Parameters
    ----------
    asset_id:
        The CLOB token ID to monitor.
    slug:
        Market slug used in alert payloads and log messages.
    direction:
        ``"YES"`` or ``"NO"`` — which side the position is on.
    entry_price:
        The position's average entry price (0–1 scale).
    position_size:
        Number of shares in the position.
    safety_multiple:
        Minimum ratio of platform volume to position size considered safe.
        Default 10 means the total bid volume at-or-below the entry price must
        be at least 10× the position size to avoid an alert.
    actions:
        Actions to invoke when an alert is triggered.
    """

    supported_event_types: frozenset[str] = frozenset({"book", "price_change"})

    def __init__(
        self,
        asset_id: str,
        slug: str,
        direction: str,
        entry_price: Decimal,
        position_size: Decimal,
        safety_multiple: float,
        actions: list[BaseAction],
    ) -> None:
        self._asset_id = asset_id
        self._slug = slug
        self._direction = direction
        self._entry_price = entry_price
        self._position_size = position_size
        self._safety_multiple = Decimal(str(safety_multiple))
        self._actions = actions
        self._order_book = OrderBook(asset_id=asset_id)
        # True while the ratio is below the safety threshold (alert is "armed").
        self._alert_active: bool = False

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return f"BidFloorWatcher({self._slug!r}, {self._direction})"

    def on_event(self, event: dict[str, Any]) -> None:  # noqa: D102
        event_type = event.get("event_type")

        if event_type == "book":
            if event.get("asset_id") == self._asset_id:
                self._order_book.apply_book_snapshot(
                    event.get("bids", []),
                    event.get("asks", []),
                )
                self._check_floor()

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
                self._check_floor()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_floor(self) -> None:
        if self._position_size <= Decimal("0"):
            return

        platform = self._order_book.bid_volume_at_or_below(self._entry_price)
        ratio = platform / self._position_size
        best_bid = self._order_book.best_bid()

        logger.debug(
            "%s: entry=%s  platform=%s  ratio=%.2fx  (need %.1fx)",
            self.name,
            self._entry_price,
            platform,
            ratio,
            self._safety_multiple,
        )

        unsafe = ratio < self._safety_multiple

        if unsafe and not self._alert_active:
            self._alert_active = True
            self._fire_alert(platform, ratio, best_bid)
        elif not unsafe and self._alert_active:
            # Ratio has recovered — re-arm so the next drop triggers again.
            self._alert_active = False
            logger.info(
                "%s: platform ratio recovered to %.2fx — re-armed.",
                self.name,
                ratio,
            )

    def _fire_alert(
        self,
        platform: Decimal,
        ratio: Decimal,
        best_bid: "Decimal | None",
    ) -> None:
        event_data: dict[str, Any] = {
            "watcher": self.name,
            "slug": self._slug,
            "direction": self._direction,
            "asset_id": self._asset_id,
            "entry_price": float(self._entry_price),
            "position_size": float(self._position_size),
            "platform_volume": float(platform),
            "platform_ratio": float(ratio),
            "safety_multiple": float(self._safety_multiple),
            "best_bid": float(best_bid) if best_bid is not None else None,
        }
        logger.warning(
            "%s: platform ratio %.2fx is below safety multiple %.1fx "
            "(platform=%s, position=%s).",
            self.name,
            ratio,
            self._safety_multiple,
            platform,
            self._position_size,
        )
        for action in self._actions:
            try:
                action.execute(event_data)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Action %s raised an unhandled exception.", action.name
                )
