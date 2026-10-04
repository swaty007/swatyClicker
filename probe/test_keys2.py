"""Throwaway probe, round 2 for Key Press after mouse injection proved to work.

Hypothesis A: keyboard needs the game's viewport focus that only a mouse click gives.
Hypothesis B: the action bound to F12 can be triggered by a Mouse Click on its shortcut slot.
Success = new "You cannot move while sitting" line in the system chat. Run elevated via run.ps1.
"""
import sys
import time

from common import (KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_LEFTDOWN,
                    MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE, MOUSEEVENTF_VIRTUALDESK, Run, diff_pixels,
                    force_foreground, grab, is_admin, send_key, send_mouse, to_absolute, user32, window)

TITLE = sys.argv[1] if len(sys.argv) > 1 else "LU4 - swatyBD"
SYSTEM_CHAT = (0, 728, 370, 140)   # system message pane, relative to window
NEUTRAL = (1514, 312)              # Party Matching title bar
F12_SLOT = (1043, 1012)            # shortcut panel row 1, slot 12
VK_F12 = 0x7B
SCAN_F12 = user32.MapVirtualKeyW(VK_F12, 0)

run = Run("keys2")
hwnd, rect = window(TITLE)


def click(x, y):
    ax, ay = to_absolute(rect.left + x, rect.top + y)
    f = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    send_mouse(ax, ay, f | MOUSEEVENTF_MOVE)
    time.sleep(0.15)
    send_mouse(ax, ay, f | MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.08)
    send_mouse(ax, ay, f | MOUSEEVENTF_LEFTUP)
    time.sleep(0.3)


def m_click_then_vk_scan():
    click(*NEUTRAL)
    send_key(VK_F12, SCAN_F12, 0)
    time.sleep(0.25)
    send_key(VK_F12, SCAN_F12, KEYEVENTF_KEYUP)


def m_click_then_scan():
    click(*NEUTRAL)
    send_key(0, SCAN_F12, KEYEVENTF_SCANCODE)
    time.sleep(0.25)
    send_key(0, SCAN_F12, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)


def m_click_then_keybd_event():
    click(*NEUTRAL)
    user32.keybd_event(VK_F12, SCAN_F12, 0, 0)
    time.sleep(0.25)
    user32.keybd_event(VK_F12, SCAN_F12, KEYEVENTF_KEYUP, 0)


def m_click_f12_slot():
    click(*F12_SLOT)


GROUND = (400, 520)                # empty grass left of the character


def m_click_ground():
    click(*GROUND)


def m_slot_long_hold():
    ax, ay = to_absolute(rect.left + F12_SLOT[0], rect.top + F12_SLOT[1])
    f = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    send_mouse(ax, ay, f | MOUSEEVENTF_MOVE)
    time.sleep(0.4)
    send_mouse(ax, ay, f | MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.25)
    send_mouse(ax, ay, f | MOUSEEVENTF_LEFTUP)


def m_slot_double():
    click(*F12_SLOT)
    click(*F12_SLOT)


METHODS = [
    ("01_click_then_vk_scan", m_click_then_vk_scan),
    ("02_click_then_scan", m_click_then_scan),
    ("03_click_then_keybd_event", m_click_then_keybd_event),
    ("04_mouse_click_f12_slot", m_click_f12_slot),
    ("05_mouse_click_ground", m_click_ground),
    ("06_slot_long_hold", m_slot_long_hold),
    ("07_slot_double", m_slot_double),
]


def chat(name):
    x, y, cw, ch = SYSTEM_CHAT
    return grab(rect.left + x, rect.top + y, cw, ch, run.path(name + ".png"))


def main():
    run.log("admin:", is_admin(), "window:", TITLE, "hwnd:", hwnd)
    if not is_admin() or not hwnd:
        run.log("ABORT")
        return
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    original_fg = user32.GetForegroundWindow()
    for name, fn in METHODS:
        if only and name[:2] not in only:
            continue
        focused = force_foreground(hwnd)
        before = chat(name + "_a")
        fn()
        time.sleep(1.5)
        after = chat(name + "_b")
        run.log(f"{name}: focused={focused} chat_changed={diff_pixels(before, after)}")
        time.sleep(1.5)
    if original_fg and original_fg != hwnd:
        force_foreground(original_fg)
    run.log("DONE", run.dir)


main()

