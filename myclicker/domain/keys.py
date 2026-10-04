"""Key names <-> Windows virtual-key codes, and global hotkey strings like "Ctrl+Alt+S"."""
from __future__ import annotations

from dataclasses import dataclass

from myclicker.domain.model import Key

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_MODIFIERS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
_MODIFIER_ORDER = [(MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift"), (MOD_WIN, "Win")]


def _build_names() -> dict[str, int]:
    names = {
        "Backspace": 0x08, "Tab": 0x09, "Enter": 0x0D, "Shift": 0x10, "Ctrl": 0x11, "Alt": 0x12, "Pause": 0x13,
        "CapsLock": 0x14, "Esc": 0x1B, "Space": 0x20, "PageUp": 0x21, "PageDown": 0x22, "End": 0x23, "Home": 0x24,
        "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28, "PrintScreen": 0x2C, "Insert": 0x2D, "Delete": 0x2E,
        "NumLock": 0x90, "ScrollLock": 0x91,
        "Num*": 0x6A, "Num+": 0x6B, "Num-": 0x6D, "Num.": 0x6E, "Num/": 0x6F,
        ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
        "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
    }
    for digit in range(10):
        names[str(digit)] = 0x30 + digit
        names[f"Num{digit}"] = 0x60 + digit
    for letter in range(26):
        names[chr(ord("A") + letter)] = 0x41 + letter
    for number in range(1, 25):
        names[f"F{number}"] = 0x6F + number
    return names


_NAME_TO_VK = _build_names()
_LOWER_TO_VK = {name.lower(): vk for name, vk in _NAME_TO_VK.items()}
_VK_TO_NAME = {vk: name for name, vk in _NAME_TO_VK.items()}


def key_names() -> list[str]:
    return list(_NAME_TO_VK)


def key_by_name(name: str) -> Key:
    vk = _LOWER_TO_VK.get(name.strip().lower())
    if vk is None:
        raise ValueError(f"неизвестная клавиша «{name}»")
    return Key(vk, _VK_TO_NAME[vk])


def key_by_vk(vk: int) -> Key:
    return Key(vk, _VK_TO_NAME.get(vk, f"VK_{vk:02X}"))


@dataclass(frozen=True)
class Hotkey:
    modifiers: int
    vk: int

    def __str__(self) -> str:
        parts = [label for flag, label in _MODIFIER_ORDER if self.modifiers & flag]
        return "+".join(parts + [key_by_vk(self.vk).name])


def parse_hotkey(text: str) -> Hotkey:
    modifiers, vk = 0, None
    for part in (p.strip() for p in text.split("+")):
        flag = _MODIFIERS.get(part.lower())
        if flag:
            modifiers |= flag
        elif vk is None:
            vk = key_by_name(part).vk
        else:
            raise ValueError(f"в «{text}» больше одной обычной клавиши")
    if vk is None:
        raise ValueError(f"в «{text}» нет обычной клавиши")
    return Hotkey(modifiers, vk)
