"""Global hotkeys via RegisterHotKey on a dedicated thread with its own message loop."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import logging
import threading
from typing import Callable

from myclicker.domain.keys import Hotkey
from myclicker.platform_win import api
from myclicker.platform_win.api import kernel32, user32

log = logging.getLogger(__name__)
MOD_NOREPEAT = 0x4000


class HotkeyListener:
    """Calls `callback(name)` on the listener thread when a registered hotkey is pressed."""

    def __init__(self, hotkeys: dict[str, Hotkey], callback: Callable[[str], None]):
        self._hotkeys = dict(hotkeys)
        self._callback = callback
        self._thread_id = 0
        self._ready = threading.Event()
        self.failed: list[str] = []   # names whose combination is taken by another program
        self._thread = threading.Thread(target=self._run, name="hotkeys", daemon=True)

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(2.0)

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, api.WM_QUIT, 0, 0)
        self._thread.join(2.0)

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        ids = {}
        for index, (name, hotkey) in enumerate(self._hotkeys.items(), start=1):
            if user32.RegisterHotKey(None, index, hotkey.modifiers | MOD_NOREPEAT, hotkey.vk):
                ids[index] = name
            else:
                self.failed.append(name)
                log.warning("hotkey %s (%s) is already taken", name, hotkey)
        self._ready.set()
        msg = w.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == api.WM_HOTKEY and msg.wParam in ids:
                    try:
                        self._callback(ids[msg.wParam])
                    except Exception:
                        log.exception("hotkey handler failed")
        finally:
            for index in ids:
                user32.UnregisterHotKey(None, index)
