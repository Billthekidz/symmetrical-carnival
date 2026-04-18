# Configuration Reference

The service is configured via a YAML file (default: `config.yaml` in the
working directory).

## Sample `config.yaml`

```yaml
# Option A — auto-discover all open positions from your proxy wallet.
# When proxy_wallet is non-empty the [market] section is ignored.
account:
  proxy_wallet: ""   # e.g. "0xYourProxyWalletHere"

# Option B — manual fallback for a single market (used when proxy_wallet is empty).
market:
  slug: "will-trump-win-in-2024"   # any Polymarket event slug
  direction: "yes"                  # "yes"/"long" or "no"/"short"
  entry_price: 0.72                 # average entry price (0–1); 0 means unknown
  position_size: 100.0              # shares held; 0 means unknown

watcher:
  bid_floor:
    enabled: true
    safety_multiple: 10.0   # alert when platform volume < 10 × position size
    floor_window_pct: 10.0  # only count bids within 10% below entry price

  value:
    enabled: true
    alert_thresholds: [90.0, 80.0, 70.0, 60.0]   # % of entry cost remaining

service:
  log_level: "INFO"          # DEBUG | INFO | WARNING | ERROR
  reconnect_delay_sec: 5.0   # seconds to wait before reconnecting

actions:
  log:
    enabled: true   # placeholder — extend with SMS / Discord / etc.

  # Discord outbound webhook — URL is injected from secrets.env, not stored here.
  discord:
    enabled: false
```

## Configuration Sections

### `account`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `proxy_wallet` | string | `""` | Polymarket proxy wallet address. When non-empty, positions are fetched automatically from the Data API and the `[market]` section is ignored. |

### `market`

Used only when `account.proxy_wallet` is empty.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slug` | string | `"will-trump-win-in-2024"` | Polymarket event URL slug |
| `direction` | string | `"yes"` | `"yes"`/`"long"` monitors YES token; `"no"`/`"short"` monitors NO token |
| `entry_price` | float | `0.0` | Average entry price (0–1 scale). Required for position-aware watchers. |
| `position_size` | float | `0.0` | Number of shares held. Required for position-aware watchers. |

### `watcher.bid_floor`

Monitors whether the total resting bid volume within a window below the entry
price remains at least `safety_multiple × position_size`.  Fires when the
ratio drops below the threshold, then re-arms once it recovers.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable the bid-floor watcher |
| `safety_multiple` | float | `10.0` | Minimum ratio of platform bid volume to position size |
| `floor_window_pct` | float | `10.0` | Only count bids within this % below the entry price as support |

### `watcher.value`

Tracks a position's current market value (`best_bid × position_size`) as a
percentage of its entry cost (`avg_price × position_size`).  Fires a one-shot
alert each time the value drops through a configured threshold (thresholds do
not re-arm).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable the value watcher |
| `alert_thresholds` | list[float] | `[90.0, 80.0, 70.0, 60.0]` | Value-retention percentages at which to fire alerts |

### `service`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `log_level` | string | `"INFO"` | Python logging level |
| `reconnect_delay_sec` | float | `5.0` | Seconds to wait after a WebSocket error before reconnecting |

### `actions`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `log.enabled` | bool | `true` | Log alert payloads to stdout via `LogAction` |
| `discord.enabled` | bool | `false` | Send alerts to Discord via an outbound webhook |

#### Discord alerts

When `actions.discord.enabled` is `true` the service reads the webhook URL from
the `DISCORD_WEBHOOK_URL` environment variable.  **The URL is never stored in
`config.yaml`.**  It is injected at runtime by systemd via the `EnvironmentFile`
directive — see [Secrets management](#secrets-management) below.

---

## Secrets management

Sensitive values (currently only `DISCORD_WEBHOOK_URL`) are kept in a dedicated
secrets file that is **never committed to version control**:

```
/etc/polymarket-watcher/secrets.env
```

The repository ships a template — `secrets.env.example` — that you copy and
populate:

```bash
sudo install -o root -g polymarket-watcher -m 0640 \
    secrets.env.example /etc/polymarket-watcher/secrets.env
sudo nano /etc/polymarket-watcher/secrets.env   # fill in real values
```

The systemd unit loads the file automatically via:

```ini
EnvironmentFile=-/etc/polymarket-watcher/secrets.env
```

The leading `-` means systemd silently skips the directive if the file does not
exist, so the service still starts when Discord alerts are disabled.

### Why not `config.yaml`?

`config.yaml` is safe to commit as a template (it contains tuning knobs, not
secrets).  Keeping credentials in a separate file with tighter permissions
(`0640`, root-owned) means:

- `config.yaml` can be stored in version control without redaction.
- Credentials have a different rotation cadence from operational config.
- If `config.yaml` is accidentally shared, no secret is exposed.

### Why not GitHub Secrets?

GitHub Secrets are only injected during GitHub Actions workflow runs — they are
not available to the running systemd service.  Adding env-var injection via the
deploy pipeline would require extra complexity (writing an env file from CI,
managing secret rotation across two systems) for no benefit given the current
single-Droplet setup.  Use the `EnvironmentFile` approach instead.
