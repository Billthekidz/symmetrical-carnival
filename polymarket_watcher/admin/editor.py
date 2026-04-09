"""Editor selection logic — Windows-friendly.

Priority
--------
1. ``$EDITOR`` environment variable (if set).
2. ``code --wait`` (VS Code) — if ``code`` is found on PATH.
3. ``notepad`` — on Windows only.
4. ``nano`` — on POSIX (if found on PATH).
5. ``vi``  — POSIX last-resort fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _which(name: str) -> bool:
    """Return True if *name* is findable on PATH."""
    return shutil.which(name) is not None


def find_editor() -> list[str]:
    """Return the editor command as a list suitable for ``subprocess.run``.

    The returned list is ready to have a file path appended.
    """
    env_editor = os.environ.get("EDITOR", "").strip()
    if env_editor:
        # $EDITOR may be a multi-word string like "emacsclient -t"
        return env_editor.split()

    if sys.platform == "win32":
        # Prefer the cmd shim; it’s the most reliable way to launch VS Code from subprocess
        if _which("code.cmd"):
            return ["code.cmd", "--wait"]
        if _which("code"):
            return ["code", "--wait"]
    else:
        if _which("code"):
            return ["code", "--wait"]

    if sys.platform == "win32":
        return ["notepad"]

    if _which("nano"):
        return ["nano"]

    return ["vi"]


def open_editor(file_path: Path) -> int:
    """Open *file_path* in the detected editor.

    Returns the process exit code.  Raises ``RuntimeError`` if the editor
    cannot be launched.
    """
    cmd = find_editor() + [str(file_path)]
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        raise RuntimeError(
            f"Editor not found: {cmd[0]!r}.  "
            "Set the $EDITOR environment variable to a valid editor."
            "VS Code user on Windows try `$EDITOR=code.cmd --wait`."
        )
