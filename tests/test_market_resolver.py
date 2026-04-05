"""Unit tests for polymarket_watcher.market_resolver."""

import json
from unittest.mock import MagicMock, patch

import pytest

from polymarket_watcher.market_resolver import get_token_ids_for_slug

YES_ID = "1111111111111111111111111111111111111111111111111111111111111111111111111111"
NO_ID  = "2222222222222222222222222222222222222222222222222222222222222222222222222222"


def _mock_response(markets: list) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = markets
    mock.raise_for_status.return_value = None
    return mock


# ──────────────────────────────────────────────────────────────────────────────


class TestGetTokenIdsForSlug:
    def test_returns_yes_no_pair_from_list_token_ids(self) -> None:
        market = {"clobTokenIds": [YES_ID, NO_ID]}
        with patch("polymarket_watcher.market_resolver.requests.get") as mock_get:
            mock_get.return_value = _mock_response([market])
            yes, no = get_token_ids_for_slug("some-slug")
        assert yes == YES_ID
        assert no == NO_ID

    def test_parses_json_string_token_ids(self) -> None:
        # The API sometimes returns clobTokenIds as a JSON-encoded string.
        market = {"clobTokenIds": json.dumps([YES_ID, NO_ID])}
        with patch("polymarket_watcher.market_resolver.requests.get") as mock_get:
            mock_get.return_value = _mock_response([market])
            yes, no = get_token_ids_for_slug("some-slug")
        assert yes == YES_ID
        assert no == NO_ID

    def test_raises_on_empty_market_list(self) -> None:
        with patch("polymarket_watcher.market_resolver.requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            with pytest.raises(ValueError, match="No market found"):
                get_token_ids_for_slug("nonexistent-slug")

    def test_raises_when_fewer_than_two_token_ids(self) -> None:
        market = {"clobTokenIds": [YES_ID]}
        with patch("polymarket_watcher.market_resolver.requests.get") as mock_get:
            mock_get.return_value = _mock_response([market])
            with pytest.raises(ValueError, match="Expected at least 2"):
                get_token_ids_for_slug("binary-only-one-token")

    def test_calls_gamma_api_with_correct_params(self) -> None:
        market = {"clobTokenIds": [YES_ID, NO_ID]}
        with patch("polymarket_watcher.market_resolver.requests.get") as mock_get:
            mock_get.return_value = _mock_response([market])
            get_token_ids_for_slug("my-slug")

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["slug"] == "my-slug"
