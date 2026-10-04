import unittest

from myclicker.domain.engine import ActionState, Engine
from myclicker.domain.model import Action, Key, KeyTarget, MouseButton, MouseTarget, Point, Profile, Schedule
from tests.fakes import FakeKeyboard, FakeMouse, FakeWindow, FakeWindowFinder


def mouse_action(action_id="a1", interval=5.0, jitter=0.0, method_id="mouse.fake", point=Point(10, 20)):
    return Action(id=action_id, name=action_id, schedule=Schedule(interval, jitter),
                  target=MouseTarget(point=point, method_id=method_id))


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse("mouse.fake")
        self.window = FakeWindow("LU4 - swatyBD")
        self.finder = FakeWindowFinder([self.window])
        self.engine = Engine(methods=[self.mouse], finder=self.finder)

    def test_mouse_action_fires_on_start_and_then_every_interval(self):
        profile = Profile(name="BD", actions=[mouse_action(interval=5.0)])
        self.engine.bind(profile, self.window)

        self.engine.start(now=0.0)
        for now in (0.0, 4.9, 5.0, 9.9):
            self.engine.tick(now)

        self.assertEqual(self.mouse.clicks, [(self.window, Point(10, 20), MouseButton.LEFT, False)] * 2)

    def test_jitter_shifts_each_delay(self):
        engine = Engine(methods=[self.mouse], finder=self.finder, rng=FixedRng(0.5))
        engine.bind(Profile(name="BD", actions=[mouse_action(interval=5.0, jitter=1.0)]), self.window)

        engine.start(now=0.0)
        for now in (0.0, 5.4, 5.5):
            engine.tick(now)

        self.assertEqual(len(self.mouse.clicks), 2)

    def test_disabled_action_never_fires(self):
        action = mouse_action()
        action.enabled = False
        self.engine.bind(Profile(name="BD", actions=[action]), self.window)

        self.engine.start(now=0.0)
        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])

    def test_key_action_presses_key_through_its_method(self):
        keyboard = FakeKeyboard("key.fake")
        engine = Engine(methods=[self.mouse, keyboard], finder=self.finder)
        f12 = Key(0x7B, "F12")
        action = Action(id="k1", name="F12", schedule=Schedule(1.0), target=KeyTarget(key=f12, method_id="key.fake"))
        engine.bind(Profile(name="BD", actions=[action]), self.window)

        engine.start(now=0.0)
        engine.tick(0.0)

        self.assertEqual(keyboard.presses, [(self.window, f12)])

    def test_nothing_fires_after_stop(self):
        self.engine.bind(Profile(name="BD", actions=[mouse_action()]), self.window)

        self.engine.start(now=0.0)
        self.engine.stop()
        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])


class EnginePauseTest(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse("mouse.fake")
        self.window = FakeWindow("LU4 - swatyBD")
        self.finder = FakeWindowFinder([self.window])
        self.engine = Engine(methods=[self.mouse], finder=self.finder)
        self.engine.bind(Profile(name="BD", actions=[mouse_action(interval=60.0)]), self.window)

    def status(self):
        return self.engine.status("BD", "a1")

    def test_minimized_client_pauses_action_until_restored(self):
        self.window.minimized = True
        self.engine.start(now=0.0)
        self.engine.tick(0.0)

        self.assertEqual(self.mouse.clicks, [])
        self.assertEqual(self.status().state, ActionState.PAUSED)
        self.assertIn("свёрнут", self.status().reason)

        self.window.minimized = False
        self.engine.tick(Engine.RETRY_DELAY)

        self.assertEqual(len(self.mouse.clicks), 1)
        self.assertEqual(self.status().state, ActionState.RUNNING)

    def test_closed_client_is_found_again_by_title(self):
        self.window.alive = False
        self.engine.start(now=0.0)
        self.engine.tick(0.0)

        self.assertEqual(self.status().state, ActionState.PAUSED)
        self.assertIn("не найден", self.status().reason)

        reopened = FakeWindow("LU4 - swatyBD")
        self.finder.windows.append(reopened)
        self.engine.tick(Engine.RETRY_DELAY)

        self.assertEqual(self.mouse.clicks[0][0], reopened)

    def test_failing_input_method_marks_error_and_keeps_running(self):
        def boom(*args):
            raise OSError("access denied")
        self.mouse.click = boom
        self.engine.start(now=0.0)
        self.engine.tick(0.0)

        self.assertEqual(self.status().state, ActionState.ERROR)
        self.assertIn("access denied", self.status().reason)

    def test_unknown_input_method_marks_error(self):
        self.engine.bind(Profile(name="BD", actions=[mouse_action(method_id="mouse.missing")]), self.window)
        self.engine.start(now=0.0)
        self.engine.tick(0.0)

        self.assertEqual(self.status().state, ActionState.ERROR)

    def test_status_counts_fired_inputs(self):
        self.engine.start(now=0.0)
        self.engine.tick(0.0)
        self.engine.tick(60.0)

        self.assertEqual(self.status().fired, 2)


class FixedRng:
    """rng whose uniform() always returns the same offset."""

    def __init__(self, value):
        self.value = value

    def uniform(self, low, high):
        return self.value


if __name__ == "__main__":
    unittest.main()
