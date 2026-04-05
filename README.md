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

### One-time Droplet setup

Before the first deploy, prepare the Droplet once (as root or a sudo-capable user):

```bash
# 1. Install Python 3.12+ and git
apt-get update && apt-get install -y python3.12 python3.12-venv git

# 2. Create a dedicated, unprivileged service account
useradd --system --no-create-home polymarket-watcher

# 3. Create the deploy directory and clone the repo
mkdir -p /opt/polymarket-watcher
git clone https://github.com/Billthekidz/symmetrical-carnival.git /opt/polymarket-watcher
chown -R <deploy_user>:<deploy_user> /opt/polymarket-watcher

# 4. Create the virtual environment and install dependencies
python3.12 -m venv /opt/polymarket-watcher/.venv
/opt/polymarket-watcher/.venv/bin/pip install -r /opt/polymarket-watcher/requirements.txt

# 5. Copy and edit config.yaml with your market slug and settings
cp /opt/polymarket-watcher/config.yaml /opt/polymarket-watcher/config.yaml.example
# Edit /opt/polymarket-watcher/config.yaml with your market slug etc.

# 6. Install the systemd unit file
cp /opt/polymarket-watcher/polymarket-watcher.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polymarket-watcher

# 7. Allow the deploy user to restart the service without a password prompt.
#    Add this line to /etc/sudoers (replace <deploy_user> with the SSH user):
echo "<deploy_user> ALL=(ALL) NOPASSWD: /usr/bin/systemctl daemon-reload, /usr/bin/systemctl restart polymarket-watcher, /usr/bin/systemctl status polymarket-watcher" \
  | sudo tee /etc/sudoers.d/polymarket-watcher
chmod 440 /etc/sudoers.d/polymarket-watcher
```

### Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and
add each of the following:

| Secret name | Description | Example |
|---|---|---|
| `DO_HOST` | Public IP address or hostname of the Droplet | `198.51.100.10` |
| `DO_USER` | SSH user that has access to `/opt/polymarket-watcher` | `deploy` |
| `DO_SSH_PRIVATE_KEY` | Full content of the private key (`~/.ssh/id_ed25519`) whose **public** half is in the Droplet's `~/.ssh/authorized_keys` | `-----BEGIN OPENSSH PRIVATE KEY-----…` |
| `DO_PORT` *(optional)* | SSH port — omit to use the default `22` | `22` |

#### Generating a dedicated deploy key

```bash
# On your local machine — create a key pair with no passphrase
ssh-keygen -t ed25519 -C "github-deploy@polymarket-watcher" -f ~/.ssh/do_deploy_key -N ""

# Copy the PUBLIC key to the Droplet
ssh-copy-id -i ~/.ssh/do_deploy_key.pub <deploy_user>@<droplet_ip>

# Add the PRIVATE key content as the DO_SSH_PRIVATE_KEY secret
cat ~/.ssh/do_deploy_key
```

### Verifying the deployment

After a successful workflow run you can check the service on the Droplet:

```bash
ssh <deploy_user>@<droplet_ip>
journalctl -u polymarket-watcher -f
```

---

## Extending the Service

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the Mermaid architecture diagram
and step-by-step guides to:

* Adding a new **watcher** (e.g. `SmartMoneyWatcher`, `MarketDisputeWatcher`).
* Adding a new **action** (e.g. Discord webhook, Twilio SMS, Telegram bot).