import unittest

from myclicker.domain.engine import ActionState, Engine
from myclicker.domain.fingerprint import FingerprintMatcher
from myclicker.domain.model import Action, Fingerprint, Image, MouseTarget, Point, Profile, Schedule
from tests.fakes import FakeMouse, FakeWindow, FakeWindowFinder, solid_image

SLOT = Point(50, 50)


def paint(image, rect_x, rect_y, size, bgr):
    """Return a copy of `image` with a size x size square painted at (rect_x, rect_y)."""
    data = bytearray(image.bgra)
    for y in range(rect_y, rect_y + size):
        for x in range(rect_x, rect_x + size):
            i = (y * image.width + x) * 4
            data[i:i + 3] = bytes(bgr)
    return Image(image.width, image.height, bytes(data))


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        self.matcher = FingerprintMatcher(size=20, tolerance=24, min_similarity=0.85)
        self.captured_scene = paint(solid_image(100, 100, (30, 30, 30)), 40, 40, 20, (0, 200, 0))  # green icon
        self.window = FakeWindow("LU4 - swatyBD", image=self.captured_scene)
        self.mouse = FakeMouse("mouse.fake")
        self.engine = Engine(methods=[self.mouse], finder=FakeWindowFinder([self.window]),
                             fingerprint_matcher=self.matcher)
        fingerprint = self.matcher.take(self.window, SLOT)
        self.action = action = Action(id="a1", name="Unstuck", schedule=Schedule(5.0),
                        target=MouseTarget(point=SLOT, method_id="mouse.fake", fingerprint=fingerprint))
        self.engine.bind(Profile(name="BD", actions=[action]), self.window)
        self.engine.start(now=0.0)

    def test_click_happens_when_slot_looks_as_captured(self):
        self.engine.tick(0.0)

        self.assertEqual(len(self.mouse.clicks), 1)

    def test_small_pixel_noise_still_matches(self):
        self.window.image = paint(self.captured_scene, 45, 45, 3, (0, 215, 10))
        self.engine.tick(0.0)

        self.assertEqual(len(self.mouse.clicks), 1)

    def test_changed_slot_pauses_action_without_clicking(self):
        self.window.image = paint(self.captured_scene, 40, 40, 20, (0, 0, 220))  # different icon in the slot
        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])
        self.assertEqual(self.engine.status("BD", "a1").state, ActionState.PAUSED)

    def test_unavailable_capture_pauses_action(self):
        self.window.image = None
        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])
        self.assertEqual(self.engine.status("BD", "a1").state, ActionState.PAUSED)

    def test_check_can_be_switched_off_per_action(self):
        self.window.image = paint(self.captured_scene, 40, 40, 20, (0, 0, 220))
        self.action.target.fingerprint.check = False
        self.engine.tick(0.0)

        self.assertEqual(len(self.mouse.clicks), 1)


class TakeFingerprintTest(unittest.TestCase):
    def test_take_captures_square_centered_on_point(self):
        scene = paint(solid_image(100, 100, (30, 30, 30)), 40, 40, 20, (0, 200, 0))
        fingerprint = FingerprintMatcher(size=20).take(FakeWindow("w", image=scene), SLOT)

        self.assertIsInstance(fingerprint, Fingerprint)
        self.assertEqual((fingerprint.image.width, fingerprint.image.height), (20, 20))
        self.assertEqual(fingerprint.image.bgra[:3], bytes((0, 200, 0)))

    def test_take_returns_none_when_window_cannot_be_captured(self):
        self.assertIsNone(FingerprintMatcher().take(FakeWindow("w", image=None), SLOT))


if __name__ == "__main__":
    unittest.main()

