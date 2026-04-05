# symmetrical-carnival — Polymarket Order Book Watcher

A background long-running service that subscribes to the
[Polymarket](https://polymarket.com) CLOB WebSocket and monitors changes in
**price support** (bid-side liquidity depth) for a configurable market and
direction (YES / long or NO / short).

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the market to watch

Copy and edit `config.yaml`:

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
  log_level: "INFO"
  reconnect_delay_sec: 5.0

actions:
  log:
    enabled: true   # placeholder — extend with SMS / Discord / etc.
```

### 3. Run

```bash
python -m polymarket_watcher config.yaml
```

---

## Project Layout

```
polymarket_watcher/        ← Python package
├── config.py              ← YAML-driven configuration dataclasses
├── market_resolver.py     ← slug → YES/NO token IDs (Gamma REST API)
├── order_book.py          ← local order-book state + price-support maths
├── websocket_client.py    ← auto-reconnecting WebSocket client
├── service.py             ← orchestrator
├── main.py                ← entry point / signal handling
├── watchers/
│   ├── base_watcher.py          ← abstract BaseWatcher
│   └── price_support_watcher.py ← monitors bid-side support drop
└── actions/
    ├── base_action.py    ← abstract BaseAction
    └── log_action.py     ← default: log alert to stdout
tests/                     ← unit tests (pytest)
config.yaml                ← sample configuration
polymarket-watcher.service ← systemd unit file
ARCHITECTURE.md            ← Mermaid diagram + extension guide
```

---

## Run Tests

```bash
pytest tests/ -v
```

---

## systemd Service (Linux)

See [`polymarket-watcher.service`](./polymarket-watcher.service) for the
ready-to-use unit file.  Installation steps:

```bash
# 1. Create a dedicated service account
sudo useradd --system --no-create-home polymarket-watcher

# 2. Deploy the code
sudo mkdir -p /opt/polymarket-watcher
sudo cp -r . /opt/polymarket-watcher/
sudo python -m venv /opt/polymarket-watcher/.venv
sudo /opt/polymarket-watcher/.venv/bin/pip install -r /opt/polymarket-watcher/requirements.txt

# 3. Install the unit file
sudo cp polymarket-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload

# 4. Enable and start
sudo systemctl enable --now polymarket-watcher

# 5. Follow logs
journalctl -u polymarket-watcher -f
```

---

## Extending the Service

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the Mermaid architecture diagram
and step-by-step guides to:

* Adding a new **watcher** (e.g. `SmartMoneyWatcher`, `MarketDisputeWatcher`).
* Adding a new **action** (e.g. Discord webhook, Twilio SMS, Telegram bot).