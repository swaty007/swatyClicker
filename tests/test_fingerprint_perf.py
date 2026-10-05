"""Speed of the Slot Fingerprint search at the production settings. The engine runs it before a Mouse Click
whenever the slot is not where it was, and again on every retry while the slot stays missing."""
import random
import time
import unittest

from myclicker.domain.fingerprint import FingerprintMatcher
from myclicker.domain.model import Image, Point
from tests.fakes import FakeWindow

BUDGET = 0.6   # seconds per check: about 0.2 s here, 1.6 s with the old per-pixel loops; slack for a busy PC


def noise(width, height, seed):
    """A busy, game-like picture: random colours in 4x4 blocks with a little per-pixel grain."""
    rng = random.Random(seed)
    blocks = [[bytes(rng.randrange(256) for _ in range(3)) for _ in range(width // 4 + 1)]
              for _ in range(height // 4 + 1)]
    data = bytearray()
    for y in range(height):
        for x in range(width):
            b, g, r = blocks[y // 4][x // 4]
            grain = rng.randrange(-6, 7)
            data += bytes((max(0, min(255, b + grain)), max(0, min(255, g + grain)), max(0, min(255, r + grain)), 255))
    return Image(width, height, bytes(data))


def paste(scene, icon, x, y):
    data = bytearray(scene.bgra)
    for row in range(icon.height):
        start = ((y + row) * scene.width + x) * 4
        data[start:start + icon.width * 4] = icon.bgra[row * icon.width * 4:(row + 1) * icon.width * 4]
    return Image(scene.width, scene.height, bytes(data))


class SearchSpeedTest(unittest.TestCase):
    def setUp(self):
        self.matcher = FingerprintMatcher(size=20, tolerance=24, min_similarity=0.85, search_radius=150)
        self.scene = noise(600, 400, seed=1)
        self.icon = noise(20, 20, seed=2)
        self.window = FakeWindow("LU4 - swatyBD", image=paste(self.scene, self.icon, 290, 190))
        self.fingerprint = self.matcher.take(self.window, Point(300, 200))

    def timed_check(self):
        start = time.perf_counter()
        check = self.matcher.check(self.window, Point(300, 200), self.fingerprint, relocate=True)
        return check, time.perf_counter() - start

    def test_slot_that_moved_far_is_found_within_budget(self):
        self.window.image = paste(self.scene, self.icon, 290 - 137, 190 + 121)

        check, seconds = self.timed_check()

        self.assertEqual(check.shift, (-137, 121))
        self.assertLess(seconds, BUDGET)

    def test_missing_slot_is_reported_within_budget(self):
        self.window.image = self.scene

        check, seconds = self.timed_check()

        self.assertIsNone(check.point)
        self.assertLess(seconds, BUDGET)

    def test_slot_with_changed_brightness_is_still_found(self):
        """The icon dims a little (cooldown shading), still within tolerance, and moved."""
        dim = Image(20, 20, bytes(max(0, v - 15) if i % 4 != 3 else v for i, v in enumerate(self.icon.bgra)))
        self.window.image = paste(self.scene, dim, 290 + 40, 190 - 30)

        check, _ = self.timed_check()

        self.assertEqual(check.shift, (40, -30))


if __name__ == "__main__":
    unittest.main()
