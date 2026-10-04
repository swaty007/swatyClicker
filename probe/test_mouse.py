"""Throwaway probe: which input method delivers a left Mouse Click to the LU4 client?

Target: the "Next" button of the Party Matching window. Success = the page
indicator ("2/9") changes. Run elevated via run.ps1.
"""
import ctypes
import ctypes.wintypes as w
import sys
import time

from common import (MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE,
                    MOUSEEVENTF_VIRTUALDESK, Run, diff_pixels, force_foreground, grab, is_admin,
                    send_mouse, to_absolute, user32, window)

TITLE = sys.argv[1] if len(sys.argv) > 1 else "LU4 - swatyBD"
BUTTON = (1377, 760)               # "Next", relative to window top-left
INDICATOR = (1280, 749, 50, 24)    # page "N/9" label, relative to window top-left
HOLD = 0.08

run = Run("mouse")
hwnd, rect = window(TITLE)
sx, sy = rect.left + BUTTON[0], rect.top + BUTTON[1]
pt = w.POINT(sx, sy)
user32.ScreenToClient(hwnd, ctypes.byref(pt))
CLIENT_LPARAM = (pt.y << 16) | (pt.x & 0xFFFF)


def m_post(_):
    user32.PostMessageW(hwnd, 0x200, 0, CLIENT_LPARAM)            # WM_MOUSEMOVE
    a = user32.PostMessageW(hwnd, 0x201, 1, CLIENT_LPARAM)        # WM_LBUTTONDOWN
    time.sleep(HOLD)
    b = user32.PostMessageW(hwnd, 0x202, 0, CLIENT_LPARAM)        # WM_LBUTTONUP
    return f"down={a} up={b}"


def m_send(_):
    res = ctypes.c_size_t()
    user32.SendMessageTimeoutW(hwnd, 0x200, 0, CLIENT_LPARAM, 2, 1000, ctypes.byref(res))
    a = user32.SendMessageTimeoutW(hwnd, 0x201, 1, CLIENT_LPARAM, 2, 1000, ctypes.byref(res))
    time.sleep(HOLD)
    b = user32.SendMessageTimeoutW(hwnd, 0x202, 0, CLIENT_LPARAM, 2, 1000, ctypes.byref(res))
    return f"down={a} up={b}"


def m_sendinput_abs(_):
    ax, ay = to_absolute(sx, sy)
    flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    send_mouse(ax, ay, flags | MOUSEEVENTF_MOVE)
    time.sleep(0.15)
    a = send_mouse(ax, ay, flags | MOUSEEVENTF_LEFTDOWN)
    time.sleep(HOLD)
    b = send_mouse(ax, ay, flags | MOUSEEVENTF_LEFTUP)
    return f"down={a} up={b}"


def m_setcursor_sendinput(_):
    user32.SetCursorPos(sx, sy)
    time.sleep(0.15)
    a = send_mouse(0, 0, MOUSEEVENTF_LEFTDOWN)
    time.sleep(HOLD)
    b = send_mouse(0, 0, MOUSEEVENTF_LEFTUP)
    return f"down={a} up={b}"


def m_mouse_event(_):
    user32.SetCursorPos(sx, sy)
    time.sleep(0.15)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(HOLD)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return "sent"


METHODS = [
    ("01_post_bg", m_post, False),
    ("02_send_bg", m_send, False),
    ("03_post_fg", m_post, True),
    ("04_sendinput_abs_fg", m_sendinput_abs, True),
    ("05_setcursor_sendinput_fg", m_setcursor_sendinput, True),
    ("06_mouse_event_fg", m_mouse_event, True),
]


def indicator(name):
    x, y, iw, ih = INDICATOR
    return grab(rect.left + x, rect.top + y, iw, ih, run.path(name + ".png"))


def main():
    run.log("admin:", is_admin(), "window:", TITLE, "hwnd:", hwnd, "button screen:", (sx, sy), "client:", (pt.x, pt.y))
    if not is_admin() or not hwnd:
        run.log("ABORT")
        return
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    original_fg = user32.GetForegroundWindow()
    cur = w.POINT()
    user32.GetCursorPos(ctypes.byref(cur))
    for name, fn, needs_focus in METHODS:
        if only and name[:2] not in only:
            continue
        focused = force_foreground(hwnd) if needs_focus else user32.GetForegroundWindow() == hwnd
        before = indicator(name + "_a")
        info = fn(hwnd)
        time.sleep(1.2)
        after = indicator(name + "_b")
        run.log(f"{name}: focused={bool(focused)} {info} indicator_changed={diff_pixels(before, after)}")
        time.sleep(0.8)
    user32.SetCursorPos(cur.x, cur.y)
    if original_fg and original_fg != hwnd:
        force_foreground(original_fg)
    run.log("DONE", run.dir)


main()
