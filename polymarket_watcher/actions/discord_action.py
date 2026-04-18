"""Slim action wrapper for Discord outbound webhook alerts.

This module is the public interface that ``service.py`` and any future code
should import.  All vendor-specific HTTP logic lives in
``polymarket_watcher.integrations.discord``; this class only handles
configuration reading and delegation.

The webhook URL is read from the ``DISCORD_WEBHOOK_URL`` environment variable
(injected via the systemd ``EnvironmentFile`` — see
``/etc/polymarket-watcher/secrets.env``).  It is **not** stored in
``config.yaml``, which keeps the config file safe to version-control.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .base_action import BaseAction
from ..integrations import discord as _discord_integration

logger = logging.getLogger(__name__)

_ENV_VAR = "DISCORD_WEBHOOK_URL"


class DiscordAction(BaseAction):
    """Sends an alert to a Discord channel via an incoming webhook.

    The webhook URL must be supplied through the ``DISCORD_WEBHOOK_URL``
    environment variable.  Raises :class:`EnvironmentError` at construction
    time if the variable is absent or empty so that misconfiguration is caught
    on startup rather than silently at alert time.
    """

    def __init__(self) -> None:
        webhook_url = os.environ.get(_ENV_VAR, "").strip()
        if not webhook_url:
            raise EnvironmentError(
                f"Discord action is enabled but {_ENV_VAR!r} is not set. "
                "Add it to /etc/polymarket-watcher/secrets.env and restart the service."
            )
        self._webhook_url = webhook_url

    @property
    def name(self) -> str:  # noqa: D102
        return "DiscordAction"

    def execute(self, event_data: dict[str, Any]) -> None:  # noqa: D102
        _discord_integration.send_webhook(self._webhook_url, event_data)
