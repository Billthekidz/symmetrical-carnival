# Configuration Reference

The service is configured via a YAML file (default: `config.yaml` in the
working directory).

## Sample `config.yaml`

```yaml
market:
  slug: "will-trump-win-in-2024"   # any Polymarket event slug
  direction: "yes"                  # "yes"/"long" or "no"/"short"

watcher:
  price_support:
    enabled: true
    threshold_pct: 5.0     # depth window as % of best bid
    alert_drop_pct: 20.0   # trigger when support drops by this %

service:
  log_level: "INFO"          # DEBUG | INFO | WARNING | ERROR
  reconnect_delay_sec: 5.0   # seconds to wait before reconnecting

actions:
  log:
    enabled: true   # placeholder — extend with SMS / Discord / etc.
```

## Configuration Sections

### `market`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slug` | string | `"will-trump-win-in-2024"` | Polymarket event URL slug |
| `direction` | string | `"yes"` | `"yes"`/`"long"` monitors YES token; `"no"`/`"short"` monitors NO token |

### `watcher.price_support`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable the price-support watcher |
| `threshold_pct` | float | `5.0` | Bids within this % of the best bid are counted as "support" |
| `alert_drop_pct` | float | `20.0` | Fire an alert when cumulative support drops by at least this % |

### `service`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `log_level` | string | `"INFO"` | Python logging level |
| `reconnect_delay_sec` | float | `5.0` | Seconds to wait after a WebSocket error before reconnecting |

### `actions`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `log.enabled` | bool | `true` | Log alert payloads to stdout via `LogAction` |
