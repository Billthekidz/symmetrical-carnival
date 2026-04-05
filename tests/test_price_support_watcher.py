"""Unit tests for polymarket_watcher.watchers.price_support_watcher."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from polymarket_watcher.watchers.price_support_watcher import PriceSupportWatcher

ASSET_ID = "abc123"


def _make_watcher(
    threshold_pct: float = 5.0,
    alert_drop_pct: float = 20.0,
) -> tuple[PriceSupportWatcher, MagicMock]:
    mock_action = MagicMock()
    mock_action.name = "MockAction"
    watcher = PriceSupportWatcher(
        asset_id=ASSET_ID,
        direction="yes",
        threshold_pct=threshold_pct,
        alert_drop_pct=alert_drop_pct,
        actions=[mock_action],
    )
    return watcher, mock_action


def _book_event(asset_id: str, bids: list, asks: list | None = None) -> dict:
    return {
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids,
        "asks": asks or [],
    }


def _price_change_event(asset_id: str, changes: list) -> dict:
    return {
        "event_type": "price_change",
        "price_changes": [
            {"asset_id": asset_id, **c} for c in changes
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────


class TestPriceSupportWatcherName:
    def test_name_includes_direction(self) -> None:
        watcher, _ = _make_watcher()
        assert "yes" in watcher.name


class TestPriceSupportWatcherBookEvent:
    def test_accepts_book_event_for_monitored_asset(self) -> None:
        watcher, action = _make_watcher()
        watcher.on_event(
            _book_event(ASSET_ID, bids=[{"price": "0.50", "size": "100"}])
        )
        # No alert on first snapshot (no prior baseline).
        action.execute.assert_not_called()

    def test_ignores_book_event_for_different_asset(self) -> None:
        watcher, _ = _make_watcher()
        # Should not raise and should not update internal state.
        watcher.on_event(_book_event("other-asset", bids=[{"price": "0.90", "size": "999"}]))
        assert watcher._order_book.best_bid() is None


class TestPriceSupportWatcherDropAlert:
    def test_fires_action_when_support_drops_beyond_threshold(self) -> None:
        watcher, action = _make_watcher(alert_drop_pct=20.0)

        # First snapshot: support = 100 shares near best bid.
        watcher.on_event(
            _book_event(ASSET_ID, bids=[{"price": "0.50", "size": "100"}])
        )

        # Second event: best bid remains but size shrinks by 50 % → alert.
        watcher.on_event(
            _price_change_event(
                ASSET_ID,
                [{"price": "0.50", "size": "50", "side": "BUY"}],
            )
        )

        action.execute.assert_called_once()
        payload: dict[str, Any] = action.execute.call_args[0][0]
        assert payload["support_before"] == pytest.approx(100.0)
        assert payload["support_after"] == pytest.approx(50.0)
        assert payload["change_pct"] == pytest.approx(-50.0, abs=0.1)

    def test_no_action_when_drop_below_threshold(self) -> None:
        watcher, action = _make_watcher(alert_drop_pct=20.0)

        watcher.on_event(
            _book_event(ASSET_ID, bids=[{"price": "0.50", "size": "100"}])
        )
        # 5 % drop — below the 20 % threshold.
        watcher.on_event(
            _price_change_event(
                ASSET_ID,
                [{"price": "0.50", "size": "95", "side": "BUY"}],
            )
        )

        action.execute.assert_not_called()

    def test_no_action_when_support_increases(self) -> None:
        watcher, action = _make_watcher(alert_drop_pct=20.0)

        watcher.on_event(
            _book_event(ASSET_ID, bids=[{"price": "0.50", "size": "100"}])
        )
        watcher.on_event(
            _price_change_event(
                ASSET_ID,
                [{"price": "0.50", "size": "200", "side": "BUY"}],
            )
        )

        action.execute.assert_not_called()


class TestPriceSupportWatcherPriceChangeFiltering:
    def test_ignores_price_change_for_different_asset(self) -> None:
        watcher, action = _make_watcher()

        watcher.on_event(
            _book_event(ASSET_ID, bids=[{"price": "0.50", "size": "100"}])
        )
        # Price change for a different asset should not update our book.
        watcher.on_event(
            _price_change_event(
                "other-asset",
                [{"price": "0.50", "size": "0", "side": "BUY"}],
            )
        )
        # Best bid must still be 0.50.
        assert watcher._order_book.best_bid() == Decimal("0.50")


class TestSupportedEventTypes:
    def test_only_handles_book_and_price_change(self) -> None:
        watcher, _ = _make_watcher()
        assert watcher.supported_event_types == frozenset({"book", "price_change"})
