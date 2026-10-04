"""Input Method interfaces. Every way of delivering a Mouse Click or a Key Press implements one of these;
the engine and the UI only ever talk to these interfaces (see ADR 0001)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from myclicker.domain.model import Key, MethodInfo, MouseButton, Point


class InputMethod(ABC):
    info: MethodInfo

    def available(self) -> tuple[bool, str]:
        """(usable now, why not). Methods that need a driver or device override this."""
        return True, ""


class MouseInputMethod(InputMethod):
    @abstractmethod
    def click(self, window, point: Point, button: MouseButton, double: bool) -> None:
        """Deliver one (or a double) Mouse Click at `point` in the client area of `window`."""


class KeyboardInputMethod(InputMethod):
    @abstractmethod
    def press(self, window, key: Key) -> None:
        """Deliver one Key Press (down + up) of `key` to `window`."""
