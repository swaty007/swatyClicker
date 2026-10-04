"""ctypes bindings to the Win32 API used by the adapters. Signatures are declared explicitly so that
pointer-sized values (HWND, WPARAM, LPARAM) are passed correctly on 64-bit Python."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

# ----- messages and flags -----
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK = 0x0201, 0x0202, 0x0203
WM_RBUTTONDOWN, WM_RBUTTONUP, WM_RBUTTONDBLCLK = 0x0204, 0x0205, 0x0206
WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK = 0x0207, 0x0208, 0x0209
MK_LBUTTON, MK_RBUTTON, MK_MBUTTON = 0x0001, 0x0002, 0x0010
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102
SMTO_ABORTIFHUNG = 0x0002

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0001, 0x0002, 0x0008
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_VIRTUALDESK, MOUSEEVENTF_ABSOLUTE = 0x4000, 0x8000

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
GA_ROOT = 2
CWP_SKIPINVISIBLE, CWP_SKIPTRANSPARENT = 0x0001, 0x0004
PW_CLIENTONLY, PW_RENDERFULLCONTENT = 0x0001, 0x0002
SRCCOPY = 0x00CC0020
SW_SHOWNORMAL, SW_SHOW, SW_RESTORE = 1, 5, 9
MAPVK_VK_TO_VSC = 0


# ----- structures -----
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _INPUTUNION)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


WNDENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)


def _sig(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = list(argtypes)


# user32
_sig(user32.EnumWindows, w.BOOL, WNDENUMPROC, w.LPARAM)
_sig(user32.GetWindowTextW, ctypes.c_int, w.HWND, w.LPWSTR, ctypes.c_int)
_sig(user32.GetWindowTextLengthW, ctypes.c_int, w.HWND)
_sig(user32.IsWindow, w.BOOL, w.HWND)
_sig(user32.IsWindowVisible, w.BOOL, w.HWND)
_sig(user32.IsIconic, w.BOOL, w.HWND)
_sig(user32.GetWindowRect, w.BOOL, w.HWND, ctypes.POINTER(w.RECT))
_sig(user32.GetClientRect, w.BOOL, w.HWND, ctypes.POINTER(w.RECT))
_sig(user32.ClientToScreen, w.BOOL, w.HWND, ctypes.POINTER(w.POINT))
_sig(user32.ScreenToClient, w.BOOL, w.HWND, ctypes.POINTER(w.POINT))
_sig(user32.MapWindowPoints, ctypes.c_int, w.HWND, w.HWND, ctypes.POINTER(w.POINT), w.UINT)
_sig(user32.WindowFromPoint, w.HWND, w.POINT)
_sig(user32.ChildWindowFromPointEx, w.HWND, w.HWND, w.POINT, w.UINT)
_sig(user32.GetAncestor, w.HWND, w.HWND, w.UINT)
_sig(user32.GetCursorPos, w.BOOL, ctypes.POINTER(w.POINT))
_sig(user32.SetCursorPos, w.BOOL, ctypes.c_int, ctypes.c_int)
_sig(user32.PostMessageW, w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.SendMessageTimeoutW, LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT,
     ctypes.POINTER(ULONG_PTR))
_sig(user32.SendInput, w.UINT, w.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_sig(user32.keybd_event, None, w.BYTE, w.BYTE, w.DWORD, ULONG_PTR)
_sig(user32.mouse_event, None, w.DWORD, w.DWORD, w.DWORD, w.DWORD, ULONG_PTR)
_sig(user32.MapVirtualKeyW, w.UINT, w.UINT, w.UINT)
_sig(user32.GetForegroundWindow, w.HWND)
_sig(user32.SetForegroundWindow, w.BOOL, w.HWND)
_sig(user32.BringWindowToTop, w.BOOL, w.HWND)
_sig(user32.ShowWindow, w.BOOL, w.HWND, ctypes.c_int)
_sig(user32.GetWindowThreadProcessId, w.DWORD, w.HWND, ctypes.POINTER(w.DWORD))
_sig(user32.AttachThreadInput, w.BOOL, w.DWORD, w.DWORD, w.BOOL)
_sig(user32.GetSystemMetrics, ctypes.c_int, ctypes.c_int)
_sig(user32.PrintWindow, w.BOOL, w.HWND, w.HDC, w.UINT)
_sig(user32.GetDC, w.HDC, w.HWND)
_sig(user32.ReleaseDC, ctypes.c_int, w.HWND, w.HDC)
_sig(user32.RegisterHotKey, w.BOOL, w.HWND, ctypes.c_int, w.UINT, w.UINT)
_sig(user32.UnregisterHotKey, w.BOOL, w.HWND, ctypes.c_int)
_sig(user32.GetMessageW, w.BOOL, ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
_sig(user32.PostThreadMessageW, w.BOOL, w.DWORD, w.UINT, w.WPARAM, w.LPARAM)
# gdi32
_sig(gdi32.CreateCompatibleDC, w.HDC, w.HDC)
_sig(gdi32.CreateCompatibleBitmap, w.HBITMAP, w.HDC, ctypes.c_int, ctypes.c_int)
_sig(gdi32.SelectObject, w.HGDIOBJ, w.HDC, w.HGDIOBJ)
_sig(gdi32.DeleteObject, w.BOOL, w.HGDIOBJ)
_sig(gdi32.DeleteDC, w.BOOL, w.HDC)
_sig(gdi32.BitBlt, w.BOOL, w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int,
     ctypes.c_int, w.DWORD)
_sig(gdi32.GetDIBits, ctypes.c_int, w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p,
     ctypes.POINTER(BITMAPINFOHEADER), w.UINT)
# kernel32 / shell32
_sig(kernel32.GetCurrentThreadId, w.DWORD)
_sig(shell32.IsUserAnAdmin, w.BOOL)
_sig(shell32.ShellExecuteW, w.HINSTANCE, w.HWND, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ctypes.c_int)


def last_error() -> OSError:
    return ctypes.WinError(ctypes.get_last_error())


def make_lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def enable_dpi_awareness() -> None:
    """Use physical pixels everywhere, so window, capture and cursor coordinates agree."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            user32.SetProcessDPIAware()
