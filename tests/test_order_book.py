"""Unit tests for polymarket_watcher.order_book."""

from decimal import Decimal

import pytest

from polymarket_watcher.order_book import OrderBook, OrderLevel


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def empty_book() -> OrderBook:
    return OrderBook(asset_id="test-asset")


@pytest.fixture()
def populated_book() -> OrderBook:
    book = OrderBook(asset_id="test-asset")
    book.apply_book_snapshot(
        bids=[
            {"price": "0.50", "size": "100"},
            {"price": "0.48", "size": "200"},
            {"price": "0.45", "size": "150"},
        ],
        asks=[
            {"price": "0.52", "size": "80"},
            {"price": "0.55", "size": "120"},
        ],
    )
    return book


# ──────────────────────────────────────────────────────────────────────────────
# Snapshot
# ──────────────────────────────────────────────────────────────────────────────


class TestApplyBookSnapshot:
    def test_bids_sorted_descending(self, populated_book: OrderBook) -> None:
        prices = [lv.price for lv in populated_book.bids]
        assert prices == sorted(prices, reverse=True)

    def test_asks_sorted_ascending(self, populated_book: OrderBook) -> None:
        prices = [lv.price for lv in populated_book.asks]
        assert prices == sorted(prices)

    def test_best_bid(self, populated_book: OrderBook) -> None:
        assert populated_book.best_bid() == Decimal("0.50")

    def test_best_ask(self, populated_book: OrderBook) -> None:
        assert populated_book.best_ask() == Decimal("0.52")

    def test_snapshot_replaces_previous_state(self, populated_book: OrderBook) -> None:
        populated_book.apply_book_snapshot(
            bids=[{"price": "0.60", "size": "50"}],
            asks=[],
        )
        assert len(populated_book.bids) == 1
        assert populated_book.best_bid() == Decimal("0.60")
        assert populated_book.asks == []

    def test_empty_book_returns_none_best(self, empty_book: OrderBook) -> None:
        assert empty_book.best_bid() is None
        assert empty_book.best_ask() is None


# ──────────────────────────────────────────────────────────────────────────────
# Incremental updates
# ──────────────────────────────────────────────────────────────────────────────


class TestApplyPriceChange:
    def test_add_new_bid_level(self, populated_book: OrderBook) -> None:
        populated_book.apply_price_change("0.49", "75", "BUY")
        prices = [lv.price for lv in populated_book.bids]
        assert Decimal("0.49") in prices

    def test_remove_bid_level_when_size_zero(
        self, populated_book: OrderBook
    ) -> None:
        populated_book.apply_price_change("0.50", "0", "BUY")
        prices = [lv.price for lv in populated_book.bids]
        assert Decimal("0.50") not in prices

    def test_update_existing_bid_level(self, populated_book: OrderBook) -> None:
        populated_book.apply_price_change("0.48", "999", "BUY")
        level = next(
            lv for lv in populated_book.bids if lv.price == Decimal("0.48")
        )
        assert level.size == Decimal("999")

    def test_add_ask_level(self, populated_book: OrderBook) -> None:
        populated_book.apply_price_change("0.53", "60", "SELL")
        prices = [lv.price for lv in populated_book.asks]
        assert Decimal("0.53") in prices

    def test_remove_ask_level_when_size_zero(
        self, populated_book: OrderBook
    ) -> None:
        populated_book.apply_price_change("0.52", "0", "SELL")
        prices = [lv.price for lv in populated_book.asks]
        assert Decimal("0.52") not in prices

    def test_bids_remain_sorted_after_update(
        self, populated_book: OrderBook
    ) -> None:
        populated_book.apply_price_change("0.49", "50", "BUY")
        prices = [lv.price for lv in populated_book.bids]
        assert prices == sorted(prices, reverse=True)

    def test_invalid_side_raises(self, populated_book: OrderBook) -> None:
        with pytest.raises(ValueError, match="Unexpected order-book side"):
            populated_book.apply_price_change("0.50", "10", "INVALID")


# ──────────────────────────────────────────────────────────────────────────────
# Price-support calculation
# ──────────────────────────────────────────────────────────────────────────────


class TestBidSupportWithinPct:
    def test_full_support_within_window(self, populated_book: OrderBook) -> None:
        # best_bid = 0.50; 5 % window → floor = 0.475
        # Bids at 0.50 (100) and 0.48 (200) qualify; 0.45 does not.
        support = populated_book.bid_support_within_pct(5.0)
        assert support == Decimal("300")

    def test_zero_pct_only_best_bid(self, populated_book: OrderBook) -> None:
        # Only bids exactly at best_bid count.
        support = populated_book.bid_support_within_pct(0.0)
        assert support == Decimal("100")

    def test_large_pct_includes_all_bids(self, populated_book: OrderBook) -> None:
        support = populated_book.bid_support_within_pct(100.0)
        assert support == Decimal("450")  # 100 + 200 + 150

    def test_empty_book_returns_zero(self, empty_book: OrderBook) -> None:
        assert empty_book.bid_support_within_pct(5.0) == Decimal("0")


class TestBidVolumeAtOrBelow:
    def test_includes_bids_exactly_at_price(
        self, populated_book: OrderBook
    ) -> None:
        # Bids: 0.50 (100), 0.48 (200), 0.45 (150)
        # At-or-below 0.50 → 100 + 200 + 150 = 450
        volume = populated_book.bid_volume_at_or_below(Decimal("0.50"))
        assert volume == Decimal("450")

    def test_excludes_bids_above_price(self, populated_book: OrderBook) -> None:
        # At-or-below 0.48 → 200 + 150 = 350  (0.50 level excluded)
        volume = populated_book.bid_volume_at_or_below(Decimal("0.48"))
        assert volume == Decimal("350")

    def test_excludes_all_bids_when_price_below_lowest(
        self, populated_book: OrderBook
    ) -> None:
        volume = populated_book.bid_volume_at_or_below(Decimal("0.40"))
        assert volume == Decimal("0")

    def test_includes_all_bids_when_price_above_all(
        self, populated_book: OrderBook
    ) -> None:
        volume = populated_book.bid_volume_at_or_below(Decimal("0.99"))
        assert volume == Decimal("450")  # 100 + 200 + 150

    def test_empty_book_returns_zero(self, empty_book: OrderBook) -> None:
        assert empty_book.bid_volume_at_or_below(Decimal("0.50")) == Decimal("0")
