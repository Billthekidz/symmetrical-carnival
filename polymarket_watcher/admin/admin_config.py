"""Per-user admin tool configuration.

The config file is stored in a standard, user-writable location:
  - Windows : %APPDATA%\\polymarket-watcher\\admin.yaml
  - macOS/Linux: ~/.config/polymarket-watcher/admin.yaml

The file is plain YAML so it is easy to hand-edit.

Example admin.yaml
------------------
host: 198.51.100.10      # required — IP/hostname of the Droplet
user: admin              # SSH user (default: admin)
unit: polymarket-watcher # systemd unit name
remote_config: /opt/polymarket-watcher/config.yaml
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Platform-aware config directory
# ---------------------------------------------------------------------------

def _config_dir() -> Path:
    """Return the per-user config directory for the admin tool."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "polymarket-watcher"
        # Fallback when APPDATA is missing (unlikely on real Windows)
        return Path.home() / "AppData" / "Roaming" / "polymarket-watcher"
    # XDG_CONFIG_HOME honoured on Linux; ~/.config on macOS and Linux otherwise
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "polymarket-watcher"


def default_config_path() -> Path:
    """Return the path to the admin config file (may not exist yet)."""
    return _config_dir() / "admin.yaml"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AdminConfig:
    """Settings for the admin CLI tool."""

    host: str = ""
    user: str = "admin"
    unit: str = "polymarket-watcher"
    remote_config: str = "/opt/polymarket-watcher/config.yaml"
    # Optional: extra ssh options forwarded verbatim (e.g. "-p 2222")
    ssh_options: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Constructors / persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AdminConfig":
        """Load config from *path* (defaults to the user config file).

        Returns default values when the file does not exist yet.
        """
        resolved = path or default_config_path()
        if not resolved.exists():
            return cls()

        with open(resolved) as fh:
            data = yaml.safe_load(fh) or {}

        ssh_options_raw = data.get("ssh_options", [])
        if isinstance(ssh_options_raw, str):
            # Allow a bare string as well as a list
            ssh_options_raw = ssh_options_raw.split()

        return cls(
            host=str(data.get("host", "")),
            user=str(data.get("user", "admin")),
            unit=str(data.get("unit", "polymarket-watcher")),
            remote_config=str(
                data.get("remote_config", "/opt/polymarket-watcher/config.yaml")
            ),
            ssh_options=list(ssh_options_raw),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        """Persist config to *path* (defaults to the user config file).

        Creates parent directories if they do not exist.  Returns the path
        that was written.
        """
        resolved = path or default_config_path()
        resolved.parent.mkdir(parents=True, exist_ok=True)

        data: dict = {
            "host": self.host,
            "user": self.user,
            "unit": self.unit,
            "remote_config": self.remote_config,
        }
        if self.ssh_options:
            data["ssh_options"] = self.ssh_options

        with open(resolved, "w") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False)

        return resolved

    def require_host(self) -> str:
        """Return *host* or raise a helpful error if it is not configured."""
        if not self.host:
            raise RuntimeError(
                "No host configured.  Run:\n\n"
                "    python -m polymarket_watcher.admin init\n\n"
                "or edit the config file shown by:\n\n"
                "    python -m polymarket_watcher.admin config-path"
            )
        return self.host
