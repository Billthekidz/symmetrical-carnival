"""Unit tests for polymarket_watcher.config."""

from pathlib import Path

import pytest
import yaml

from polymarket_watcher.config import (
    ActionsConfig,
    Config,
    MarketConfig,
    PriceSupportConfig,
    ServiceConfig,
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

    def test_default_price_support_enabled(self) -> None:
        cfg = Config()
        assert cfg.watcher.price_support.enabled is True

    def test_default_alert_drop_pct(self) -> None:
        cfg = Config()
        assert cfg.watcher.price_support.alert_drop_pct == 20.0


class TestConfigFromYaml:
    def test_loads_market_slug_from_file(self, tmp_path: Path) -> None:
        data = {"market": {"slug": "election-2026", "direction": "no"}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.market.slug == "election-2026"
        assert cfg.market.direction == "no"

    def test_loads_price_support_settings(self, tmp_path: Path) -> None:
        data = {
            "watcher": {
                "price_support": {
                    "enabled": False,
                    "threshold_pct": 2.5,
                    "alert_drop_pct": 10.0,
                }
            }
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = Config.from_yaml(cfg_file)
        assert cfg.watcher.price_support.enabled is False
        assert cfg.watcher.price_support.threshold_pct == 2.5
        assert cfg.watcher.price_support.alert_drop_pct == 10.0

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
