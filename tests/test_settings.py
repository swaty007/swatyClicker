import tempfile
import unittest
from pathlib import Path

from myclicker.persistence.settings import Settings, SettingsStore


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "settings.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_run_uses_agreed_defaults(self):
        settings = SettingsStore(self.path).load()

        self.assertEqual(settings.hotkey_toggle, "Ctrl+Alt+S")
        self.assertEqual(settings.hotkey_capture, "Ctrl+Alt+C")
        self.assertEqual(settings.hotkey_bind_window, "Ctrl+Alt+A")
        self.assertEqual(settings.default_mouse_method, "mouse.postmessage")

    def test_changes_survive_restart(self):
        store = SettingsStore(self.path)
        settings = store.load()
        settings.mini_panel_x, settings.mini_panel_y = 300, 40
        settings.hotkey_toggle = "Ctrl+Shift+F9"
        store.save(settings)

        loaded = SettingsStore(self.path).load()
        self.assertEqual((loaded.mini_panel_x, loaded.mini_panel_y, loaded.hotkey_toggle), (300, 40, "Ctrl+Shift+F9"))

    def test_broken_file_falls_back_to_defaults(self):
        self.path.write_text("{not json", encoding="utf-8")

        self.assertEqual(SettingsStore(self.path).load(), Settings())


if __name__ == "__main__":
    unittest.main()
