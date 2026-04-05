"""Default action: log the event payload to the standard logger.

This acts as a placeholder that confirms the watcher pipeline is working.
Replace or supplement it with richer notification actions (SMS, Discord, etc.)
without touching any other module.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .base_action import BaseAction

logger = logging.getLogger(__name__)


class LogAction(BaseAction):
    """Writes a structured JSON payload to the application log.

    Severity level is WARNING so the message is visible even with a
    moderately restrictive log filter.
    """

    @property
    def name(self) -> str:
        return "LogAction"

    def execute(self, event_data: dict[str, Any]) -> None:  # noqa: D102
        logger.warning(
            "[ACTION] %s",
            json.dumps(event_data, indent=2, default=str),
        )
