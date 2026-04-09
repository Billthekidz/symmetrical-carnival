# Usage & Deployment

## Project Layout

```
symmetrical-carnival/
├── polymarket_watcher/        ← Python package
│   ├── config.py              ← YAML-driven configuration dataclasses
│   ├── market_resolver.py     ← slug → YES/NO token IDs (Gamma REST API)
│   ├── order_book.py          ← local order-book state + price-support maths
│   ├── websocket_client.py    ← auto-reconnecting WebSocket client
│   ├── service.py             ← orchestrator
│   ├── main.py                ← entry point / signal handling
│   ├── admin/                 ← local admin CLI/TUI (SSH-based)
│   │   ├── admin_config.py    ← per-user admin tool config
│   │   ├── cli.py             ← Click-based CLI (status/logs/restart/config)
│   │   ├── editor.py          ← Windows-friendly editor selection
│   │   ├── ssh.py             ← ssh/scp subprocess helpers
│   │   └── tui.py             ← Textual streaming log viewer
│   ├── watchers/
│   │   ├── base_watcher.py          ← abstract BaseWatcher
│   │   └── price_support_watcher.py ← monitors bid-side support drop
│   └── actions/
│       ├── base_action.py    ← abstract BaseAction
│       └── log_action.py     ← default: log alert to stdout
├── tests/                     ← unit tests (pytest)
├── config.yaml                ← sample configuration
└── polymarket-watcher.service ← systemd unit file
```

---

## Running Locally

### Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Start the watcher

```bash
python -m polymarket_watcher config.yaml
```

### Run tests

```bash
pytest tests/ -v
```

---

## systemd Service (Linux)

Use the included `polymarket-watcher.service` unit file to run the watcher as a
managed system service.

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
deploys the service to a DigitalOcean Droplet via SSH (see
`.github/workflows/deploy.yml`).

### How it works

```
push to main
    │
    ▼
[Test job] ── pytest tests/ -v
    │  (deploy is skipped if tests fail)
    ▼
[Deploy job]
    1. SCP the source tree to /opt/polymarket-watcher on the Droplet
    2. pip install -r requirements.txt (inside the Droplet's .venv)
    3. systemctl daemon-reload && systemctl restart polymarket-watcher
```

### One-time Droplet setup

Run these steps once on the Droplet before the first deploy (as root or a
sudo-capable user):

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

# 5. Edit config.yaml with your market slug and settings
# Edit /opt/polymarket-watcher/config.yaml

# 6. Install the systemd unit file
cp /opt/polymarket-watcher/polymarket-watcher.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polymarket-watcher

# 7. Allow the deploy user to restart the service without a password prompt
#    (replace <deploy_user> with the SSH user)
echo "<deploy_user> ALL=(ALL) NOPASSWD: /usr/bin/systemctl daemon-reload, /usr/bin/systemctl restart polymarket-watcher, /usr/bin/systemctl status polymarket-watcher" \
  | sudo tee /etc/sudoers.d/polymarket-watcher
chmod 440 /etc/sudoers.d/polymarket-watcher
```

### Required GitHub secrets / variables

Go to **Settings → Secrets and variables → Actions** and add:

| Name | Kind | Description | Example |
|---|---|---|---|
| `DO_SSH_PRIVATE_KEY` | Secret | Full content of the deploy private key | `-----BEGIN OPENSSH PRIVATE KEY-----…` |
| `DO_HOST` | Variable | Droplet IP address or hostname | `198.51.100.10` |
| `DO_USER` | Variable | SSH user with access to `/opt/polymarket-watcher` | `deploy` |
| `DO_PORT` | Variable *(optional)* | SSH port — omit to default to `22` | `22` |
| `COPILOT_TOKEN` | Secret | Fine-grained PAT with the **Copilot Requests** permission (used by the documentation-update workflow) | `github_pat_…` |

> **How to create `COPILOT_TOKEN`:** Go to *GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens*, generate a token scoped to this repository, and grant the **Copilot Requests (Read & Write)** permission.  See the [GitHub docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/automate-with-actions) for details.

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

```bash
ssh <deploy_user>@<droplet_ip>
journalctl -u polymarket-watcher -f
```

---

## Automated Documentation Updates

Whenever a non-documentation commit lands on `main`, the workflow
`.github/workflows/update-docs.yml` automatically runs a Copilot CLI agent that
reviews the changes and updates `README.md`, `ARCHITECTURE.md`, and the `docs/`
directory.

### How it works

```
push to main (non-doc files only)
    │
    ▼
[update-docs job]
    1. Finds the last commit whose message contains "[documentation]"
    2. Installs @github/copilot via npm
    3. Runs: copilot -p "…review commits since <sha>…update docs…"
    4. Agent commits updated docs with "[documentation]" in the message
```

Self-triggering is prevented by two mechanisms:
- **`paths-ignore`** — pushes that only touch `*.md` or `docs/**` never start
  the workflow.
- **`if` condition** — the job is skipped when the head commit message already
  contains `[documentation]` (i.e. the agent's own commit).

### Authentication

The Copilot CLI uses a fine-grained PAT rather than `GITHUB_TOKEN`.  Store it
as the `COPILOT_TOKEN` repository secret (see the secrets table above).  The
PAT must have the **Copilot Requests** permission.

Reference: <https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/automate-with-actions>

---

## Admin CLI/TUI

The `polymarket_watcher.admin` module is a **local** tool you run on your
laptop (or any machine that has SSH access to the Droplet).  It uses your
existing SSH key — no extra credentials required.

### Installing the extra dependencies

The admin tool requires two additional packages (`click` and `textual`).
Install them on your **local machine** (e.g. your Windows laptop) — not on the
Droplet:

```bash
pip install -r requirements-admin.txt
```

### One-time setup — configure the remote host

Run `init` once to record the Droplet's address in your per-user config file:

```bash
python -m polymarket_watcher.admin init
```

You will be prompted for:

| Setting | Default | Description |
|---|---|---|
| `host` | *(required)* | IP address or hostname of the Droplet |
| `user` | `admin` | SSH user on the Droplet |
| `unit` | `polymarket-watcher` | systemd unit name |
| `remote_config` | `/opt/polymarket-watcher/config.yaml` | Path to the service config file |

The config file is stored in a standard per-user location — you can always
check where with:

```bash
python -m polymarket_watcher.admin config-path
```

You can also set the path explicitly via `--config-file` or the
`PMW_ADMIN_CONFIG` environment variable.

### Remote Droplet prerequisites

The `admin` user on the Droplet needs:

1. **SSH access** — add your public key to `/home/admin/.ssh/authorized_keys`.

2. **Journal read permission** — add the user to the `systemd-journal` group:

   ```bash
   usermod -aG systemd-journal admin
   ```

3. **Passwordless sudo** for restart and status — create
   `/etc/sudoers.d/polymarket-watcher-admin`:

   ```
   admin ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart polymarket-watcher, /usr/bin/systemctl status polymarket-watcher
   ```

   ```bash
   chmod 440 /etc/sudoers.d/polymarket-watcher-admin
   ```

### Commands

#### `status` — show service status

```bash
python -m polymarket_watcher.admin status
```

Runs `systemctl status polymarket-watcher --no-pager` on the remote host and
prints the output.

#### `logs` — streaming log viewer (TUI)

```bash
python -m polymarket_watcher.admin logs
```

Opens a full-screen terminal UI that streams `journalctl -f` output over SSH.
Press **`q`** to quit.

#### `restart` — restart the service

```bash
python -m polymarket_watcher.admin restart
```

Prompts for confirmation, then runs `sudo systemctl restart polymarket-watcher`
on the remote host.

#### `config edit` — edit the remote config locally

```bash
python -m polymarket_watcher.admin config edit
```

1. Downloads `/opt/polymarket-watcher/config.yaml` from the Droplet.
2. Opens it in your local editor:
   - Uses `$EDITOR` if set.
   - Falls back to **VS Code** (`code --wait`) if found on PATH.
   - Falls back to **Notepad** on Windows.
   - Falls back to **nano** then **vi** on POSIX.
3. Validates the edited file (YAML parse + service config schema check).
4. Uploads the file back **atomically** (writes `.tmp` then moves on the remote).
5. Prompts whether to restart the service immediately.

### Editor selection (Windows-friendly)

No manual editor configuration is needed on a Windows machine with VS Code
installed.  The tool detects `code` on PATH and passes `--wait` so the CLI
waits for you to close the editor tab before continuing.

If you prefer a different editor, set the `EDITOR` environment variable:

```bash
# PowerShell
$env:EDITOR = "notepad++"

# cmd.exe
set EDITOR=notepad++
```
