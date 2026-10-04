"""Win32 implementation of the Window port: lookup, geometry, capture (PrintWindow) and focus helpers."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import fnmatch
import time
from contextlib import contextmanager
from typing import Optional

from myclicker.domain.model import Image, Point, Rect
from myclicker.platform_win import api
from myclicker.platform_win.api import gdi32, kernel32, user32


class Win32Window:
    """A top-level window. Points passed in and out are client-area coordinates."""

    def __init__(self, hwnd: int):
        self.hwnd = int(hwnd)

    def __eq__(self, other):
        return isinstance(other, Win32Window) and other.hwnd == self.hwnd

    def __hash__(self):
        return hash(self.hwnd)

    def __repr__(self):
        return f"Win32Window({self.hwnd:#x}, {self.title!r})"

    @property
    def title(self) -> str:
        length = user32.GetWindowTextLengthW(self.hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(self.hwnd, buf, length + 1)
        return buf.value

    def is_alive(self) -> bool:
        return bool(user32.IsWindow(self.hwnd))

    def is_minimized(self) -> bool:
        return bool(user32.IsIconic(self.hwnd))

    def client_size(self) -> tuple[int, int]:
        r = w.RECT()
        user32.GetClientRect(self.hwnd, ctypes.byref(r))
        return r.right - r.left, r.bottom - r.top

    def client_to_screen(self, point: Point) -> Point:
        p = w.POINT(point.x, point.y)
        user32.ClientToScreen(self.hwnd, ctypes.byref(p))
        return Point(p.x, p.y)

    def screen_to_client(self, point: Point) -> Point:
        p = w.POINT(point.x, point.y)
        user32.ScreenToClient(self.hwnd, ctypes.byref(p))
        return Point(p.x, p.y)

    def capture(self, rect: Rect) -> Optional[Image]:
        """Pixels of `rect` (client coordinates) as the window draws them, even when it is covered."""
        width, height = self.client_size()
        if (self.is_minimized() or width <= 0 or height <= 0 or rect.x < 0 or rect.y < 0
                or rect.x + rect.width > width or rect.y + rect.height > height):
            return None
        screen_dc = user32.GetDC(None)
        full_dc = gdi32.CreateCompatibleDC(screen_dc)
        full_bmp = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
        part_dc = gdi32.CreateCompatibleDC(screen_dc)
        part_bmp = gdi32.CreateCompatibleBitmap(screen_dc, rect.width, rect.height)
        try:
            gdi32.SelectObject(full_dc, full_bmp)
            if not user32.PrintWindow(self.hwnd, full_dc, api.PW_CLIENTONLY | api.PW_RENDERFULLCONTENT):
                return None
            gdi32.SelectObject(part_dc, part_bmp)
            gdi32.BitBlt(part_dc, 0, 0, rect.width, rect.height, full_dc, rect.x, rect.y, api.SRCCOPY)
            header = api.BITMAPINFOHEADER(40, rect.width, -rect.height, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = ctypes.create_string_buffer(rect.width * rect.height * 4)
            if not gdi32.GetDIBits(part_dc, part_bmp, 0, rect.height, buf, ctypes.byref(header), 0):
                return None
            return Image(rect.width, rect.height, buf.raw)
        finally:
            gdi32.DeleteObject(part_bmp)
            gdi32.DeleteDC(part_dc)
            gdi32.DeleteObject(full_bmp)
            gdi32.DeleteDC(full_dc)
            user32.ReleaseDC(None, screen_dc)


def top_level_windows() -> list[Win32Window]:
    """Visible top-level windows that have a title."""
    found = []

    @api.WNDENUMPROC
    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(Win32Window(hwnd))
        return True

    user32.EnumWindows(collect, 0)
    return found


class Win32WindowFinder:
    def find_by_title(self, title: str) -> Optional[Win32Window]:
        """Exact title, or a shell-style pattern when the title contains * or ?."""
        pattern = any(ch in title for ch in "*?")
        for window in top_level_windows():
            current = window.title
            if (fnmatch.fnmatchcase(current, title) if pattern else current == title):
                return window
        return None


def cursor_position() -> Point:
    p = w.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return Point(p.x, p.y)


def window_under_cursor() -> tuple[Optional[Win32Window], Optional[Point]]:
    """The top-level window under the mouse cursor and the cursor position in its client area."""
    screen = cursor_position()
    hwnd = user32.WindowFromPoint(w.POINT(screen.x, screen.y))
    if not hwnd:
        return None, None
    root = user32.GetAncestor(hwnd, api.GA_ROOT) or hwnd
    window = Win32Window(root)
    return window, window.screen_to_client(screen)


def deepest_child_at(hwnd: int, point: Point) -> tuple[int, Point]:
    """The innermost visible child window under `point` and the point in that child's client area."""
    current, local = hwnd, w.POINT(point.x, point.y)
    for _ in range(32):
        child = user32.ChildWindowFromPointEx(current, local, api.CWP_SKIPINVISIBLE | api.CWP_SKIPTRANSPARENT)
        if not child or child == current:
            break
        user32.MapWindowPoints(current, child, ctypes.byref(local), 1)
        current = child
    return current, Point(local.x, local.y)


def _unlock_foreground() -> None:
    """A zero-length relative mouse move makes this process the last input source, which Windows
    requires before SetForegroundWindow; unlike the usual ALT tap it has no visible side effect."""
    move = api.INPUT(api.INPUT_MOUSE, api._INPUTUNION(mi=api.MOUSEINPUT(0, 0, 0, api.MOUSEEVENTF_MOVE, 0, 0)))
    user32.SendInput(1, ctypes.byref(move), ctypes.sizeof(api.INPUT))


def force_foreground(hwnd: int) -> bool:
    for attempt in range(4):
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, api.SW_RESTORE)
        _unlock_foreground()
        foreground = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        me = kernel32.GetCurrentThreadId()
        attached = bool(fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(me, fg_thread, False)
        time.sleep(0.05 * (attempt + 1))
        if user32.GetForegroundWindow() == hwnd:
            return True
    return False


@contextmanager
def foreground(window: Win32Window, restore_cursor: bool = True):
    """Make `window` the foreground window for the duration of the block, then give focus
    (and the mouse cursor) back to whatever had it before."""
    previous = user32.GetForegroundWindow()
    cursor = cursor_position()
    if previous != window.hwnd and not force_foreground(window.hwnd):
        raise OSError("не удалось сделать окно активным")
    try:
        yield
    finally:
        if restore_cursor:
            user32.SetCursorPos(cursor.x, cursor.y)
        if previous and previous != window.hwnd and user32.IsWindow(previous):
            force_foreground(previous)
