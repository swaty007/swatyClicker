"""Input Method interfaces. Every way of delivering a Mouse Click or a Key Press implements one of these;
the engine and the UI only ever talk to these interfaces (see ADR 0001)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from myclicker.domain.model import ClickTiming, Key, MethodInfo, MouseButton, MouseTarget, Point


class InputMethod(ABC):
    info: MethodInfo

    def available(self) -> tuple[bool, str]:
        """(usable now, why not). Methods that need a driver or device override this."""
        return True, ""


class MouseInputMethod(InputMethod):
    @abstractmethod
    def click(self, window, point: Point, button: MouseButton, double: bool, timing: ClickTiming) -> None:
        """Deliver one (or a double) Mouse Click at `point` in the client area of `window`,
        waiting `timing.hover` after moving onto the point and holding the button `timing.hold`."""


class KeyboardInputMethod(InputMethod):
    @abstractmethod
    def press(self, window, key: Key) -> None:
        """Deliver one Key Press (down + up) of `key` to `window`."""


def deliver(method: InputMethod, window, target) -> None:
    """Send `target`'s Mouse Click or Key Press to `window` through `method`."""
    if isinstance(target, MouseTarget):
        if method.info.device != "mouse":
            raise ValueError("для клика нужен способ ввода мыши")
        method.click(window, target.point, target.button, target.double, target.timing)
    else:
        if method.info.device != "keyboard":
            raise ValueError("для клавиши нужен способ ввода клавиатуры")
        method.press(window, target.key)
