# Extending the Service

## How to Add a New Watcher

1. **Create a module** in `polymarket_watcher/watchers/`, e.g.
   `smart_money_watcher.py`.

2. **Subclass `BaseWatcher`**:

   ```python
   from ..watchers.base_watcher import BaseWatcher
   from typing import Any, FrozenSet

   class SmartMoneyWatcher(BaseWatcher):
       supported_event_types: FrozenSet[str] = frozenset({"price_change"})

       @property
       def name(self) -> str:
           return "SmartMoneyWatcher"

       def on_event(self, event: dict[str, Any]) -> None:
           # Inspect the event and fire actions if relevant.
           ...
   ```

3. **Add configuration** (optional) — add a new dataclass to `config.py` and
   a matching YAML key in `config.yaml`.

4. **Register the watcher** — inside `WatcherService._build_watchers()` in
   `service.py`, instantiate and append your watcher:

   ```python
   if cfg.watcher.smart_money.enabled:
       watchers.append(SmartMoneyWatcher(..., actions=actions))
   ```

That's it — no other file needs to change.

---

## How to Add a New Action

1. **Create a module** in `polymarket_watcher/actions/`, e.g.
   `discord_action.py`.

2. **Subclass `BaseAction`**:

   ```python
   import httpx
   from .base_action import BaseAction
   from typing import Any

   class DiscordAction(BaseAction):
       def __init__(self, webhook_url: str) -> None:
           self._webhook_url = webhook_url

       @property
       def name(self) -> str:
           return "DiscordAction"

       def execute(self, event_data: dict[str, Any]) -> None:
           content = f"🚨 **{event_data['watcher']}** alert\n```json\n{event_data}\n```"
           httpx.post(self._webhook_url, json={"content": content})
   ```

3. **Wire the action** — in `WatcherService._build_watchers()`, add it to the
   `actions` list:

   ```python
   actions = [LogAction(), DiscordAction(webhook_url=cfg.actions.discord.webhook_url)]
   ```
