"""Shared helpers for probe scripts: logging, PNG screenshots, SendInput, focus."""
import ctypes
import ctypes.wintypes as w
import datetime
import os
import struct
import time
import zlib

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()
user32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT,
                                       ctypes.POINTER(ctypes.c_size_t)]

HERE = os.path.dirname(os.path.abspath(__file__))


class Run:
    """A results folder plus a log file for one probe run."""

    def __init__(self, tag):
        self.dir = os.path.join(HERE, "results", datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + tag)
        os.makedirs(self.dir, exist_ok=True)
        self._log = open(os.path.join(self.dir, "log.txt"), "w", encoding="utf-8")

    def log(self, *a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        self._log.write(line + "\n")
        self._log.flush()

    def path(self, name):
        return os.path.join(self.dir, name)


# ---------- screenshots ----------
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


def grab(x, y, width, height, png_path=None):
    """Capture a screen rectangle; return raw BGRA bytes, optionally saving a PNG."""
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
    if png_path:
        raw = bytearray()
        for r in range(height):
            row = data[r * width * 4:(r + 1) * width * 4]
            px = bytearray(width * 3)
            px[0::3], px[1::3], px[2::3] = row[2::4], row[1::4], row[0::4]
            raw += b"\0" + px

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

        with open(png_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
                    + chunk(b"IEND", b""))
    return data


def grab_window(hwnd, png_path=None, crop=None):
    """Capture a window's own content via PrintWindow (works when occluded); crop=(x,y,w,h) in window coords."""
    r = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    width, height = r.right - r.left, r.bottom - r.top
    sdc = user32.GetDC(0)
    mdc = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, width, height)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
    x, y, cw, ch = crop or (0, 0, width, height)
    out_dc = gdi32.CreateCompatibleDC(sdc)
    out_bmp = gdi32.CreateCompatibleBitmap(sdc, cw, ch)
    gdi32.SelectObject(out_dc, out_bmp)
    gdi32.BitBlt(out_dc, 0, 0, cw, ch, mdc, x, y, 0x00CC0020)
    data = _encode(out_dc, out_bmp, cw, ch, png_path)
    for obj in (bmp, out_bmp):
        gdi32.DeleteObject(obj)
    for dc in (mdc, out_dc):
        gdi32.DeleteDC(dc)
    user32.ReleaseDC(0, sdc)
    return data


def _encode(dc, bmp, width, height, png_path):
    bi = BITMAPINFOHEADER(40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(dc, bmp, 0, height, buf, ctypes.byref(bi), 0)
    data = buf.raw
    if png_path:
        raw = bytearray()
        for r in range(height):
            row = data[r * width * 4:(r + 1) * width * 4]
            px = bytearray(width * 3)
            px[0::3], px[1::3], px[2::3] = row[2::4], row[1::4], row[0::4]
            raw += b"\0" + px

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

        with open(png_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
                    + chunk(b"IEND", b""))
    return data


def diff_pixels(a, b):
    return sum(1 for i in range(0, len(a), 4) if a[i:i + 3] != b[i:i + 3])


def window(title):
    hwnd = user32.FindWindowW(None, title)
    r = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return hwnd, r


# ---------- SendInput ----------
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _U)]


KEYEVENTF_KEYUP = 0x2
KEYEVENTF_SCANCODE = 0x8
MOUSEEVENTF_MOVE = 0x1
MOUSEEVENTF_LEFTDOWN = 0x2
MOUSEEVENTF_LEFTUP = 0x4
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000


def send_key(vk, scan, flags):
    inp = INPUT(1, _U(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def send_mouse(dx, dy, flags):
    inp = INPUT(0, _U(mi=MOUSEINPUT(dx, dy, 0, flags, 0, 0)))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def to_absolute(x, y):
    """Screen point -> 0..65535 coordinates over the whole virtual desktop."""
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    return int((x - vx) * 65535 / (vw - 1)), int((y - vy) * 65535 / (vh - 1))


# ---------- focus ----------
def force_foreground(hwnd):
    kernel32 = ctypes.windll.kernel32
    for attempt in range(4):
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        # A tap of ALT lifts the foreground lock so SetForegroundWindow is honoured.
        send_key(0x12, 0, 0)
        send_key(0x12, 0, KEYEVENTF_KEYUP)
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        me = kernel32.GetCurrentThreadId()
        attached = fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attempt >= 2:
            user32.SwitchToThisWindow(hwnd, True)
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)
        time.sleep(0.4)
        if user32.GetForegroundWindow() == hwnd:
            return True
    return False


def is_admin():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())
