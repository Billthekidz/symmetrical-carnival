"""Unit tests for polymarket_watcher.watchers.bid_floor_watcher."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from polymarket_watcher.watchers.bid_floor_watcher import BidFloorWatcher

ASSET_ID = "asset-xyz"


def _make_watcher(
    entry_price: float = 0.50,
    position_size: float = 100.0,
    safety_multiple: float = 10.0,
    floor_window_pct: float = 10.0,
) -> tuple[BidFloorWatcher, MagicMock]:
    mock_action = MagicMock()
    mock_action.name = "MockAction"
    watcher = BidFloorWatcher(
        asset_id=ASSET_ID,
        slug="test-market",
        direction="yes",
        entry_price=Decimal(str(entry_price)),
        position_size=Decimal(str(position_size)),
        safety_multiple=safety_multiple,
        floor_window_pct=floor_window_pct,
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
        "price_changes": [{"asset_id": asset_id, **c} for c in changes],
    }


# ──────────────────────────────────────────────────────────────────────────────


class TestBidFloorWatcherName:
    def test_name_includes_slug_and_direction(self) -> None:
        watcher, _ = _make_watcher()
        assert "test-market" in watcher.name
        assert "yes" in watcher.name


class TestBidFloorWatcherSupportedEvents:
    def test_handles_book_and_price_change(self) -> None:
        watcher, _ = _make_watcher()
        assert watcher.supported_event_types == frozenset({"book", "price_change"})


class TestBidFloorWatcherBookEventRouting:
    def test_ignores_book_event_for_different_asset(self) -> None:
        watcher, action = _make_watcher()
        watcher.on_event(_book_event("other-asset", bids=[{"price": "0.40", "size": "9999"}]))
        action.execute.assert_not_called()
        assert watcher._order_book.best_bid() is None

    def test_ignores_price_change_for_different_asset(self) -> None:
        watcher, action = _make_watcher()
        # Seed the book.
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.45", "size": "500"}]))
        action.execute.reset_mock()  # reset any alert from first snapshot
        # Price change for a different asset must not affect our book.
        watcher.on_event(
            _price_change_event("other-asset", [{"price": "0.45", "size": "0", "side": "BUY"}])
        )
        assert watcher._order_book.best_bid() == Decimal("0.45")


class TestBidFloorWatcherAlertFiring:
    def test_fires_when_platform_below_safety_multiple(self) -> None:
        # entry=0.50, size=100, safety=10 → need >= 1000 volume at/below 0.50
        watcher, action = _make_watcher(entry_price=0.50, position_size=100.0, safety_multiple=10.0)

        # Platform at/below 0.50: only 800 (< 1000) → alert
        watcher.on_event(
            _book_event(
                ASSET_ID,
                bids=[
                    {"price": "0.50", "size": "500"},
                    {"price": "0.45", "size": "300"},
                    {"price": "0.55", "size": "999"},  # ABOVE entry — excluded
                ],
            )
        )
        action.execute.assert_called_once()
        payload: dict[str, Any] = action.execute.call_args[0][0]
        assert payload["platform_volume"] == pytest.approx(800.0)
        assert payload["platform_ratio"] == pytest.approx(8.0)
        assert payload["entry_price"] == pytest.approx(0.50)
        assert payload["position_size"] == pytest.approx(100.0)

    def test_no_alert_when_platform_above_safety_multiple(self) -> None:
        # entry=0.50, size=100, safety=10 → need >= 1000
        watcher, action = _make_watcher(entry_price=0.50, position_size=100.0, safety_multiple=10.0)

        # 1200 at/below 0.50 — safe
        watcher.on_event(
            _book_event(
                ASSET_ID,
                bids=[
                    {"price": "0.50", "size": "700"},
                    {"price": "0.45", "size": "500"},
                ],
            )
        )
        action.execute.assert_not_called()

    def test_alert_payload_includes_slug_and_direction(self) -> None:
        watcher, action = _make_watcher(entry_price=0.50, position_size=100.0, safety_multiple=10.0)
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.49", "size": "50"}]))

        payload = action.execute.call_args[0][0]
        assert payload["slug"] == "test-market"
        assert payload["direction"] == "yes"


class TestBidFloorWatcherReArm:
    def test_does_not_fire_twice_while_unsafe(self) -> None:
        watcher, action = _make_watcher(entry_price=0.50, position_size=100.0, safety_multiple=10.0)

        # First unsafe event → alert fires.
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.49", "size": "50"}]))
        assert action.execute.call_count == 1

        # Still unsafe on next tick → should NOT fire again.
        watcher.on_event(
            _price_change_event(ASSET_ID, [{"price": "0.49", "size": "40", "side": "BUY"}])
        )
        assert action.execute.call_count == 1

    def test_rearms_after_recovery_and_refires(self) -> None:
        watcher, action = _make_watcher(entry_price=0.50, position_size=100.0, safety_multiple=10.0)

        # 1. Unsafe → alert fires.
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.49", "size": "50"}]))
        assert action.execute.call_count == 1

        # 2. Recover (>= 1000 at/below 0.50) → re-arm, no new alert.
        watcher.on_event(
            _price_change_event(ASSET_ID, [{"price": "0.49", "size": "1100", "side": "BUY"}])
        )
        assert action.execute.call_count == 1

        # 3. Drops again → alert fires again.
        watcher.on_event(
            _price_change_event(ASSET_ID, [{"price": "0.49", "size": "20", "side": "BUY"}])
        )
        assert action.execute.call_count == 2

    def test_no_alert_when_position_size_is_zero(self) -> None:
        watcher, action = _make_watcher(position_size=0.0)
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.40", "size": "1"}]))
        action.execute.assert_not_called()


class TestBidFloorWatcherFloorWindow:
    """floor_window_pct limits the support scan to a window below entry price."""

    def test_bids_outside_window_are_excluded(self) -> None:
        # entry=0.50, floor_window_pct=10 → window [0.45, 0.50]
        # Bid at 0.44 is outside the window and must NOT count.
        # safety=10, size=100 → need >= 1000 within window
        watcher, action = _make_watcher(
            entry_price=0.50, position_size=100.0, safety_multiple=10.0, floor_window_pct=10.0
        )
        watcher.on_event(
            _book_event(
                ASSET_ID,
                bids=[
                    {"price": "0.49", "size": "500"},   # inside window
                    {"price": "0.44", "size": "9999"},  # outside window — ignored
                ],
            )
        )
        # Only 500 inside the window → below 1000 → alert fires.
        action.execute.assert_called_once()
        payload: dict[str, Any] = action.execute.call_args[0][0]
        assert payload["platform_volume"] == pytest.approx(500.0)

    def test_bids_inside_window_are_counted(self) -> None:
        # entry=0.50, floor_window_pct=10 → window [0.45, 0.50]
        watcher, action = _make_watcher(
            entry_price=0.50, position_size=100.0, safety_multiple=10.0, floor_window_pct=10.0
        )
        watcher.on_event(
            _book_event(
                ASSET_ID,
                bids=[
                    {"price": "0.50", "size": "600"},   # at entry — included
                    {"price": "0.47", "size": "500"},   # inside window — included
                    {"price": "0.44", "size": "9999"},  # outside — ignored
                ],
            )
        )
        # 600 + 500 = 1100 ≥ 1000 → no alert
        action.execute.assert_not_called()

    def test_wider_window_includes_more_bids(self) -> None:
        # floor_window_pct=20 → window [0.40, 0.50]
        # Bid at 0.42 should now count.
        watcher, action = _make_watcher(
            entry_price=0.50, position_size=100.0, safety_multiple=10.0, floor_window_pct=20.0
        )
        watcher.on_event(
            _book_event(
                ASSET_ID,
                bids=[
                    {"price": "0.42", "size": "1200"},  # inside 20% window
                ],
            )
        )
        # 1200 ≥ 1000 → no alert
        action.execute.assert_not_called()
