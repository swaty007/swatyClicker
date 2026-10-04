"""Keyboard Input Methods available through the plain Win32 API."""
from __future__ import annotations

import ctypes
import time

from myclicker.domain.input import KeyboardInputMethod
from myclicker.domain.model import Key, MethodInfo
from myclicker.platform_win import api
from myclicker.platform_win.api import user32
from myclicker.platform_win.windows import foreground

HOLD = 0.06

# Keys that live on the "extended" part of the keyboard (arrows, Ins/Del/Home/End/PgUp/PgDn, Num/, NumLock, PrtSc).
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x6F, 0x90}
_CHARS = {"Space": " ", "Enter": "\r", "Tab": "\t", "Backspace": "\b"}


def _scan(key: Key) -> int:
    return user32.MapVirtualKeyW(key.vk, api.MAPVK_VK_TO_VSC)


def _key_lparams(key: Key) -> tuple[int, int]:
    down = 1 | (_scan(key) << 16) | ((1 << 24) if key.vk in _EXTENDED else 0)
    return down, down | (1 << 30) | (1 << 31)


class PostMessageKey(KeyboardInputMethod):
    info = MethodInfo("key.postmessage", "PostMessage WM_KEYDOWN/UP (фон)", "keyboard", needs_focus=False,
                      description="Сообщения о нажатии в очередь окна. Работает в фоне, если программа их читает.")

    def press(self, window, key: Key) -> None:
        down, up = _key_lparams(key)
        if not user32.PostMessageW(window.hwnd, api.WM_KEYDOWN, key.vk, down):
            raise api.last_error()
        time.sleep(HOLD)
        user32.PostMessageW(window.hwnd, api.WM_KEYUP, key.vk, up)


class SendMessageKey(KeyboardInputMethod):
    info = MethodInfo("key.sendmessage", "SendMessage WM_KEYDOWN/UP (фон)", "keyboard", needs_focus=False,
                      description="То же, что PostMessage, но ждёт обработки сообщения окном.")

    def press(self, window, key: Key) -> None:
        down, up = _key_lparams(key)
        result = api.ULONG_PTR()
        for msg, lparam in ((api.WM_KEYDOWN, down), (api.WM_KEYUP, up)):
            if not user32.SendMessageTimeoutW(window.hwnd, msg, key.vk, lparam, api.SMTO_ABORTIFHUNG, 1000,
                                              ctypes.byref(result)):
                raise api.last_error()
            time.sleep(HOLD)


class PostMessageCharKey(KeyboardInputMethod):
    info = MethodInfo("key.postmessage_char", "PostMessage WM_CHAR (ввод символа, фон)", "keyboard",
                      needs_focus=False, description="Отправляет символ клавиши как набранный текст.")

    def press(self, window, key: Key) -> None:
        char = _CHARS.get(key.name, key.name.lower() if len(key.name) == 1 else None)
        if char is None:
            raise ValueError(f"у клавиши {key.name} нет символа для WM_CHAR")
        if not user32.PostMessageW(window.hwnd, api.WM_CHAR, ord(char), 1):
            raise api.last_error()


def _send_key_input(vk: int, scan: int, flags: int) -> None:
    event = api.INPUT(api.INPUT_KEYBOARD, api._INPUTUNION(ki=api.KEYBDINPUT(vk, scan, flags, 0, 0)))
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(api.INPUT)) != 1:
        raise api.last_error()


class SendInputVkKey(KeyboardInputMethod):
    info = MethodInfo("key.sendinput_vk", "SendInput (виртуальный код)", "keyboard", needs_focus=True,
                      description="Системная эмуляция нажатия по коду клавиши. Окно становится активным.")

    def press(self, window, key: Key) -> None:
        extended = api.KEYEVENTF_EXTENDEDKEY if key.vk in _EXTENDED else 0
        with foreground(window, restore_cursor=False):
            _send_key_input(key.vk, _scan(key), extended)
            time.sleep(HOLD)
            _send_key_input(key.vk, _scan(key), extended | api.KEYEVENTF_KEYUP)


class SendInputScanKey(KeyboardInputMethod):
    info = MethodInfo("key.sendinput_scan", "SendInput (скан-код)", "keyboard", needs_focus=True,
                      description="Эмуляция по скан-коду — так видят DirectInput/RawInput-игры. Окно становится активным.")

    def press(self, window, key: Key) -> None:
        flags = api.KEYEVENTF_SCANCODE | (api.KEYEVENTF_EXTENDEDKEY if key.vk in _EXTENDED else 0)
        with foreground(window, restore_cursor=False):
            _send_key_input(0, _scan(key), flags)
            time.sleep(HOLD)
            _send_key_input(0, _scan(key), flags | api.KEYEVENTF_KEYUP)


class KeybdEventKey(KeyboardInputMethod):
    info = MethodInfo("key.keybd_event", "keybd_event", "keyboard", needs_focus=True,
                      description="Устаревший API keybd_event. Окно становится активным.")

    def press(self, window, key: Key) -> None:
        extended = api.KEYEVENTF_EXTENDEDKEY if key.vk in _EXTENDED else 0
        with foreground(window, restore_cursor=False):
            user32.keybd_event(key.vk, _scan(key), extended, 0)
            time.sleep(HOLD)
            user32.keybd_event(key.vk, _scan(key), extended | api.KEYEVENTF_KEYUP, 0)
