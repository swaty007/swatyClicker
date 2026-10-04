import tempfile
import unittest
from pathlib import Path

from myclicker.app.controller import Controller, PlatformServices
from myclicker.domain.model import ClickTiming, Key, MouseTarget, Point
from tests.fakes import FakeKeyboard, FakeMouse, FakeWindow, FakeWindowFinder, solid_image


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.bd = FakeWindow("LU4 - swatyBD", image=solid_image(200, 200, (0, 200, 0)))
        self.farm = FakeWindow("LU4 - swatyFarm", image=solid_image(200, 200, (0, 0, 200)))
        self.cursor = (self.bd, Point(50, 60))
        self.mouse = FakeMouse("mouse.postmessage")
        self.keyboard = FakeKeyboard("key.sendinput_scan")
        self.controller = self.make_controller()

    def make_controller(self):
        services = PlatformServices(methods=[self.mouse, self.keyboard],
                                    finder=FakeWindowFinder([self.bd, self.farm]),
                                    window_under_cursor=lambda: self.cursor)
        return Controller(self.data, services)

    def tearDown(self):
        self.controller.shutdown()
        self.tmp.cleanup()

    def test_capture_binds_profile_to_window_under_cursor_and_saves_action(self):
        self.controller.create_profile("BD")

        action = self.controller.capture_mouse_action("BD")

        self.assertEqual(self.controller.bound_window("BD"), self.bd)
        self.assertEqual(action.target.point, Point(50, 60))
        self.assertEqual(action.target.method_id, "mouse.postmessage")
        self.assertIsNotNone(action.target.fingerprint)
        reloaded = self.make_controller().profile("BD")
        self.assertEqual([a.id for a in reloaded.actions], [action.id])

    def test_captured_click_gets_default_timing_from_settings(self):
        self.controller.settings.default_hover_delay = 0.2
        self.controller.settings.default_hold = 0.09
        self.controller.create_profile("BD")

        action = self.controller.capture_mouse_action("BD")

        self.assertEqual(action.target.timing, ClickTiming(hover=0.2, hold=0.09))

    def test_capture_over_another_window_is_rejected(self):
        self.controller.create_profile("BD")
        self.controller.bind_window("BD", self.bd)
        self.cursor = (self.farm, Point(10, 10))

        with self.assertRaises(ValueError):
            self.controller.capture_mouse_action("BD")
        self.assertEqual(self.controller.profile("BD").actions, [])

    def test_bind_window_under_cursor(self):
        self.controller.create_profile("Farm")
        self.cursor = (self.farm, Point(1, 1))

        self.controller.bind_window_under_cursor("Farm")

        self.assertEqual(self.controller.bound_window("Farm"), self.farm)

    def test_key_action_uses_default_keyboard_method(self):
        self.controller.create_profile("BD")

        action = self.controller.add_key_action("BD", Key(0x7B, "F12"))

        self.assertEqual(action.target.method_id, "key.sendinput_scan")

    def test_test_action_delivers_once_with_chosen_method(self):
        self.controller.create_profile("BD")
        action = self.controller.capture_mouse_action("BD")

        self.controller.test_action("BD", action.id, "mouse.postmessage")

        self.assertEqual(self.mouse.clicks, [(self.bd, Point(50, 60), action.target.button, False)])
        self.assertEqual(self.mouse.timings, [action.target.timing])

    def test_profiles_are_created_with_unique_names(self):
        self.controller.create_profile("BD")

        with self.assertRaises(ValueError):
            self.controller.create_profile("BD")


if __name__ == "__main__":
    unittest.main()
