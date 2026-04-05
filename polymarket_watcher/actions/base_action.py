"""Abstract base class for all notification actions.

How to add a new action
-----------------------
1. Create a new module in ``polymarket_watcher/actions/``.
2. Subclass :class:`BaseAction` and implement :meth:`execute` and the
   ``name`` property.
3. Instantiate your action in ``service.py`` and include it in the list
   passed to any watcher that should use it.

Example future actions: SMS via Twilio, Discord webhook, Telegram bot, PagerDuty alert.

See ``ARCHITECTURE.md`` for the full extension guide.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAction(ABC):
    """Executed when a watcher determines that an event warrants notification.

    Actions are intentionally decoupled from watchers: the same action
    instance can be shared across multiple watchers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier, used in log messages."""

    @abstractmethod
    def execute(self, event_data: dict[str, Any]) -> None:
        """Perform the notification or side-effect.

        Parameters
        ----------
        event_data:
            A dictionary describing the event.  Keys and values depend on the
            watcher that triggered the action.
        """
