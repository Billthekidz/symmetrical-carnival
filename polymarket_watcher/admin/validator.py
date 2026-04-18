"""Config validation logic — click-free.

This module can be imported without click being installed, making it safe to
use from tests and core code that do not depend on the CLI layer.
"""

from __future__ import annotations

import yaml


class ConfigValidationError(ValueError):
    """Raised when a service config file cannot be parsed or fails schema checks."""


def validate_service_config(yaml_text: str) -> None:
    """Parse *yaml_text* and instantiate Config dataclasses to validate it.

    Raises :class:`ConfigValidationError` on any error so callers that do not
    depend on click can catch a plain exception.  The CLI wrapper in
    ``cli.py`` re-raises this as a ``click.ClickException``.
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"YAML parse error: {exc}") from exc

    # Re-use the existing service Config dataclasses for schema validation
    try:
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

        market_data = data.get("market", {})
        watcher_data = data.get("watcher", {})
        service_data = data.get("service", {})
        actions_data = data.get("actions", {})
        account_data = data.get("account", {})
        bf_data = watcher_data.get("bid_floor", {})
        val_data = watcher_data.get("value", {})

        Config(
            account=AccountConfig(**account_data),
            market=MarketConfig(**market_data),
            watcher=WatcherConfig(
                bid_floor=BidFloorConfig(**bf_data),
                value=ValueConfig(**val_data),
            ),
            service=ServiceConfig(**service_data),
            actions=ActionsConfig(
                log_enabled=actions_data.get("log", {}).get("enabled", True)
            ),
        )
    except Exception as exc:
        raise ConfigValidationError(f"Config validation failed: {exc}") from exc
