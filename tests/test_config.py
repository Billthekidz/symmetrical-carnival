"""Unit tests for polymarket_watcher.config."""

from pathlib import Path

import pytest
import yaml

from polymarket_watcher.config import (
    AccountConfig,
    ActionsConfig,
    BidFloorConfig,
    Config,
    MarketConfig,
    ServiceConfig,
    ValueConfig,
    WatcherConfig,
)


class TestConfigDefaults:
    def test_default_market_slug(self) -> None:
        cfg = Config()
        assert cfg.market.slug == "will-trump-win-in-2024"

    def test_default_direction(self) -> None:
        cfg = Config()
        assert cfg.market.direction == "yes"

    def test_default_log_level(self) -> None:
        cfg = Config()
        assert cfg.service.log_level == "INFO"

    def test_default_reconnect_delay(self) -> None:
        cfg = Config()
        assert cfg.service.reconnect_delay_sec == 5.0

    def test_default_proxy_wallet_is_empty(self) -> None:
        cfg = Config()
        assert cfg.account.proxy_wallet == ""

    def test_default_bid_floor_enabled(self) -> None:
        cfg = Config()
        assert cfg.watcher.bid_floor.enabled is True

    def test_default_bid_floor_safety_multiple(self) -> None:
        cfg = Config()
        assert cfg.watcher.bid_floor.safety_multiple == 10.0

    def test_default_value_enabled(self) -> None:
        cfg = Config()
        assert cfg.watcher.value.enabled is True

    def test_default_value_alert_thresholds(self) -> None:
        cfg = Config()
        assert cfg.watcher.value.alert_thresholds == [90.0, 80.0, 70.0, 60.0]


class TestConfigFromYaml:
    def test_loads_market_slug_from_file(self, tmp_path: Path) -> None:
        data = {"market": {"slug": "election-2026", "direction": "no"}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.market.slug == "election-2026"
        assert cfg.market.direction == "no"

    def test_loads_service_settings(self, tmp_path: Path) -> None:
        data = {"service": {"log_level": "DEBUG", "reconnect_delay_sec": 15.0}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.service.log_level == "DEBUG"
        assert cfg.service.reconnect_delay_sec == 15.0

    def test_returns_defaults_when_file_missing(self, tmp_path: Path) -> None:
        cfg = Config.from_yaml(tmp_path / "nonexistent.yaml")
        assert cfg == Config()

    def test_handles_empty_yaml_file(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        cfg = Config.from_yaml(cfg_file)
        assert cfg == Config()

    def test_log_action_enabled_from_yaml(self, tmp_path: Path) -> None:
        data = {"actions": {"log": {"enabled": False}}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.actions.log_enabled is False

    def test_loads_proxy_wallet_from_yaml(self, tmp_path: Path) -> None:
        data = {"account": {"proxy_wallet": "0xDeAdBeEf"}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.account.proxy_wallet == "0xDeAdBeEf"

    def test_loads_bid_floor_settings(self, tmp_path: Path) -> None:
        data = {"watcher": {"bid_floor": {"enabled": False, "safety_multiple": 5.0}}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.watcher.bid_floor.enabled is False
        assert cfg.watcher.bid_floor.safety_multiple == 5.0

    def test_loads_value_settings(self, tmp_path: Path) -> None:
        data = {
            "watcher": {
                "value": {"enabled": True, "alert_thresholds": [80.0, 50.0]}
            }
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.watcher.value.enabled is True
        assert cfg.watcher.value.alert_thresholds == [80.0, 50.0]

    def test_loads_manual_entry_price_and_size(self, tmp_path: Path) -> None:
        data = {
            "market": {
                "slug": "some-market",
                "direction": "yes",
                "entry_price": 0.72,
                "position_size": 200.0,
            }
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.market.entry_price == pytest.approx(0.72)
        assert cfg.market.position_size == pytest.approx(200.0)


class TestMarketConfigDirectionValidation:
    @pytest.mark.parametrize("direction", ["yes", "no", "long", "short"])
    def test_valid_directions_accepted(self, direction: str) -> None:
        cfg = MarketConfig(slug="some-market", direction=direction)
        assert cfg.direction == direction

    @pytest.mark.parametrize("direction", ["YES", "No", "LONG", "Short"])
    def test_direction_normalised_to_lowercase(self, direction: str) -> None:
        cfg = MarketConfig(slug="some-market", direction=direction)
        assert cfg.direction == direction.lower()

    def test_direction_whitespace_stripped(self) -> None:
        cfg = MarketConfig(slug="some-market", direction="  yes  ")
        assert cfg.direction == "yes"

    @pytest.mark.parametrize("direction", ["yess", "up", "down", "", " "])
    def test_invalid_direction_raises(self, direction: str) -> None:
        with pytest.raises(ValueError, match="Invalid direction"):
            MarketConfig(slug="some-market", direction=direction)

    def test_invalid_direction_from_yaml_raises(self, tmp_path: Path) -> None:
        data = {"market": {"slug": "test-market", "direction": "maybe"}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        with pytest.raises(ValueError, match="Invalid direction"):
            Config.from_yaml(cfg_file)
