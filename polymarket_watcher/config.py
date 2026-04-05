"""Configuration loading from a YAML file with safe defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class MarketConfig:
    """Settings that identify the market and direction to watch."""

    slug: str = "will-trump-win-in-2024"
    direction: str = "yes"  # "yes"/"long" or "no"/"short"


@dataclass
class PriceSupportConfig:
    """Tuning knobs for the price-support watcher."""

    enabled: bool = True
    # Bids whose price is within this many percent of the best bid count as
    # "supporting" the current price level.
    threshold_pct: float = 5.0
    # Trigger an alert when total support drops by at least this percentage.
    alert_drop_pct: float = 20.0


@dataclass
class WatcherConfig:
    """Container for all watcher sub-configurations."""

    price_support: PriceSupportConfig = field(default_factory=PriceSupportConfig)


@dataclass
class ServiceConfig:
    """Operational settings for the long-running service."""

    log_level: str = "INFO"
    reconnect_delay_sec: float = 5.0


@dataclass
class ActionsConfig:
    """Toggle individual notification actions."""

    log_enabled: bool = True


@dataclass
class Config:
    """Root configuration object."""

    market: MarketConfig = field(default_factory=MarketConfig)
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    service: ServiceConfig = field(default_factory=ServiceConfig)
    actions: ActionsConfig = field(default_factory=ActionsConfig)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from *path*, falling back to ``config.yaml``."""
        resolved = path or DEFAULT_CONFIG_PATH
        if not resolved.exists():
            return cls()

        with open(resolved) as fh:
            data = yaml.safe_load(fh) or {}

        market_data = data.get("market", {})
        watcher_data = data.get("watcher", {})
        service_data = data.get("service", {})
        actions_data = data.get("actions", {})

        ps_data = watcher_data.get("price_support", {})

        return cls(
            market=MarketConfig(**market_data),
            watcher=WatcherConfig(price_support=PriceSupportConfig(**ps_data)),
            service=ServiceConfig(**service_data),
            actions=ActionsConfig(
                log_enabled=actions_data.get("log", {}).get("enabled", True)
            ),
        )
