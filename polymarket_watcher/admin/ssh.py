"""SSH/SCP subprocess helpers.

All remote operations are performed by shelling out to the system ``ssh``
and ``scp`` binaries so that existing ``~/.ssh/config``, agent forwarding,
and known-hosts behaviour is automatically respected.  This also works with
the Windows OpenSSH client (shipped since Windows 10 build 1809).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from .admin_config import AdminConfig


def _ssh_base(cfg: AdminConfig) -> list[str]:
    """Return the base ``ssh`` invocation (without a remote command)."""
    cmd = ["ssh"]
    if cfg.ssh_options:
        cmd.extend(cfg.ssh_options)
    cmd.append(f"{cfg.user}@{cfg.require_host()}")
    return cmd


def ssh_run(
    cfg: AdminConfig,
    remote_cmd: Sequence[str],
    *,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Execute *remote_cmd* on the remote host via SSH.

    Parameters
    ----------
    cfg:
        Admin tool config (host, user, …).
    remote_cmd:
        The command (and arguments) to run on the remote side.
    capture:
        When True, stdout is captured and returned in the result object.
    check:
        When True, a non-zero exit code raises ``subprocess.CalledProcessError``.
    """
    full_cmd = _ssh_base(cfg) + list(remote_cmd)
    return subprocess.run(
        full_cmd,
        capture_output=capture,
        text=capture,
        check=check,
        # Redirect stdin from /dev/null so SSH does not allocate a pseudo-TTY
        # and does not block waiting for local input after the remote command
        # exits (which caused "status" to hang indefinitely).
        stdin=subprocess.DEVNULL,
    )


def ssh_stream(cfg: AdminConfig, remote_cmd: Sequence[str]) -> subprocess.Popen:
    """Start *remote_cmd* on the remote host and return the open ``Popen`` object.

    stdout is piped so the caller can read it line-by-line.  stderr is
    inherited from the parent process.
    """
    full_cmd = _ssh_base(cfg) + list(remote_cmd)
    return subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=None,  # inherit
        text=True,
        bufsize=1,  # line-buffered
        stdin=subprocess.DEVNULL,
    )


def scp_download(cfg: AdminConfig, remote_path: str, local_path: Path) -> None:
    """Copy *remote_path* from the remote host to *local_path*."""
    src = f"{cfg.user}@{cfg.require_host()}:{remote_path}"
    cmd = ["scp"] + cfg.ssh_options + [src, str(local_path)]
    subprocess.run(cmd, check=True)


def scp_upload(cfg: AdminConfig, local_path: Path, remote_path: str) -> None:
    """Copy *local_path* to *remote_path* on the remote host."""
    dst = f"{cfg.user}@{cfg.require_host()}:{remote_path}"
    cmd = ["scp"] + cfg.ssh_options + [str(local_path), dst]
    subprocess.run(cmd, check=True)
