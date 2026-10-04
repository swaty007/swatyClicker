"""Throwaway probe: which input-emulation method delivers F12 to the LU4 client?

Run elevated (the game runs as admin; UIPI blocks input from lower integrity).
For each method: screenshot chat -> press F12 -> wait -> screenshot chat.
Success = a new "You cannot move while sitting" line in the chat.
"""
import ctypes
import ctypes.wintypes as w
import datetime
import os
import struct
import sys
import time
import zlib

WINDOW_TITLE = sys.argv[1] if len(sys.argv) > 1 else "LU4 - swatyBD"
CHAT_RECT = (0, 711, 370, 345)  # x, y, w, h relative to the window's top-left
VK_F12 = 0x7B
HOLD = 0.08   # seconds between key down and key up
SETTLE = 2.0  # seconds to wait for the chat to update
GAP = 2.0     # pause between methods so their chat lines don't merge

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
user32.SetProcessDPIAware()
user32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT, ctypes.POINTER(ctypes.c_size_t)]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results",
                   datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "log.txt"), "w", encoding="utf-8")


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    LOG.write(line + "\n")
    LOG.flush()


# ---------- screenshots (no PIL) ----------
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


def grab_png(x, y, width, height, path):
    sdc = user32.GetDC(0)
    mdc = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, width, height)
    gdi32.SelectObject(mdc, bmp)
    gdi32.BitBlt(mdc, 0, 0, width, height, sdc, x, y, 0x00CC0020)
    bi = BITMAPINFOHEADER(40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mdc, bmp, 0, height, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(0, sdc)
    data = buf.raw
    raw = bytearray()
    for r in range(height):
        row = data[r * width * 4:(r + 1) * width * 4]
        px = bytearray(width * 3)
        px[0::3], px[1::3], px[2::3] = row[2::4], row[1::4], row[0::4]
        raw += b"\0" + px

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
                + chunk(b"IEND", b""))
    return data


def shot_chat(hwnd, name):
    r = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    x, y, cw, ch = CHAT_RECT
    return grab_png(r.left + x, r.top + y, cw, ch, os.path.join(OUT, name + ".png"))


# ---------- SendInput ----------
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _U)]


KEYEVENTF_KEYUP = 0x2
KEYEVENTF_SCANCODE = 0x8


def send_input_key(vk, scan, flags):
    inp = INPUT(1, _U(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


SCAN_F12 = user32.MapVirtualKeyW(VK_F12, 0)
LPARAM_DOWN = 1 | (SCAN_F12 << 16)
LPARAM_UP = LPARAM_DOWN | (1 << 30) | (1 << 31)


# ---------- focus helpers ----------
def force_foreground(hwnd):
    # A tap of ALT lifts the foreground lock so SetForegroundWindow is honoured.
    send_input_key(0x12, 0, 0)
    send_input_key(0x12, 0, KEYEVENTF_KEYUP)
    user32.ShowWindow(hwnd, 5)
    ok = user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return ok and user32.GetForegroundWindow() == hwnd


# ---------- methods ----------
def m_post(hwnd):
    a = user32.PostMessageW(hwnd, 0x100, VK_F12, LPARAM_DOWN)
    time.sleep(HOLD)
    b = user32.PostMessageW(hwnd, 0x101, VK_F12, LPARAM_UP)
    return f"down={a} up={b} err={ctypes.GetLastError()}"


def m_send(hwnd):
    res = ctypes.c_size_t()
    a = user32.SendMessageTimeoutW(hwnd, 0x100, VK_F12, LPARAM_DOWN, 0x2, 1000, ctypes.byref(res))
    time.sleep(HOLD)
    b = user32.SendMessageTimeoutW(hwnd, 0x101, VK_F12, LPARAM_UP, 0x2, 1000, ctypes.byref(res))
    return f"down={a} up={b} err={ctypes.GetLastError()}"


def m_post_fake_activate(hwnd):
    user32.PostMessageW(hwnd, 0x0006, 1, 0)   # WM_ACTIVATE(WA_ACTIVE)
    user32.PostMessageW(hwnd, 0x0007, 0, 0)   # WM_SETFOCUS
    time.sleep(0.1)
    return m_post(hwnd)


def m_sendinput_vk(hwnd):
    a = send_input_key(VK_F12, 0, 0)
    time.sleep(HOLD)
    b = send_input_key(VK_F12, 0, KEYEVENTF_KEYUP)
    return f"down={a} up={b} err={ctypes.GetLastError()}"


def m_sendinput_scan(hwnd):
    a = send_input_key(0, SCAN_F12, KEYEVENTF_SCANCODE)
    time.sleep(HOLD)
    b = send_input_key(0, SCAN_F12, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)
    return f"down={a} up={b} err={ctypes.GetLastError()}"


def m_keybd_event(hwnd):
    user32.keybd_event(VK_F12, SCAN_F12, 0, 0)
    time.sleep(HOLD)
    user32.keybd_event(VK_F12, SCAN_F12, KEYEVENTF_KEYUP, 0)
    return "sent"


# (name, function, needs_focus)
METHODS = [
    ("01_post_bg", m_post, False),
    ("02_send_bg", m_send, False),
    ("03_post_fakeactivate_bg", m_post_fake_activate, False),
    ("04_post_fg", m_post, True),
    ("05_sendinput_vk_fg", m_sendinput_vk, True),
    ("06_sendinput_scan_fg", m_sendinput_scan, True),
    ("07_keybd_event_fg", m_keybd_event, True),
]


def main():
    log("admin:", ctypes.windll.shell32.IsUserAnAdmin(), "window:", WINDOW_TITLE)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        log("ABORT: not elevated")
        return
    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if not hwnd:
        log("ABORT: window not found")
        return
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    original_fg = user32.GetForegroundWindow()
    for name, fn, needs_focus in METHODS:
        if only and name[:2] not in only:
            continue
        if needs_focus:
            focused = force_foreground(hwnd)
        else:
            if user32.GetForegroundWindow() == hwnd and original_fg != hwnd:
                user32.SetForegroundWindow(original_fg)
                time.sleep(0.3)
            focused = user32.GetForegroundWindow() == hwnd
        before = shot_chat(hwnd, name + "_a_before")
        ctypes.windll.kernel32.SetLastError(0)
        info = fn(hwnd)
        time.sleep(SETTLE)
        after = shot_chat(hwnd, name + "_b_after")
        changed = sum(1 for i in range(0, len(before), 4) if before[i:i + 3] != after[i:i + 3])
        log(f"{name}: focused={bool(focused)} {info} chat_pixels_changed={changed}")
        time.sleep(GAP)
    if original_fg and original_fg != hwnd:
        force_foreground(original_fg)
    log("DONE", OUT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("ERROR", repr(e))
        raise
    finally:
        LOG.close()
