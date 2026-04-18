"""Discord outbound webhook integration.

This module owns all vendor-specific details: payload shape, HTTP transport,
and error handling.  It is intentionally free of the ``BaseAction`` protocol
so that it can be tested and reused independently.

The public surface is a single function:

    send_webhook(webhook_url, event_data)

Consumers should go through ``polymarket_watcher.actions.discord_action``
rather than calling this module directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Discord caps message content at 2 000 characters; stay well under that.
_MAX_CONTENT_CHARS = 1800

# Timeout for the outbound HTTP request (connect, read).
_REQUEST_TIMEOUT = (5, 10)


def _build_content(event_data: dict[str, Any]) -> str:
    """Render *event_data* as a compact Discord message string."""
    watcher = event_data.get("watcher", "Unknown watcher")
    header = f"\u26a0\ufe0f **{watcher}** alert"
    body = json.dumps(event_data, indent=2, default=str)
    message = f"{header}\n```json\n{body}\n```"
    if len(message) > _MAX_CONTENT_CHARS:
        # Truncate the JSON body to fit within Discord's limit.
        truncated = body[: _MAX_CONTENT_CHARS - len(header) - 30]
        message = f"{header}\n```json\n{truncated}\n… (truncated)\n```"
    return message


def send_webhook(webhook_url: str, event_data: dict[str, Any]) -> None:
    """POST *event_data* as a Discord message to *webhook_url*.

    Failures are logged as errors but never re-raised so that a transient
    Discord outage cannot crash the watcher service.

    Parameters
    ----------
    webhook_url:
        The full Discord incoming webhook URL
        (``https://discord.com/api/webhooks/<id>/<token>``).
    event_data:
        Structured alert payload produced by a watcher.
    """
    content = _build_content(event_data)
    payload = {"content": content}

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        logger.debug("Discord webhook delivered (HTTP %s).", response.status_code)
    except requests.exceptions.Timeout:
        logger.error("Discord webhook timed out — alert not delivered.")
    except requests.exceptions.RequestException as exc:
        logger.error("Discord webhook failed: %s", exc)
