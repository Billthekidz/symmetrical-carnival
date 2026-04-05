"""Local order-book state management and price-support calculation.

The order book is maintained by applying a full snapshot (``book`` event)
followed by incremental ``price_change`` deltas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


@dataclass
class OrderLevel:
    """A single price level in the order book."""

    price: Decimal
    size: Decimal


@dataclass
class OrderBook:
    """Mutable, locally-maintained order book for one outcome token.

    Attributes
    ----------
    asset_id:
        The CLOB token ID this book belongs to.
    bids:
        Buy orders, sorted highest-price first.
    asks:
        Sell orders, sorted lowest-price first.
    """

    asset_id: str
    bids: List[OrderLevel] = field(default_factory=list)
    asks: List[OrderLevel] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def apply_book_snapshot(
        self,
        bids: list[dict],
        asks: list[dict],
    ) -> None:
        """Replace the entire book with a fresh snapshot.

        Parameters
        ----------
        bids, asks:
            Each entry is a dict with ``"price"`` and ``"size"`` string keys.
        """
        self.bids = [
            OrderLevel(Decimal(b["price"]), Decimal(b["size"])) for b in bids
        ]
        self.asks = [
            OrderLevel(Decimal(a["price"]), Decimal(a["size"])) for a in asks
        ]
        self._sort()

    def apply_price_change(self, price: str, size: str, side: str) -> None:
        """Apply an incremental order-book update.

        Parameters
        ----------
        price:
            String representation of the price level being updated.
        size:
            New total resting size at *price*.  ``"0"`` means the level is
            fully removed.
        side:
            ``"BUY"`` for a bid update, ``"SELL"`` for an ask update.
        """
        p = Decimal(price)
        s = Decimal(size)
        if side == "BUY":
            levels: List[OrderLevel] = self.bids
        elif side == "SELL":
            levels = self.asks
        else:
            raise ValueError(f"Unexpected order-book side: {side!r}")

        # Remove any existing level at this price.
        levels[:] = [lv for lv in levels if lv.price != p]

        # Re-insert only when the new size is positive.
        if s > Decimal("0"):
            levels.append(OrderLevel(p, s))

        self._sort()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def best_bid(self) -> Optional[Decimal]:
        """Return the highest bid price, or ``None`` when the book is empty."""
        return self.bids[0].price if self.bids else None

    def best_ask(self) -> Optional[Decimal]:
        """Return the lowest ask price, or ``None`` when the book is empty."""
        return self.asks[0].price if self.asks else None

    def bid_support_within_pct(self, pct: float) -> Decimal:
        """Sum of bid sizes where price ≥ best_bid × (1 − pct / 100).

        This represents the total buy-side liquidity within *pct* percent of
        the best bid — a proxy for "price support" on the long side.

        Parameters
        ----------
        pct:
            Depth window as a percentage, e.g. ``5.0`` for 5 %.

        Returns
        -------
        Decimal
            Total supported size; ``Decimal("0")`` when there are no bids.
        """
        best = self.best_bid()
        if best is None:
            return Decimal("0")

        floor = best * (Decimal("1") - Decimal(str(pct)) / Decimal("100"))
        return sum(
            (lv.size for lv in self.bids if lv.price >= floor),
            Decimal("0"),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sort(self) -> None:
        self.bids.sort(key=lambda lv: lv.price, reverse=True)
        self.asks.sort(key=lambda lv: lv.price)
