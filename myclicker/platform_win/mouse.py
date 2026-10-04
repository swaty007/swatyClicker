"""Mouse Input Methods available through the plain Win32 API."""
from __future__ import annotations

import ctypes
import time

from myclicker.domain.input import MouseInputMethod
from myclicker.domain.model import ClickTiming, MethodInfo, MouseButton, Point
from myclicker.platform_win import api
from myclicker.platform_win.api import user32
from myclicker.platform_win.windows import deepest_child_at, foreground

# button -> (down msg, up msg, double-click msg, MK_* flag)
_MESSAGES = {
    MouseButton.LEFT: (api.WM_LBUTTONDOWN, api.WM_LBUTTONUP, api.WM_LBUTTONDBLCLK, api.MK_LBUTTON),
    MouseButton.RIGHT: (api.WM_RBUTTONDOWN, api.WM_RBUTTONUP, api.WM_RBUTTONDBLCLK, api.MK_RBUTTON),
    MouseButton.MIDDLE: (api.WM_MBUTTONDOWN, api.WM_MBUTTONUP, api.WM_MBUTTONDBLCLK, api.MK_MBUTTON),
}
# button -> (MOUSEEVENTF down, up)
_EVENT_FLAGS = {
    MouseButton.LEFT: (api.MOUSEEVENTF_LEFTDOWN, api.MOUSEEVENTF_LEFTUP),
    MouseButton.RIGHT: (api.MOUSEEVENTF_RIGHTDOWN, api.MOUSEEVENTF_RIGHTUP),
    MouseButton.MIDDLE: (api.MOUSEEVENTF_MIDDLEDOWN, api.MOUSEEVENTF_MIDDLEUP),
}


class _WindowMessageMouse(MouseInputMethod):
    """Sends WM_* mouse messages straight to the window under the point. No focus, no cursor move."""

    def _send(self, hwnd: int, msg: int, wparam: int, lparam: int) -> None:
        raise NotImplementedError

    def click(self, window, point: Point, button: MouseButton, double: bool, timing: ClickTiming) -> None:
        hwnd, local = deepest_child_at(window.hwnd, point)
        lparam = api.make_lparam(local.x, local.y)
        down, up, dblclk, mk = _MESSAGES[button]
        self._send(hwnd, api.WM_MOUSEMOVE, 0, lparam)
        time.sleep(timing.hover)      # let the game notice the cursor is over the button first
        self._send(hwnd, down, mk, lparam)
        time.sleep(timing.hold)
        self._send(hwnd, up, 0, lparam)
        if double:
            self._send(hwnd, dblclk, mk, lparam)
            time.sleep(timing.hold)
            self._send(hwnd, up, 0, lparam)


class PostMessageMouse(_WindowMessageMouse):
    info = MethodInfo("mouse.postmessage", "PostMessage (фон)", "mouse", needs_focus=False,
                      description="WM_LBUTTONDOWN/UP в очередь окна. Работает в фоне, курсор не двигается.")

    def _send(self, hwnd, msg, wparam, lparam):
        if not user32.PostMessageW(hwnd, msg, wparam, lparam):
            raise api.last_error()


class SendMessageMouse(_WindowMessageMouse):
    info = MethodInfo("mouse.sendmessage", "SendMessage (фон)", "mouse", needs_focus=False,
                      description="То же, что PostMessage, но ждёт, пока окно обработает сообщение.")

    def _send(self, hwnd, msg, wparam, lparam):
        result = api.ULONG_PTR()
        if not user32.SendMessageTimeoutW(hwnd, msg, wparam, lparam, api.SMTO_ABORTIFHUNG, 1000,
                                          ctypes.byref(result)):
            raise api.last_error()


def _send_mouse_input(dx: int, dy: int, flags: int) -> None:
    event = api.INPUT(api.INPUT_MOUSE, api._INPUTUNION(mi=api.MOUSEINPUT(dx, dy, 0, flags, 0, 0)))
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(api.INPUT)) != 1:
        raise api.last_error()


def _absolute(screen: Point) -> tuple[int, int]:
    """Screen point -> 0..65535 coordinates over the whole virtual desktop (all monitors)."""
    vx, vy = user32.GetSystemMetrics(api.SM_XVIRTUALSCREEN), user32.GetSystemMetrics(api.SM_YVIRTUALSCREEN)
    vw, vh = user32.GetSystemMetrics(api.SM_CXVIRTUALSCREEN), user32.GetSystemMetrics(api.SM_CYVIRTUALSCREEN)
    return round((screen.x - vx) * 65535 / max(vw - 1, 1)), round((screen.y - vy) * 65535 / max(vh - 1, 1))


class _ForegroundMouse(MouseInputMethod):
    """Emulates the real mouse: activates the window, moves the cursor, clicks, then restores both."""

    def _move(self, screen: Point) -> None:
        raise NotImplementedError

    def _button(self, screen: Point, flag: int) -> None:
        raise NotImplementedError

    def click(self, window, point: Point, button: MouseButton, double: bool, timing: ClickTiming) -> None:
        down, up = _EVENT_FLAGS[button]
        with foreground(window):
            screen = window.client_to_screen(point)
            self._move(screen)
            time.sleep(timing.hover)
            for _ in range(2 if double else 1):
                self._button(screen, down)
                time.sleep(timing.hold)
                self._button(screen, up)


class SendInputAbsoluteMouse(_ForegroundMouse):
    info = MethodInfo("mouse.sendinput_abs", "SendInput (абсолютные координаты)", "mouse", needs_focus=True,
                      description="Движение и клик одним API SendInput по всему виртуальному рабочему столу.")

    def _move(self, screen):
        _send_mouse_input(*_absolute(screen), api.MOUSEEVENTF_ABSOLUTE | api.MOUSEEVENTF_VIRTUALDESK
                          | api.MOUSEEVENTF_MOVE)

    def _button(self, screen, flag):
        _send_mouse_input(*_absolute(screen), api.MOUSEEVENTF_ABSOLUTE | api.MOUSEEVENTF_VIRTUALDESK | flag)


class SetCursorSendInputMouse(_ForegroundMouse):
    info = MethodInfo("mouse.setcursor_sendinput", "SetCursorPos + SendInput", "mouse", needs_focus=True,
                      description="Курсор ставится SetCursorPos, кнопка нажимается через SendInput.")

    def _move(self, screen):
        user32.SetCursorPos(screen.x, screen.y)

    def _button(self, screen, flag):
        _send_mouse_input(0, 0, flag)


class MouseEventMouse(_ForegroundMouse):
    info = MethodInfo("mouse.mouse_event", "SetCursorPos + mouse_event", "mouse", needs_focus=True,
                      description="Устаревший API mouse_event (так работают многие старые автокликеры).")

    def _move(self, screen):
        user32.SetCursorPos(screen.x, screen.y)

    def _button(self, screen, flag):
        user32.mouse_event(flag, 0, 0, 0, 0)
