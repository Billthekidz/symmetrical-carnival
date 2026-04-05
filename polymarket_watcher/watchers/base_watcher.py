"""Abstract base class for all event watchers.

How to add a new watcher
------------------------
1. Create a new module in ``polymarket_watcher/watchers/``.
2. Subclass :class:`BaseWatcher` and implement :meth:`on_event` and the
   ``name`` property.
3. Optionally implement ``supported_event_types`` to advertise which
   ``event_type`` values your watcher handles — the service uses this for
   routing optimisation but it is not mandatory.
4. Instantiate your watcher in ``service.py`` and append it to
   ``self._watchers``.

See ``ARCHITECTURE.md`` for the full extension guide.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, FrozenSet, Optional


class BaseWatcher(ABC):
    """Observes incoming market events and triggers actions when noteworthy.

    Each call to :meth:`on_event` receives one decoded JSON message from the
    Polymarket WebSocket channel.  Watchers are free to maintain internal
    state (e.g. a local order-book copy) across calls.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier, used in log messages."""

    @property
    def supported_event_types(self) -> Optional[FrozenSet[str]]:
        """Return the set of ``event_type`` strings this watcher handles.

        Return ``None`` (the default) to receive *all* events.  Returning a
        non-empty frozenset lets the dispatcher skip this watcher for
        irrelevant events.
        """
        return None

    @abstractmethod
    def on_event(self, event: dict[str, Any]) -> None:
        """Process one incoming WebSocket event.

        Parameters
        ----------
        event:
            Decoded JSON payload.  Always has an ``"event_type"`` key.
        """
