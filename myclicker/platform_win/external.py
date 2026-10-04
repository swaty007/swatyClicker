"""Input Methods that need something outside Windows itself: the Interception driver or an Arduino HID."""
from __future__ import annotations

import ctypes
import threading
import time
from pathlib import Path
from typing import Optional

from myclicker.domain.input import KeyboardInputMethod, MouseInputMethod
from myclicker.domain.model import Key, MethodInfo, MouseButton, Point
from myclicker.platform_win import api
from myclicker.platform_win.api import user32
from myclicker.platform_win.mouse import _absolute
from myclicker.platform_win.windows import foreground

HOLD = 0.06


class _KeyStroke(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("state", ctypes.c_ushort), ("information", ctypes.c_uint)]


class _MouseStroke(ctypes.Structure):
    _fields_ = [("state", ctypes.c_ushort), ("flags", ctypes.c_ushort), ("rolling", ctypes.c_short),
                ("x", ctypes.c_int), ("y", ctypes.c_int), ("information", ctypes.c_uint)]


_STROKE_SIZE = ctypes.sizeof(_MouseStroke)  # InterceptionStroke == char[sizeof(InterceptionMouseStroke)]
_KEY_UP, _KEY_E0 = 0x01, 0x02
_MOUSE_ABSOLUTE_VIRTUAL = 0x001 | 0x002
_MOUSE_STATES = {MouseButton.LEFT: (0x001, 0x002), MouseButton.RIGHT: (0x004, 0x008),
                 MouseButton.MIDDLE: (0x010, 0x020)}
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x6F, 0x90}


def find_interception_dll(app_dir: Path) -> Optional[Path]:
    """interception.dll next to the program, or inside an unpacked Interception package there."""
    direct = app_dir / "interception.dll"
    if direct.exists():
        return direct
    for candidate in app_dir.glob("Interception/**/x64/interception.dll"):
        return candidate
    return None


class InterceptionDriver:
    """Thin wrapper over interception.dll; input sent through it looks like it came from real hardware."""

    def __init__(self, app_dir: Path):
        self._app_dir = app_dir
        self._lib = None
        self._context = None
        self._lock = threading.Lock()
        self._problem = ""

    def _ensure(self) -> bool:
        if self._context:
            return True
        dll = find_interception_dll(self._app_dir)
        if dll is None:
            self._problem = "нет interception.dll рядом с программой"
            return False
        try:
            lib = ctypes.CDLL(str(dll))
        except OSError as error:
            self._problem = f"не загрузилась interception.dll: {error}"
            return False
        lib.interception_create_context.restype = ctypes.c_void_p
        lib.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        lib.interception_get_hardware_id.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        lib.interception_get_hardware_id.restype = ctypes.c_uint
        context = lib.interception_create_context()
        if not context:
            self._problem = "драйвер Interception не установлен (нужна установка и перезагрузка)"
            return False
        self._lib, self._context = lib, context
        return True

    def _devices(self, keyboards: bool) -> list[int]:
        found = []
        for device in (range(1, 11) if keyboards else range(11, 21)):
            buf = ctypes.create_string_buffer(512)
            if self._lib.interception_get_hardware_id(self._context, device, buf, 512):
                found.append(device)
        return found

    def check(self, keyboards: bool) -> tuple[bool, str]:
        with self._lock:
            if not self._ensure():
                return False, self._problem
            if not self._devices(keyboards):
                return False, ("драйвер не видит ни одного устройства "
                               "(его может блокировать античит — проверьте при закрытой игре)")
            return True, ""

    def send(self, keyboards: bool, stroke: ctypes.Structure) -> None:
        with self._lock:
            if not self._ensure():
                raise OSError(self._problem)
            devices = self._devices(keyboards)
            if not devices:
                raise OSError("Interception не видит устройств")
            buf = ctypes.create_string_buffer(_STROKE_SIZE)
            ctypes.memmove(buf, ctypes.byref(stroke), ctypes.sizeof(stroke))
            if self._lib.interception_send(self._context, devices[0], buf, 1) != 1:
                raise OSError("Interception не принял ввод")


class InterceptionMouse(MouseInputMethod):
    info = MethodInfo("mouse.interception", "Interception (драйвер)", "mouse", needs_focus=True,
                      description="Ввод на уровне драйвера мыши — для программы неотличим от настоящего.")

    def __init__(self, driver: InterceptionDriver):
        self._driver = driver

    def available(self):
        return self._driver.check(keyboards=False)

    def click(self, window, point: Point, button: MouseButton, double: bool) -> None:
        down, up = _MOUSE_STATES[button]
        with foreground(window):
            ax, ay = _absolute(window.client_to_screen(point))
            self._driver.send(False, _MouseStroke(0, _MOUSE_ABSOLUTE_VIRTUAL, 0, ax, ay, 0))
            time.sleep(0.05)
            for _ in range(2 if double else 1):
                self._driver.send(False, _MouseStroke(down, _MOUSE_ABSOLUTE_VIRTUAL, 0, ax, ay, 0))
                time.sleep(HOLD)
                self._driver.send(False, _MouseStroke(up, _MOUSE_ABSOLUTE_VIRTUAL, 0, ax, ay, 0))


class InterceptionKeyboard(KeyboardInputMethod):
    info = MethodInfo("key.interception", "Interception (драйвер)", "keyboard", needs_focus=True,
                      description="Нажатие на уровне драйвера клавиатуры — для программы неотличимо от настоящего.")

    def __init__(self, driver: InterceptionDriver):
        self._driver = driver

    def available(self):
        return self._driver.check(keyboards=True)

    def press(self, window, key: Key) -> None:
        scan = user32.MapVirtualKeyW(key.vk, api.MAPVK_VK_TO_VSC)
        e0 = _KEY_E0 if key.vk in _EXTENDED else 0
        with foreground(window, restore_cursor=False):
            self._driver.send(True, _KeyStroke(scan, e0, 0))
            time.sleep(HOLD)
            self._driver.send(True, _KeyStroke(scan, e0 | _KEY_UP, 0))


_ARDUINO_TODO = "ещё не реализовано: нужен Arduino Pro Micro/Leonardo с прошивкой MyClicker"


class ArduinoHidMouse(MouseInputMethod):
    info = MethodInfo("mouse.arduino", "Arduino HID (железо)", "mouse", needs_focus=True,
                      description="Плата Arduino как настоящая USB-мышь, управляемая по COM-порту.")

    def available(self):
        return False, _ARDUINO_TODO

    def click(self, window, point, button, double):
        raise NotImplementedError(_ARDUINO_TODO)


class ArduinoHidKeyboard(KeyboardInputMethod):
    info = MethodInfo("key.arduino", "Arduino HID (железо)", "keyboard", needs_focus=True,
                      description="Плата Arduino как настоящая USB-клавиатура, управляемая по COM-порту.")

    def available(self):
        return False, _ARDUINO_TODO

    def press(self, window, key):
        raise NotImplementedError(_ARDUINO_TODO)
