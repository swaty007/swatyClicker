"""Throwaway probe: run a sequence of injected input steps against one LU4 client.

Usage (elevated, via run.ps1):
  steps.py "<window title>" [nofocus] step [step ...]
Steps (coordinates relative to the window's top-left):
  click:X,Y   rclick:X,Y   dclick:X,Y   move:X,Y   key:VK_HEX   wait:SECONDS
For every step: system-chat screenshot before/after. At the end: full window screenshot.
"""
import ctypes
import ctypes.wintypes as w
import re
import sys
import time

from common import (INPUT, MOUSEINPUT, _U, KEYEVENTF_KEYUP, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
                    MOUSEEVENTF_MOVE, MOUSEEVENTF_VIRTUALDESK, Run, diff_pixels, force_foreground, grab, grab_window,
                    is_admin, send_key, send_mouse, to_absolute, user32, window)

KEYEVENTF_UNICODE = 0x4
MOUSEEVENTF_RIGHTDOWN = 0x8
MOUSEEVENTF_RIGHTUP = 0x10
SYSTEM_CHAT = (0, 728, 370, 140)

args = sys.argv[1:]
title = args.pop(0)
nofocus = bool(args) and args[0] == "nofocus"
if nofocus:
    args.pop(0)
run = Run("steps")
hwnd, rect = window(title)


def at(x, y):
    return to_absolute(rect.left + x, rect.top + y)


def mouse(x, y, down, up, clicks=1):
    ax, ay = at(x, y)
    f = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    send_mouse(ax, ay, f | MOUSEEVENTF_MOVE)
    time.sleep(0.2)
    for i in range(clicks):
        send_mouse(ax, ay, f | down)
        time.sleep(0.08)
        send_mouse(ax, ay, f | up)
        time.sleep(0.1)


def do(step):
    global SYSTEM_CHAT
    kind, _, val = step.partition(":")
    if kind == "region":    # change the chat area used for before/after screenshots
        SYSTEM_CHAT = tuple(map(int, re.split(r"[^0-9]+", val.strip())))
        return
    if kind == "fg":        # bring another window to the foreground (target goes to background)
        other = user32.FindWindowW(None, val)
        run.log("fg", val, "->", force_foreground(other))
        return
    if kind == "show":      # show:6 minimize, show:9 restore (ShowWindow command)
        user32.ShowWindow(hwnd, int(val))
        return
    if kind == "wait":
        time.sleep(float(val))
        return
    if kind == "key":
        vk = int(val, 16)
        scan = user32.MapVirtualKeyW(vk, 0)
        send_key(vk, scan, 0)
        time.sleep(0.1)
        send_key(vk, scan, KEYEVENTF_KEYUP)
        return
    if kind == "type":      # SendInput KEYEVENTF_UNICODE, "~" means Enter
        for ch in val:
            if ch == "~":
                send_key(0x0D, user32.MapVirtualKeyW(0x0D, 0), 0)
                time.sleep(0.05)
                send_key(0x0D, user32.MapVirtualKeyW(0x0D, 0), KEYEVENTF_KEYUP)
            else:
                send_key(0, ord(ch), KEYEVENTF_UNICODE)
                time.sleep(0.03)
                send_key(0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
            time.sleep(0.05)
        return
    if kind == "ptype":     # PostMessage WM_CHAR to the window, "~" means Enter
        for ch in val:
            if ch == "~":
                user32.PostMessageW(hwnd, 0x100, 0x0D, 1 | (0x1C << 16))
                user32.PostMessageW(hwnd, 0x102, 0x0D, 1 | (0x1C << 16))
                user32.PostMessageW(hwnd, 0x101, 0x0D, 1 | (0x1C << 16) | (3 << 30))
            else:
                user32.PostMessageW(hwnd, 0x102, ord(ch), 1)
            time.sleep(0.05)
        return
    if kind == "pkey":
        vk = int(val, 16)
        lp = 1 | (user32.MapVirtualKeyW(vk, 0) << 16)
        user32.PostMessageW(hwnd, 0x100, vk, lp)
        time.sleep(0.1)
        user32.PostMessageW(hwnd, 0x101, vk, lp | (3 << 30))
        return
    nums = list(map(int, re.split(r"[^0-9]+", val.strip())))
    x, y = nums[0], nums[1]
    if kind in ("pclick", "pdclick", "prclick"):   # PostMessage to the client area, no focus needed
        pt = w.POINT(rect.left + x, rect.top + y)
        user32.ScreenToClient(hwnd, ctypes.byref(pt))
        lp = (pt.y << 16) | (pt.x & 0xFFFF)
        down, up, mk = (0x204, 0x205, 2) if kind == "prclick" else (0x201, 0x202, 1)
        user32.PostMessageW(hwnd, 0x200, 0, lp)
        time.sleep(0.1)
        for msg in ([down, up, 0x203, up] if kind == "pdclick" else [down, up]):
            user32.PostMessageW(hwnd, msg, mk if msg in (down, 0x203) else 0, lp)
            time.sleep(0.08)
        return
    if kind == "drag":      # drag:X1,Y1,X2,Y2 with the left button
        x1, y1, x2, y2 = nums
        f = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        send_mouse(*at(x1, y1), f | MOUSEEVENTF_MOVE)
        time.sleep(0.15)
        send_mouse(*at(x1, y1), f | MOUSEEVENTF_LEFTDOWN)
        for i in range(1, 11):
            time.sleep(0.03)
            send_mouse(*at(x1 + (x2 - x1) * i // 10, y1 + (y2 - y1) * i // 10), f | MOUSEEVENTF_MOVE)
        time.sleep(0.1)
        send_mouse(*at(x2, y2), f | MOUSEEVENTF_LEFTUP)
        return
    if kind == "wheel":     # SendInput wheel down over the point (scrolls chat to the bottom)
        ax, ay = at(x, y)
        send_mouse(ax, ay, MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE)
        time.sleep(0.1)
        for _ in range(15):
            inp = INPUT(0, _U(mi=MOUSEINPUT(0, 0, (-120) & 0xFFFFFFFF, 0x0800, 0, 0)))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            time.sleep(0.03)
        return
    if kind == "move":
        ax, ay = at(x, y)
        send_mouse(ax, ay, MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE)
    elif kind == "click":
        mouse(x, y, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
    elif kind == "dclick":
        mouse(x, y, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, clicks=2)
    elif kind == "rclick":
        mouse(x, y, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
    else:
        raise ValueError(step)


def chat(name):
    x, y, cw, ch = SYSTEM_CHAT
    return grab_window(hwnd, run.path(name + ".png"), (x, y, cw, ch))


def main():
    run.log("admin:", is_admin(), "window:", title, "hwnd:", hwnd, "nofocus:", nofocus, "steps:", args)
    if not is_admin() or not hwnd:
        run.log("ABORT")
        return
    original_fg = user32.GetForegroundWindow()
    focused = user32.GetForegroundWindow() == hwnd if nofocus else force_foreground(hwnd)
    run.log("focused:", focused)
    for i, step in enumerate(args, 1):
        name = f"{i:02d}_{step.replace(':', '_').replace(',', '-')}"
        before = chat(name + "_a")
        do(step)
        time.sleep(1.5)
        after = chat(name + "_b")
        run.log(f"{name}: chat_changed={diff_pixels(before, after)}")
    grab(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, run.path("zz_window.png"))
    if not nofocus and original_fg and original_fg != hwnd:
        force_foreground(original_fg)
    run.log("DONE", run.dir)


main()




