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

New notification channels follow a two-layer pattern that keeps vendor-specific
HTTP/protocol logic separate from the action protocol used by the rest of the
codebase:

| Layer | Location | Responsibility |
|---|---|---|
| Integration module | `polymarket_watcher/integrations/<vendor>.py` | All vendor HTTP details: payload shape, retries, error handling |
| Action wrapper | `polymarket_watcher/actions/<vendor>_action.py` | Subclasses `BaseAction`; reads config/env; delegates to the integration |

### Example: Discord webhook action (already implemented)

**Step 1 — Integration module** (`polymarket_watcher/integrations/discord.py`)

Owns everything Discord-specific: building the message content, POSTing to the
webhook URL, and handling transport errors without crashing the service.

**Step 2 — Action wrapper** (`polymarket_watcher/actions/discord_action.py`)

A thin `DiscordAction(BaseAction)` subclass.  Its `__init__` reads
`DISCORD_WEBHOOK_URL` from the environment (injected via the systemd
`EnvironmentFile`) and raises `EnvironmentError` on startup if it is missing,
so misconfiguration is caught immediately.  `execute(event_data)` simply calls
`integrations.discord.send_webhook(webhook_url, event_data)`.

**Step 3 — Config toggle** (`config.py` + `config.yaml`)

Add an `enabled` boolean under `actions`:

```yaml
actions:
  discord:
    enabled: true
```

**Step 4 — Wire in `service.py`**

```python
if cfg.actions.discord.enabled:
    actions.append(DiscordAction())
```

### Adding a brand-new integration (e.g. Telegram)

1. Create `polymarket_watcher/integrations/telegram.py` with a `send_message(token, chat_id, event_data)` function.
2. Create `polymarket_watcher/actions/telegram_action.py` — subclass `BaseAction`, read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from env, delegate to step 1.
3. Add `TelegramActionConfig(enabled: bool = False)` to `config.py` and a matching YAML key.
4. Add `TELEGRAM_BOT_TOKEN=…` and `TELEGRAM_CHAT_ID=…` to `/etc/polymarket-watcher/secrets.env`.
5. Wire the action in `service.py`.
