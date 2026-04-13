"""Fetch open positions for a Polymarket proxy wallet from the public Data API.

No authentication is required — the Data API is publicly accessible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import requests

logger = logging.getLogger(__name__)

DATA_API_BASE = "https://data-api.polymarket.com"
REQUEST_TIMEOUT = 10  # seconds


@dataclass
class Position:
    """A single open outcome-token position held by the wallet.

    Attributes
    ----------
    asset_id:
        The CLOB token ID — used to subscribe to WebSocket order-book feeds.
    slug:
        Market slug (for logging and display purposes).
    title:
        Human-readable market question / title.
    direction:
        ``"YES"`` or ``"NO"`` — which outcome token is held.
    size:
        Number of shares owned (Decimal).
    avg_price:
        Weighted average entry price in the 0–1 range (Decimal).
    entry_cost:
        Total capital deployed: ``avg_price × size`` (Decimal).
    """

    asset_id: str
    slug: str
    title: str
    direction: str
    size: Decimal
    avg_price: Decimal
    entry_cost: Decimal


def fetch_positions(proxy_wallet: str) -> list[Position]:
    """Return all open positions (size > 0) for *proxy_wallet*.

    Parameters
    ----------
    proxy_wallet:
        The Polymarket proxy wallet address (e.g. ``"0xAbCd…"``).

    Returns
    -------
    list[Position]
        One :class:`Position` per open holding.  Positions with ``size ≤ 0``
        are filtered out before returning.

    Raises
    ------
    requests.HTTPError
        When the Data API returns a non-2xx response.
    """
    url = f"{DATA_API_BASE}/positions"
    logger.debug("Fetching positions for wallet %s from %s", proxy_wallet, url)

    resp = requests.get(
        url,
        params={"user": proxy_wallet, "sizeThreshold": "0.01"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()

    positions: List[Position] = []
    for item in resp.json():
        raw_size = item.get("size", "0")
        size = Decimal(str(raw_size))
        if size <= Decimal("0"):
            continue

        avg_price = Decimal(str(item.get("avgPrice", "0")))
        # The "asset" field holds the CLOB token ID used for WebSocket subscriptions.
        asset_id: str = item.get("asset", "")
        # Market display info.
        market = item.get("market") if isinstance(item.get("market"), dict) else {}
        slug: str = market.get("slug", "")
        title: str = item.get("title") or market.get("question", "")
        # "outcome" is "Yes" or "No"; normalise to uppercase.
        direction: str = item.get("outcome", "YES").upper()

        positions.append(
            Position(
                asset_id=asset_id,
                slug=slug,
                title=title,
                direction=direction,
                size=size,
                avg_price=avg_price,
                entry_cost=avg_price * size,
            )
        )

    logger.info(
        "Found %d open position(s) for wallet %s.",
        len(positions),
        proxy_wallet[:8] + "…" if len(proxy_wallet) > 8 else proxy_wallet,
    )
    return positions
