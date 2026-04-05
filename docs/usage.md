# Quick Start

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

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
```

---

## Run Tests

```bash
pytest tests/ -v
```

---

## systemd Service (Linux)

See the ready-to-use `polymarket-watcher.service` unit file included in the
repository.  Installation steps:

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

## Automated Deployment to DigitalOcean

Pushing to the `main` branch automatically runs tests and, if they pass,
deploys the service to a DigitalOcean Droplet via SSH.

### How it works

```
push to main
    │
    ▼
[Test job] ── pytest tests/ -v
    │  (deploy is skipped if tests fail)
    ▼
[Deploy job]
    1. SSH into the Droplet
    2. git pull (fast-forward to HEAD of main)
    3. pip install -r requirements.txt
    4. systemctl restart polymarket-watcher
```

### Required GitHub Secrets

| Secret name | Description | Example |
|---|---|---|
| `DO_HOST` | Public IP address or hostname of the Droplet | `198.51.100.10` |
| `DO_USER` | SSH user with access to `/opt/polymarket-watcher` | `deploy` |
| `DO_SSH_PRIVATE_KEY` | Full content of the private key | `-----BEGIN OPENSSH...` |
| `DO_PORT` *(optional)* | SSH port — omit to use the default `22` | `22` |
