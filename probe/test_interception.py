"""Throwaway probe: deliver a Key Press / Mouse Click through the Interception driver (hardware-level input).

Usage (elevated, via run.ps1): test_interception.py "<window title>" key:7B | click:XxY [region:x,y,w,h]
The driver must already be installed; interception.dll comes from the local Interception package.
"""
import ctypes
import re
import sys
import time

from common import Run, diff_pixels, force_foreground, grab_window, is_admin, to_absolute, user32, window

DLL = r"D:\MyClicker\Interception\Interception\library\x64\interception.dll"


class KeyStroke(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("state", ctypes.c_ushort), ("information", ctypes.c_uint)]


class MouseStroke(ctypes.Structure):
    _fields_ = [("state", ctypes.c_ushort), ("flags", ctypes.c_ushort), ("rolling", ctypes.c_short),
                ("x", ctypes.c_int), ("y", ctypes.c_int), ("information", ctypes.c_uint)]


STROKE_SIZE = ctypes.sizeof(MouseStroke)  # InterceptionStroke is a char[sizeof(InterceptionMouseStroke)]

lib = ctypes.CDLL(DLL)
lib.interception_create_context.restype = ctypes.c_void_p
lib.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
lib.interception_get_hardware_id.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
lib.interception_get_hardware_id.restype = ctypes.c_uint


def send(ctx, device, stroke):
    buf = ctypes.create_string_buffer(STROKE_SIZE)
    ctypes.memmove(buf, ctypes.byref(stroke), ctypes.sizeof(stroke))
    return lib.interception_send(ctx, device, buf, 1)


def devices(ctx):
    found = []
    for device in range(1, 21):
        buf = ctypes.create_unicode_buffer(512)
        n = lib.interception_get_hardware_id(ctx, device, buf, ctypes.sizeof(buf))
        if n:
            found.append((device, buf.value))
    return found


def main():
    args = sys.argv[1:]
    title = args.pop(0)
    run = Run("interception")
    region = (10, 600, 370, 160)
    hwnd, rect = window(title)
    ctx = lib.interception_create_context()
    run.log("admin:", is_admin(), "ctx:", bool(ctx), "window:", title, hwnd)
    found = devices(ctx)
    for device, hwid in found:
        run.log(f"device {device}: {'keyboard' if device <= 10 else 'mouse'} {hwid}")
    keyboard = next((d for d, _ in found if d <= 10), 1)
    mouse = next((d for d, _ in found if d > 10), 11)
    original_fg = user32.GetForegroundWindow()
    run.log("focused:", force_foreground(hwnd))
    for i, step in enumerate(args, 1):
        kind, _, val = step.partition(":")
        if kind == "region":
            region = tuple(map(int, re.split(r"[^0-9]+", val)))
            continue
        name = f"{i:02d}_{kind}"
        before = grab_window(hwnd, run.path(name + "_a.png"), region)
        if kind == "key":
            scan = user32.MapVirtualKeyW(int(val, 16), 0)
            r1 = send(ctx, keyboard, KeyStroke(scan, 0, 0))
            time.sleep(0.08)
            r2 = send(ctx, keyboard, KeyStroke(scan, 1, 0))
            info = f"device={keyboard} scan={scan:#x} sent={r1},{r2}"
        elif kind == "click":
            x, y = map(int, re.split(r"[^0-9]+", val))
            ax, ay = to_absolute(rect.left + x, rect.top + y)
            r0 = send(ctx, mouse, MouseStroke(0, 0x001 | 0x002, 0, ax, ay, 0))   # absolute move, virtual desktop
            time.sleep(0.15)
            r1 = send(ctx, mouse, MouseStroke(0x001, 0x001 | 0x002, 0, ax, ay, 0))
            time.sleep(0.08)
            r2 = send(ctx, mouse, MouseStroke(0x002, 0x001 | 0x002, 0, ax, ay, 0))
            info = f"device={mouse} sent={r0},{r1},{r2}"
        else:
            raise ValueError(step)
        time.sleep(1.5)
        after = grab_window(hwnd, run.path(name + "_b.png"), region)
        run.log(f"{name}: {info} chat_changed={diff_pixels(before, after)}")
    if original_fg and original_fg != hwnd:
        force_foreground(original_fg)
    lib.interception_destroy_context(ctypes.c_void_p(ctx))
    run.log("DONE", run.dir)


main()
