"""Hypothesis: LU4 accepts synthetic clicks on game actions only shortly after REAL user input in its window.

A low-level mouse hook records real (non-injected) mouse events over the client window. Every PERIOD seconds
a background PostMessage click hits a toggling macro (the chat changes on success). Each attempt is logged
with the seconds elapsed since the last real input over the window.

Usage: python probe/real_input_window.py "<window title>" X Y DURATION
"""
import ctypes
import ctypes.wintypes as w
import datetime
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from myclicker.domain.fingerprint import similarity  # noqa: E402
from myclicker.domain.model import ClickTiming, MouseButton, Point, Rect  # noqa: E402
from myclicker.platform_win import api  # noqa: E402
from myclicker.platform_win.api import user32  # noqa: E402
from myclicker.platform_win.mouse import PostMessageMouse  # noqa: E402
from myclicker.platform_win.windows import Win32Window, Win32WindowFinder  # noqa: E402

PERIOD = 4.0
CHAT = Rect(5, 592, 360, 130)
LLMHF_INJECTED = 0x1
WM_MOUSEMOVE, WM_LBUTTONDOWN = 0x200, 0x201


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", w.POINT), ("mouseData", w.DWORD), ("flags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, w.WPARAM, w.LPARAM)
user32.SetWindowsHookExW.restype = w.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, w.HINSTANCE, w.DWORD]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM]

title, x, y, duration = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
api.enable_dpi_awareness()
window = Win32WindowFinder().find_by_title(title)
rect = w.RECT()
user32.GetWindowRect(window.hwnd, ctypes.byref(rect))
last_real = {"move": None, "click": None}
lock = threading.Lock()


@HOOKPROC
def hook(code, wparam, lparam):
    if code == 0:
        info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        inside = rect.left <= info.pt.x < rect.right and rect.top <= info.pt.y < rect.bottom
        if inside and not info.flags & LLMHF_INJECTED:
            with lock:
                last_real["move"] = time.monotonic()
                if wparam == WM_LBUTTONDOWN:
                    last_real["click"] = time.monotonic()
    return user32.CallNextHookEx(None, code, wparam, lparam)


def pump():
    user32.SetWindowsHookExW(14, hook, None, 0)   # WH_MOUSE_LL
    msg = w.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        pass


threading.Thread(target=pump, daemon=True).start()
log = ROOT / "probe" / "results" / f"real-input-{datetime.datetime.now():%H%M%S}.txt"
method, start = PostMessageMouse(), time.monotonic()
with log.open("w", encoding="utf-8") as out:
    def say(line):
        print(line, flush=True)
        out.write(line + "\n")
        out.flush()

    say("t      | worked | since real move | since real click | foreground")
    while time.monotonic() - start < duration:
        before = window.capture(CHAT)
        method.click(window, Point(x, y), MouseButton.LEFT, False, ClickTiming(0.1, 0.06))
        time.sleep(1.5)
        after = window.capture(CHAT)
        now = time.monotonic()
        with lock:
            since = {k: (f"{now - v:6.1f}s" if v else "   never") for k, v in last_real.items()}
        fg = Win32Window(user32.GetForegroundWindow()).title[:20]
        worked = "YES" if similarity(before, after, 8) < 0.99 else " no"
        say(f"{now - start:6.1f} |  {worked}   | {since['move']:>15} | {since['click']:>16} | {fg}")
        time.sleep(max(0.0, PERIOD - 1.5))
say_done = f"log: {log}"
print(say_done)
