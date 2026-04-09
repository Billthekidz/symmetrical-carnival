"""Textual-based streaming log viewer for journalctl output over SSH."""

from __future__ import annotations

import subprocess
import threading
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, RichLog

from .admin_config import AdminConfig
from .ssh import ssh_stream


class LogsApp(App):
    """TUI that streams ``journalctl -f`` output over SSH.

    Key bindings
    ------------
    q / ctrl+c   Quit.
    """

    TITLE = "polymarket-watcher · live logs"
    CSS = """
    RichLog {
        height: 1fr;
        border: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self, cfg: AdminConfig) -> None:
        super().__init__()
        self._cfg = cfg
        self._proc: Optional[subprocess.Popen[str]] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(highlight=True, markup=False, wrap=True, id="log_view")
        yield Footer()

    def on_mount(self) -> None:
        """Start the background reader thread once the UI is ready."""
        self._start_reader()

    def _start_reader(self) -> None:
        """Spawn a daemon thread that pipes SSH output into the log widget."""
        remote_cmd = [
            "journalctl",
            "-u", self._cfg.unit,
            "-f",
            "-o", "short-iso",
            "--no-pager",
        ]
        try:
            self._proc = ssh_stream(self._cfg, remote_cmd)
        except FileNotFoundError:
            self.call_from_thread(self._append, "[red]Error: 'ssh' not found on PATH.[/red]")
            return

        t = threading.Thread(target=self._reader_loop, daemon=True)
        t.start()

    def _reader_loop(self) -> None:
        """Read lines from the SSH process and forward them to the TUI."""
        if self._proc is None or self._proc.stdout is None:
            self.call_from_thread(
                self._append, "[red]Error: SSH process not started.[/red]"
            )
            return
        try:
            for line in self._proc.stdout:
                self.call_from_thread(self._append, line.rstrip())
        except Exception:
            pass

    def _append(self, text: str) -> None:
        log_view = self.query_one("#log_view", RichLog)
        log_view.write(text)

    def action_quit(self) -> None:
        """Terminate the SSH process and exit the TUI."""
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self.exit()


def run_logs_tui(cfg: AdminConfig) -> None:
    """Launch the streaming log TUI (blocks until the user quits)."""
    app = LogsApp(cfg)
    app.run()
