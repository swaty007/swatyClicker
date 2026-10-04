"""Test doubles for the ports the domain depends on (windows, input methods)."""
from myclicker.domain.model import Image, MethodInfo


class FakeWindow:
    def __init__(self, title, alive=True, minimized=False, image=None):
        self.title = title
        self.alive = alive
        self.minimized = minimized
        self.image = image  # what capture() returns for any rect

    def is_alive(self):
        return self.alive

    def is_minimized(self):
        return self.minimized

    def capture(self, rect):
        if self.image is None:
            return None
        return self.image.crop(rect)

    def __repr__(self):
        return f"FakeWindow({self.title!r})"


class FakeWindowFinder:
    def __init__(self, windows):
        self.windows = list(windows)

    def find_by_title(self, title):
        for window in self.windows:
            if window.title == title and window.is_alive():
                return window
        return None


class FakeMouse:
    def __init__(self, method_id, needs_focus=False):
        self.info = MethodInfo(id=method_id, name=method_id, device="mouse", needs_focus=needs_focus)
        self.clicks = []

    def available(self):
        return True, ""

    def click(self, window, point, button, double):
        self.clicks.append((window, point, button, double))


class FakeKeyboard:
    def __init__(self, method_id):
        self.info = MethodInfo(id=method_id, name=method_id, device="keyboard", needs_focus=False)
        self.presses = []

    def available(self):
        return True, ""

    def press(self, window, key):
        self.presses.append((window, key))


def solid_image(width, height, bgr):
    b, g, r = bgr
    return Image(width, height, bytes([b, g, r, 255]) * (width * height))
