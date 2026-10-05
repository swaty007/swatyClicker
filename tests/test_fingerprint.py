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


class RelocateTest(unittest.TestCase):
    """The game moved its window: the slot icon is now somewhere else nearby."""

    def setUp(self):
        self.matcher = FingerprintMatcher(size=20, tolerance=24, min_similarity=0.85, search_radius=60)
        background = solid_image(200, 200, (30, 30, 30))
        self.window = FakeWindow("LU4 - swatyBD", image=paint(background, 90, 90, 20, (0, 200, 0)))
        fingerprint = self.matcher.take(self.window, Point(100, 100))
        self.moved = []
        self.mouse = FakeMouse("mouse.fake")
        self.engine = Engine(methods=[self.mouse], finder=FakeWindowFinder([self.window]),
                             fingerprint_matcher=self.matcher,
                             on_target_moved=lambda profile, action: self.moved.append(action.target.point))
        self.action = Action(id="a1", name="Unstuck", schedule=Schedule(5.0),
                             target=MouseTarget(point=Point(100, 100), method_id="mouse.fake",
                                                fingerprint=fingerprint))
        self.engine.bind(Profile(name="BD", actions=[self.action]), self.window)
        self.engine.start(now=0.0)
        self.background = background

    def test_click_follows_the_slot_that_moved(self):
        self.window.image = paint(self.background, 120, 65, 20, (0, 200, 0))   # icon moved by (+30, -25)

        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks[0][1], Point(130, 75))
        self.assertEqual(self.action.target.point, Point(130, 75))
        self.assertEqual(self.moved, [Point(130, 75)])

    def test_status_counts_checks_and_moves_with_the_last_shift(self):
        self.engine.tick(0.0)                                                   # in place
        self.window.image = paint(self.background, 120, 65, 20, (0, 200, 0))
        self.engine.tick(5.0)                                                   # moved by (+30, -25)
        self.window.image = self.background
        self.engine.tick(10.0)                                                  # gone

        status = self.engine.status("BD", "a1")
        self.assertEqual((status.checks, status.moves, status.last_shift), (3, 1, (30, -25)))

    def test_slot_gone_from_the_area_pauses(self):
        self.window.image = self.background

        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])
        self.assertEqual(self.engine.status("BD", "a1").state, ActionState.PAUSED)

    def test_missing_slot_is_searched_less_and_less_often(self):
        self.window.image = self.background

        for step in range(0, 33):                     # every half second for 16 s
            self.engine.tick(step / 2)

        self.assertEqual(self.engine.status("BD", "a1").checks, 5)   # at 0, 1, 3, 7 and 15 s

    def test_found_slot_resets_the_search_delay(self):
        self.window.image = self.background
        for now in (0.0, 1.0, 3.0):                   # two misses: the next search is 4 s later
            self.engine.tick(now)
        self.window.image = paint(self.background, 120, 65, 20, (0, 200, 0))
        self.engine.tick(7.0)                         # found and clicked
        self.window.image = self.background
        for now in (12.0, 13.0):                      # interval 5 s, then a miss retried 1 s later
            self.engine.tick(now)

        self.assertEqual(self.engine.status("BD", "a1").checks, 6)

    def test_relocation_can_be_switched_off_per_action(self):
        self.action.target.relocate = False
        self.window.image = paint(self.background, 120, 65, 20, (0, 200, 0))

        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])
        self.assertEqual(self.action.target.point, Point(100, 100))


class SlotCheckTest(unittest.TestCase):
    """`check` is what the engine asks before a Mouse Click: is the slot still there, or where did it go."""

    def setUp(self):
        self.matcher = FingerprintMatcher(size=20, tolerance=24, min_similarity=0.85, search_radius=60)
        self.background = solid_image(200, 200, (30, 30, 30))
        self.window = FakeWindow("LU4 - swatyBD", image=paint(self.background, 90, 90, 20, (0, 200, 0)))
        self.fingerprint = self.matcher.take(self.window, Point(100, 100))
        self.window.captures = 0

    def test_slot_in_place(self):
        check = self.matcher.check(self.window, Point(100, 100), self.fingerprint, relocate=True)

        self.assertEqual((check.point, check.shift), (Point(100, 100), (0, 0)))

    def test_moved_slot_is_found_with_a_single_capture(self):
        self.window.image = paint(self.background, 120, 65, 20, (0, 200, 0))

        check = self.matcher.check(self.window, Point(100, 100), self.fingerprint, relocate=True)

        self.assertEqual((check.point, check.shift), (Point(130, 75), (30, -25)))
        self.assertEqual(self.window.captures, 1)

    def test_moved_slot_is_not_followed_without_relocate(self):
        self.window.image = paint(self.background, 120, 65, 20, (0, 200, 0))

        check = self.matcher.check(self.window, Point(100, 100), self.fingerprint, relocate=False)

        self.assertIsNone(check.point)

    def test_slot_gone(self):
        self.window.image = self.background

        self.assertIsNone(self.matcher.check(self.window, Point(100, 100), self.fingerprint, relocate=True).point)


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

