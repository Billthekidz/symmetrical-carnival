"""Streaming log viewer — pipes ``journalctl -f`` over SSH straight to stdout.

Replaces the previous Textual-based TUI, which produced ANSI escape garbage and
flickered / broke on resize in Windows PowerShell.  Plain stdout streaming is
the most reliable approach across all terminals: PowerShell, Windows Terminal,
cmd, and Linux.  Press Ctrl+C to stop.
"""

from __future__ import annotations

import re
import sys

from .admin_config import AdminConfig
from .ssh import ssh_stream

# Matches any ANSI/VT escape sequence.  journalctl may emit colour codes even
# when its stdout is a pipe; stripping them keeps the output readable in every
# terminal host.
_ANSI_ESC = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def run_logs_tui(cfg: AdminConfig) -> None:
    """Stream ``journalctl -f`` over SSH and print each line to stdout.

    Blocks until the user presses **Ctrl+C** or the remote process exits.
    """
    # SYSTEMD_COLORS=0 asks journalctl not to emit colour codes regardless of
    # whether it thinks its output is a terminal.  We also strip any surviving
    # escape sequences client-side as a belt-and-braces measure.
    remote_cmd = [
        "env", "SYSTEMD_COLORS=0",
        "journalctl",
        "-u", cfg.unit,
        "-f",
        "-o", "short-iso",
        "--no-pager",
    ]

    try:
        proc = ssh_stream(cfg, remote_cmd)
    except FileNotFoundError:
        sys.exit("Error: 'ssh' not found on PATH.")

    print(f"Streaming logs for '{cfg.unit}' — press Ctrl+C to stop.\n", flush=True)

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(_ANSI_ESC.sub("", line.rstrip()), flush=True)
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C — no stack trace.
        print()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass
