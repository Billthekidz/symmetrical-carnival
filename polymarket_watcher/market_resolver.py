"""Resolve a Polymarket market slug to YES/NO CLOB token IDs.

Uses the public Gamma REST API — no authentication required.
"""

from __future__ import annotations

import json
import logging
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
REQUEST_TIMEOUT = 10  # seconds


def get_token_ids_for_slug(slug: str) -> Tuple[str, str]:
    """Return ``(yes_token_id, no_token_id)`` for *slug*.

    Parameters
    ----------
    slug:
        The URL slug of the market, e.g. ``"will-trump-win-in-2024"``.

    Returns
    -------
    tuple[str, str]
        A two-element tuple where index 0 is the YES token ID and index 1 is
        the NO token ID.

    Raises
    ------
    ValueError
        When no market is found for the given slug, or the market does not
        contain exactly two outcome tokens.
    requests.HTTPError
        When the Gamma API returns a non-2xx response.
    """
    url = f"{GAMMA_API_BASE}/markets"
    logger.debug("Fetching token IDs for slug %r from %s", slug, url)

    resp = requests.get(url, params={"slug": slug}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    markets = resp.json()
    if not markets:
        raise ValueError(f"No market found for slug: {slug!r}")

    market = markets[0]
    raw_ids = market.get("clobTokenIds", "[]")

    # The field is sometimes a JSON-encoded string rather than a native list.
    clob_token_ids: list[str] = (
        json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
    )

    if len(clob_token_ids) < 2:
        raise ValueError(
            f"Expected at least 2 token IDs for slug {slug!r}, "
            f"got {len(clob_token_ids)}: {clob_token_ids}"
        )

    yes_id, no_id = clob_token_ids[0], clob_token_ids[1]
    logger.info(
        "Resolved slug %r → YES token %s… / NO token %s…", slug, yes_id[:8], no_id[:8]
    )
    return yes_id, no_id
