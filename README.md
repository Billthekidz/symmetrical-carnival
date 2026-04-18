# symmetrical-carnival — Polymarket Order Book Watcher

A background long-running service that subscribes to the
[Polymarket](https://polymarket.com) CLOB WebSocket and monitors your open
positions for risk signals.  It ships two built-in watchers:

* **BidFloorWatcher** — alerts when the resting bid volume within a
  configurable window below your entry price falls below a safety multiple of
  your position size.
* **ValueWatcher** — fires one-shot escalating alerts as your position's
  current market value drops through configurable percentage thresholds.

Positions can be discovered automatically from a proxy wallet address, or
configured manually for a single market.

---

## Quick Start

### Prerequisites

- Python 3.12+
- `git`

### 1. Clone and install

```bash
git clone https://github.com/Billthekidz/symmetrical-carnival.git
cd symmetrical-carnival

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml` with the market and thresholds you want to watch:

```yaml
# Option A — auto-discover all open positions from your proxy wallet
account:
  proxy_wallet: ""   # e.g. "0xYourProxyWalletHere"

# Option B — manual config for a single market (used when proxy_wallet is empty)
market:
  slug: "will-trump-win-in-2024"   # Polymarket event slug
  direction: "yes"                  # "yes"/"long" or "no"/"short"
  entry_price: 0.72                 # avg entry price (0–1 scale)
  position_size: 100.0              # shares held

watcher:
  bid_floor:
    enabled: true
    safety_multiple: 10.0   # alert when bid platform < 10 × position size
    floor_window_pct: 10.0  # only count bids within 10% below entry price
  value:
    enabled: true
    alert_thresholds: [90.0, 80.0, 70.0, 60.0]  # % of entry cost remaining

service:
  log_level: "INFO"          # DEBUG | INFO | WARNING | ERROR
  reconnect_delay_sec: 5.0

actions:
  log:
    enabled: true            # logs alerts to stdout (extend with SMS/Discord/etc.)
```

See [`docs/configuration.md`](./docs/configuration.md) for the full reference.

### 3. Run

```bash
python -m polymarket_watcher config.yaml
```

---

## Admin CLI/TUI

Administer the service running on DigitalOcean from your local machine:

```bash
# Install admin deps on your local machine (not needed on the Droplet)
pip install -r requirements-admin.txt

# First-time setup — stores host in ~/.config/polymarket-watcher/admin.yaml
python -m polymarket_watcher.admin init

# Show service status
python -m polymarket_watcher.admin status

# Stream live logs (Ctrl+C to stop)
python -m polymarket_watcher.admin logs

# Edit remote config locally, validate, upload, then optionally restart
python -m polymarket_watcher.admin config edit

# Restart the service (prompts for confirmation)
python -m polymarket_watcher.admin restart
```

See [`docs/usage.md`](./docs/usage.md#admin-clitui) for remote setup
requirements (SSH key, journal group, sudoers).

---

## Run Tests

```bash
pytest tests/ -v
```

---

## Further Reading

| Topic | Document |
|---|---|
| Full configuration reference | [`docs/configuration.md`](./docs/configuration.md) |
| Deployment (systemd + DigitalOcean CI/CD) | [`docs/usage.md`](./docs/usage.md) |
| Documentation automation workflow | [`docs/usage.md#automated-documentation-updates`](./docs/usage.md#automated-documentation-updates) |
| Admin CLI/TUI (status, logs, config edit) | [`docs/usage.md#admin-clitui`](./docs/usage.md#admin-clitui) |
| Architecture, data flow & module map | [`docs/architecture.md`](./docs/architecture.md) |
| Adding watchers and actions | [`docs/extending.md`](./docs/extending.md) |
