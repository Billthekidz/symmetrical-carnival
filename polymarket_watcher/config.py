"""Configuration loading from a YAML file with safe defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_VALID_DIRECTIONS = frozenset({"yes", "long", "no", "short"})

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class AccountConfig:
    """Wallet settings for auto-discovering positions."""

    # Polymarket proxy wallet address.  When non-empty the service fetches all
    # open positions from the Data API and creates watchers automatically.
    proxy_wallet: str = ""


@dataclass
class MarketConfig:
    """Settings that identify the market and direction to watch.

    Used as a manual fallback when ``AccountConfig.proxy_wallet`` is empty.
    """

    slug: str = "will-trump-win-in-2024"
    direction: str = "yes"  # "yes"/"long" or "no"/"short"
    entry_price: float = 0.0   # average entry price (0–1); 0 means unknown
    position_size: float = 0.0  # number of shares held; 0 means unknown

    def __post_init__(self) -> None:
        self.direction = self.direction.strip().lower()
        if self.direction not in _VALID_DIRECTIONS:
            raise ValueError(
                f"Invalid direction {self.direction!r}. "
                f"Must be one of: {sorted(_VALID_DIRECTIONS)}"
            )


@dataclass
class BidFloorConfig:
    """Tuning knobs for the bid-floor (support safety) watcher."""

    enabled: bool = True
    # Alert when total bid volume at-or-below the entry price falls below
    # ``safety_multiple × position_size``.
    safety_multiple: float = 10.0


@dataclass
class ValueConfig:
    """Tuning knobs for the value (panic level) watcher."""

    enabled: bool = True
    # Percentage-of-entry-cost thresholds at which to fire a one-shot alert.
    alert_thresholds: list[float] = field(
        default_factory=lambda: [90.0, 80.0, 70.0, 60.0]
    )


@dataclass
class WatcherConfig:
    """Container for all watcher sub-configurations."""

    bid_floor: BidFloorConfig = field(default_factory=BidFloorConfig)
    value: ValueConfig = field(default_factory=ValueConfig)


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

    account: AccountConfig = field(default_factory=AccountConfig)
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

        account_data = data.get("account", {})
        market_data = data.get("market", {})
        watcher_data = data.get("watcher", {})
        service_data = data.get("service", {})
        actions_data = data.get("actions", {})

        bf_data = watcher_data.get("bid_floor", {})
        val_data = watcher_data.get("value", {})

        return cls(
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
