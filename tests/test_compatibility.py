import tempfile
import unittest
from pathlib import Path

from myclicker.domain.compatibility import CompatibilityTable, Entry, Status
from myclicker.persistence.compatibility import CompatibilityStore

BUILTIN = [
    Entry("LU4", "mouse.postmessage", Status.WORKS, "Game Macro, фон"),
    Entry("LU4", "key.sendinput_scan", Status.FAILS, ""),
]


class CompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "compatibility.json"

    def tearDown(self):
        self.tmp.cleanup()

    def table(self):
        return CompatibilityTable(BUILTIN, CompatibilityStore(self.path))

    def test_builtin_research_results_are_shown(self):
        self.assertEqual(self.table().entry("LU4", "mouse.postmessage").status, Status.WORKS)

    def test_method_without_results_is_untested(self):
        self.assertEqual(self.table().entry("LU4", "mouse.mouse_event").status, Status.UNTESTED)

    def test_user_mark_overrides_builtin_and_survives_restart(self):
        self.table().mark("LU4", "key.sendinput_scan", Status.WORKS, "после патча")

        entry = self.table().entry("LU4", "key.sendinput_scan")
        self.assertEqual((entry.status, entry.note), (Status.WORKS, "после патча"))

    def test_marking_a_new_program_adds_it_to_the_list(self):
        table = self.table()
        table.mark("Notepad", "key.postmessage", Status.WORKS, "")

        self.assertEqual(self.table().apps(), ["LU4", "Notepad"])

    def test_reset_returns_to_builtin_result(self):
        self.table().mark("LU4", "mouse.postmessage", Status.FAILS, "")
        self.table().reset("LU4", "mouse.postmessage")

        self.assertEqual(self.table().entry("LU4", "mouse.postmessage").status, Status.WORKS)


if __name__ == "__main__":
    unittest.main()
