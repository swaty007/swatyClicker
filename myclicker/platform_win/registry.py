"""All Input Methods the application offers, in display order."""
from __future__ import annotations

from pathlib import Path

from myclicker.domain.input import InputMethod
from myclicker.platform_win import external, keyboard, mouse


def build_input_methods(app_dir: Path) -> list[InputMethod]:
    driver = external.InterceptionDriver(app_dir)
    return [
        mouse.PostMessageMouse(),
        mouse.SendMessageMouse(),
        mouse.SendInputAbsoluteMouse(),
        mouse.SetCursorSendInputMouse(),
        mouse.MouseEventMouse(),
        external.InterceptionMouse(driver),
        external.ArduinoHidMouse(),
        keyboard.PostMessageKey(),
        keyboard.SendMessageKey(),
        keyboard.PostMessageCharKey(),
        keyboard.SendInputVkKey(),
        keyboard.SendInputScanKey(),
        keyboard.KeybdEventKey(),
        external.InterceptionKeyboard(driver),
        external.ArduinoHidKeyboard(),
    ]
