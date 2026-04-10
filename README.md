# symmetrical-carnival — Polymarket Order Book Watcher

A background long-running service that subscribes to the
[Polymarket](https://polymarket.com) CLOB WebSocket and monitors changes in
**price support** (bid-side liquidity depth) for a configurable market and
direction (YES / long or NO / short).

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
market:
  slug: "will-trump-win-in-2024"   # Polymarket event slug
  direction: "yes"                  # "yes"/"long" or "no"/"short"

watcher:
  price_support:
    enabled: true
    threshold_pct: 5.0     # bids within this % of best bid count as support
    alert_drop_pct: 20.0   # fire alert when support drops by this %

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

# Stream live logs (press q to quit)
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
| Admin CLI/TUI (status, logs, config edit) | [`docs/usage.md#admin-clitui`](./docs/usage.md#admin-clitui) |
| Architecture, data flow & module map | [`docs/architecture.md`](./docs/architecture.md) |
| Adding watchers and actions | [`docs/extending.md`](./docs/extending.md) |