"""Domain model. Vocabulary follows CONTEXT.md (Target, Action, Profile, Slot Fingerprint, Input Method)."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass(frozen=True)
class Point:
    """A point in the client area of a window."""
    x: int
    y: int


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @staticmethod
    def centered(point: Point, width: int, height: int) -> "Rect":
        return Rect(point.x - width // 2, point.y - height // 2, width, height)


@dataclass(frozen=True)
class Image:
    """Uncompressed 32-bit BGRA pixels, top-down rows."""
    width: int
    height: int
    bgra: bytes

    def crop(self, rect: Rect) -> Optional["Image"]:
        if rect.x < 0 or rect.y < 0 or rect.x + rect.width > self.width or rect.y + rect.height > self.height:
            return None
        rows = []
        for row in range(rect.y, rect.y + rect.height):
            start = (row * self.width + rect.x) * 4
            rows.append(self.bgra[start:start + rect.width * 4])
        return Image(rect.width, rect.height, b"".join(rows))


class MouseButton(enum.Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass(frozen=True)
class Key:
    """A keyboard key identified by its Windows virtual-key code."""
    vk: int
    name: str


@dataclass(frozen=True)
class MethodInfo:
    """Describes an Input Method implementation."""
    id: str
    name: str
    device: str            # "mouse" | "keyboard"
    needs_focus: bool      # True: the Client must be the foreground window (no Background Input)
    description: str = ""


@dataclass
class Fingerprint:
    """Slot Fingerprint: the pixels around a mouse Target captured when it was set."""
    image: Image
    check: bool = True


@dataclass(frozen=True)
class ClickTiming:
    """Pauses inside one Mouse Click. Games update what is under the cursor once per frame, so the
    press must come a little after the move onto the point, and the button must stay down a moment."""
    hover: float = 0.1   # seconds after moving onto the point, before pressing
    hold: float = 0.06   # seconds between button down and up


@dataclass
class MouseTarget:
    point: Point
    method_id: str
    button: MouseButton = MouseButton.LEFT
    double: bool = False
    fingerprint: Optional[Fingerprint] = None
    timing: ClickTiming = field(default_factory=ClickTiming)
    relocate: bool = True   # if the Slot Fingerprint is not at `point`, look for it nearby and follow it


@dataclass
class KeyTarget:
    key: Key
    method_id: str


Target = Union[MouseTarget, KeyTarget]


@dataclass(frozen=True)
class Schedule:
    """Repeat every `interval` seconds, each delay randomly shifted by up to ±`jitter` seconds."""
    interval: float
    jitter: float = 0.0

    MIN_DELAY = 0.05

    def next_delay(self, rng) -> float:
        delay = self.interval + (rng.uniform(-self.jitter, self.jitter) if self.jitter else 0.0)
        return max(self.MIN_DELAY, delay)


@dataclass
class Action:
    id: str
    name: str
    schedule: Schedule
    target: Target
    enabled: bool = True


@dataclass
class Profile:
    """A user-named set of Actions for one Client. The Client is bound at runtime."""
    name: str
    actions: list[Action] = field(default_factory=list)
    window_title: str = ""   # title of the last bound window, used to find it again
