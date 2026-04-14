"""Unit tests for polymarket_watcher.watchers.value_watcher."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from polymarket_watcher.watchers.value_watcher import ValueWatcher

ASSET_ID = "asset-val"


def _make_watcher(
    avg_price: float = 0.80,
    position_size: float = 100.0,
    alert_thresholds: list[float] | None = None,
) -> tuple[ValueWatcher, MagicMock]:
    if alert_thresholds is None:
        alert_thresholds = [90.0, 80.0, 70.0, 60.0]
    mock_action = MagicMock()
    mock_action.name = "MockAction"
    entry_cost = Decimal(str(avg_price)) * Decimal(str(position_size))
    watcher = ValueWatcher(
        asset_id=ASSET_ID,
        slug="test-value-market",
        direction="YES",
        entry_cost=entry_cost,
        position_size=Decimal(str(position_size)),
        avg_price=Decimal(str(avg_price)),
        alert_thresholds=alert_thresholds,
        actions=[mock_action],
    )
    return watcher, mock_action


def _book_event(asset_id: str, bids: list) -> dict:
    return {
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids,
        "asks": [],
    }


def _price_change_event(asset_id: str, changes: list) -> dict:
    return {
        "event_type": "price_change",
        "price_changes": [{"asset_id": asset_id, **c} for c in changes],
    }


# ──────────────────────────────────────────────────────────────────────────────


class TestValueWatcherName:
    def test_name_includes_slug_and_direction(self) -> None:
        watcher, _ = _make_watcher()
        assert "test-value-market" in watcher.name
        assert "YES" in watcher.name


class TestValueWatcherSupportedEvents:
    def test_handles_book_and_price_change(self) -> None:
        watcher, _ = _make_watcher()
        assert watcher.supported_event_types == frozenset({"book", "price_change"})


class TestValueWatcherNoAlertAboveThresholds:
    def test_no_alert_when_value_above_all_thresholds(self) -> None:
        # avg_price=0.80, size=100 → entry_cost=80; value at bid 0.77 = 77
        # 77/80 * 100 = 96.25% — above all thresholds
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.77", "size": "500"}]))
        action.execute.assert_not_called()

    def test_no_alert_when_book_is_empty(self) -> None:
        watcher, action = _make_watcher()
        watcher.on_event(_book_event(ASSET_ID, bids=[]))
        action.execute.assert_not_called()

    def test_ignores_events_for_different_asset(self) -> None:
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)
        # Value would be very low if this were our asset — but it's not.
        watcher.on_event(_book_event("other-asset", bids=[{"price": "0.01", "size": "1"}]))
        action.execute.assert_not_called()


class TestValueWatcherThresholdCrossing:
    def test_fires_90_pct_threshold(self) -> None:
        # entry_cost = 0.80 * 100 = 80; 90% = 72; bid must be <= 0.72 to trigger
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.71", "size": "500"}]))

        assert action.execute.call_count >= 1
        thresholds_fired = {c[0][0]["threshold_crossed"] for c in action.execute.call_args_list}
        assert 90.0 in thresholds_fired

    def test_fires_all_crossed_thresholds_on_single_event(self) -> None:
        # entry_cost = 80; 60% = 48; bid 0.47 → value 47 → crosses 90/80/70/60
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.47", "size": "500"}]))

        thresholds_fired = {c[0][0]["threshold_crossed"] for c in action.execute.call_args_list}
        assert thresholds_fired == {90.0, 80.0, 70.0, 60.0}

    def test_each_threshold_fires_only_once(self) -> None:
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)

        # First event drops through 90%.
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.71", "size": "500"}]))
        count_after_first = action.execute.call_count

        # Second event is still at the same level — 90% already fired, no repeat.
        watcher.on_event(
            _price_change_event(ASSET_ID, [{"price": "0.71", "size": "400", "side": "BUY"}])
        )
        assert action.execute.call_count == count_after_first

    def test_descending_thresholds_fire_in_sequence(self) -> None:
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)

        # entry_cost = 80; drop to 89% (71.2 value) → triggers 90%
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.712", "size": "999"}]))
        assert action.execute.call_count == 1
        assert action.execute.call_args[0][0]["threshold_crossed"] == 90.0

        # Drop to 79% (63.2 value) → triggers 80%  (90 already fired).
        # Remove the old best bid and add the new lower one in a single event so
        # best_bid moves from 0.712 to 0.632.
        watcher.on_event(
            _price_change_event(
                ASSET_ID,
                [
                    {"price": "0.712", "size": "0", "side": "BUY"},   # remove
                    {"price": "0.632", "size": "999", "side": "BUY"},  # new best
                ],
            )
        )
        thresholds = {c[0][0]["threshold_crossed"] for c in action.execute.call_args_list}
        assert 80.0 in thresholds
        assert action.execute.call_count == 2

    def test_thresholds_provided_out_of_order_still_work(self) -> None:
        # Provide thresholds in ascending order — watcher should sort internally.
        watcher, action = _make_watcher(
            avg_price=0.80,
            position_size=100.0,
            alert_thresholds=[60.0, 90.0, 70.0, 80.0],
        )
        # Crosses all four thresholds at once.
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.47", "size": "500"}]))
        thresholds_fired = {c[0][0]["threshold_crossed"] for c in action.execute.call_args_list}
        assert thresholds_fired == {90.0, 80.0, 70.0, 60.0}


class TestValueWatcherAlertPayload:
    def test_payload_fields(self) -> None:
        watcher, action = _make_watcher(avg_price=0.80, position_size=100.0)
        # 70% of 80 = 56; bid of 0.55 → value=55 → crosses 90, 80, 70
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.55", "size": "1"}]))

        # Inspect the payload for the 90% alert (first one fired, highest threshold).
        payloads = [c[0][0] for c in action.execute.call_args_list]
        payload_90 = next(p for p in payloads if p["threshold_crossed"] == 90.0)

        assert payload_90["slug"] == "test-value-market"
        assert payload_90["direction"] == "YES"
        assert payload_90["asset_id"] == ASSET_ID
        assert payload_90["entry_price"] == pytest.approx(0.80)
        assert payload_90["position_size"] == pytest.approx(100.0)
        assert payload_90["entry_cost"] == pytest.approx(80.0)
        assert payload_90["current_value"] == pytest.approx(55.0)
        assert payload_90["best_bid"] == pytest.approx(0.55)
        assert "value_pct" in payload_90


class TestValueWatcherZeroEntryCost:
    def test_no_alert_when_entry_cost_is_zero(self) -> None:
        mock_action = MagicMock()
        mock_action.name = "MockAction"
        watcher = ValueWatcher(
            asset_id=ASSET_ID,
            slug="zero-cost",
            direction="YES",
            entry_cost=Decimal("0"),
            position_size=Decimal("0"),
            avg_price=Decimal("0"),
            alert_thresholds=[90.0],
            actions=[mock_action],
        )
        watcher.on_event(_book_event(ASSET_ID, bids=[{"price": "0.10", "size": "1"}]))
        mock_action.execute.assert_not_called()
