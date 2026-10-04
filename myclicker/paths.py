"""Portable layout: everything the program writes lives in data/ next to the program itself."""
from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):          # PyInstaller build: folder of MyClicker.exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # source checkout: the repository root


def data_dir() -> Path:
    return app_dir() / "data"
