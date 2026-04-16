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
