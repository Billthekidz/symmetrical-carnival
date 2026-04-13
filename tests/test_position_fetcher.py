"""Unit tests for polymarket_watcher.position_fetcher."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from polymarket_watcher.position_fetcher import Position, fetch_positions

WALLET = "0xDeAdBeEf1234"

_SAMPLE_API_RESPONSE = [
    {
        "asset": "token-yes-abc",
        "outcome": "Yes",
        "size": "150.0",
        "avgPrice": "0.72",
        "curPrice": "0.68",
        "title": "Will X happen?",
        "market": {"slug": "will-x-happen"},
    },
    {
        "asset": "token-no-def",
        "outcome": "No",
        "size": "50.0",
        "avgPrice": "0.30",
        "curPrice": "0.25",
        "title": "Will Y happen?",
        "market": {"slug": "will-y-happen"},
    },
    # Zero-size position — should be filtered out.
    {
        "asset": "token-zero",
        "outcome": "Yes",
        "size": "0",
        "avgPrice": "0.50",
        "curPrice": "0.50",
        "title": "Closed market",
        "market": {"slug": "closed-market"},
    },
    # Negative size — should be filtered out.
    {
        "asset": "token-neg",
        "outcome": "Yes",
        "size": "-1.0",
        "avgPrice": "0.50",
        "curPrice": "0.50",
        "title": "Weird market",
        "market": {"slug": "weird-market"},
    },
    # curPrice == 0 — resolved/lost market, should be filtered out.
    {
        "asset": "token-lost",
        "outcome": "Yes",
        "size": "200.0",
        "avgPrice": "0.60",
        "curPrice": "0",
        "title": "Lost market",
        "market": {"slug": "lost-market"},
    },
]


def _mock_response(data: list) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


# ──────────────────────────────────────────────────────────────────────────────


class TestFetchPositionsFiltering:
    def test_zero_size_positions_excluded(self) -> None:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_SAMPLE_API_RESPONSE)
            positions = fetch_positions(WALLET)

        asset_ids = [p.asset_id for p in positions]
        assert "token-zero" not in asset_ids
        assert "token-neg" not in asset_ids

    def test_concluded_positions_excluded(self) -> None:
        """Positions with curPrice == 0 (resolved/lost) must be filtered out."""
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_SAMPLE_API_RESPONSE)
            positions = fetch_positions(WALLET)

        asset_ids = [p.asset_id for p in positions]
        assert "token-lost" not in asset_ids

    def test_returns_only_positive_size_positions(self) -> None:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_SAMPLE_API_RESPONSE)
            positions = fetch_positions(WALLET)

        assert len(positions) == 2

    def test_empty_api_response_returns_empty_list(self) -> None:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            positions = fetch_positions(WALLET)

        assert positions == []


class TestFetchPositionsFields:
    def _get_positions(self) -> list[Position]:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_SAMPLE_API_RESPONSE)
            return fetch_positions(WALLET)

    def test_asset_id_mapped_correctly(self) -> None:
        positions = self._get_positions()
        assert positions[0].asset_id == "token-yes-abc"
        assert positions[1].asset_id == "token-no-def"

    def test_direction_normalised_to_uppercase(self) -> None:
        positions = self._get_positions()
        assert positions[0].direction == "YES"
        assert positions[1].direction == "NO"

    def test_size_parsed_as_decimal(self) -> None:
        positions = self._get_positions()
        assert positions[0].size == Decimal("150.0")
        assert positions[1].size == Decimal("50.0")

    def test_avg_price_parsed_as_decimal(self) -> None:
        positions = self._get_positions()
        assert positions[0].avg_price == Decimal("0.72")
        assert positions[1].avg_price == Decimal("0.30")

    def test_entry_cost_computed_correctly(self) -> None:
        positions = self._get_positions()
        # 0.72 × 150 = 108.0
        assert positions[0].entry_cost == Decimal("0.72") * Decimal("150.0")
        # 0.30 × 50 = 15.0
        assert positions[1].entry_cost == Decimal("0.30") * Decimal("50.0")

    def test_slug_extracted_from_market_dict(self) -> None:
        positions = self._get_positions()
        assert positions[0].slug == "will-x-happen"
        assert positions[1].slug == "will-y-happen"


class TestFetchPositionsCurPriceFilter:
    """curPrice == 0 means the market resolved as a loss — must be skipped."""

    def test_cur_price_zero_excluded(self) -> None:
        data = [
            {
                "asset": "token-active",
                "outcome": "Yes",
                "size": "100.0",
                "avgPrice": "0.50",
                "curPrice": "0.55",
                "title": "Active market",
                "market": {"slug": "active-market"},
            },
            {
                "asset": "token-resolved-loss",
                "outcome": "Yes",
                "size": "80.0",
                "avgPrice": "0.60",
                "curPrice": "0",
                "title": "Lost market",
                "market": {"slug": "lost-market"},
            },
        ]
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response(data)
            positions = fetch_positions(WALLET)

        assert len(positions) == 1
        assert positions[0].asset_id == "token-active"

    def test_cur_price_missing_treated_as_active(self) -> None:
        """If curPrice is absent the position is treated as active (safe default)."""
        data = [
            {
                "asset": "token-no-cur-price",
                "outcome": "Yes",
                "size": "50.0",
                "avgPrice": "0.40",
                "title": "No curPrice field",
                "market": {"slug": "no-cur-price"},
            },
        ]
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response(data)
            positions = fetch_positions(WALLET)

        assert len(positions) == 1
        assert positions[0].asset_id == "token-no-cur-price"


class TestFetchPositionsApiCall:
    def test_calls_correct_url(self) -> None:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            fetch_positions(WALLET)

        call_args = mock_get.call_args
        assert "data-api.polymarket.com/positions" in call_args[0][0]

    def test_passes_user_param(self) -> None:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            fetch_positions(WALLET)

        params = mock_get.call_args[1]["params"]
        assert params["user"] == WALLET

    def test_raises_for_http_error(self) -> None:
        with patch("polymarket_watcher.position_fetcher.requests.get") as mock_get:
            mock = MagicMock()
            mock.raise_for_status.side_effect = Exception("HTTP 500")
            mock_get.return_value = mock

            with pytest.raises(Exception, match="HTTP 500"):
                fetch_positions(WALLET)
