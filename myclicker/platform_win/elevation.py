"""Administrator rights: games that run elevated only accept input from elevated processes (UIPI)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from myclicker.platform_win.api import shell32


def is_admin() -> bool:
    return bool(shell32.IsUserAnAdmin())


def relaunch_as_admin(argv: list[str]) -> bool:
    """Start this program again with a UAC prompt. True if the elevated copy was launched."""
    if getattr(sys, "frozen", False):
        executable, args = sys.executable, argv[1:]
    else:
        python = Path(sys.executable)
        windowed = python.with_name("pythonw.exe")
        executable = str(windowed if windowed.exists() else python)
        args = [str(Path(argv[0]).resolve())] + argv[1:]
    params = subprocess.list2cmdline(args)
    result = shell32.ShellExecuteW(None, "runas", executable, params, str(Path.cwd()), 1)
    return int(result or 0) > 32
