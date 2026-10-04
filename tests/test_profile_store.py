import tempfile
import unittest
from pathlib import Path

from myclicker.domain.model import (Action, Fingerprint, Image, Key, KeyTarget, MouseButton, MouseTarget, Point,
                                    Profile, Schedule)
from myclicker.persistence.profiles import ProfileStore


def sample_profile(name="BD фарм: 1/2"):
    icon = Image(2, 2, bytes([1, 2, 3, 255, 4, 5, 6, 255, 7, 8, 9, 255, 10, 11, 12, 255]))
    return Profile(
        name=name,
        window_title="LU4 - swatyBD",
        actions=[
            Action(id="a1", name="Unstuck", schedule=Schedule(5.0, 0.5),
                   target=MouseTarget(point=Point(965, 796), method_id="mouse.postmessage",
                                      button=MouseButton.RIGHT, double=True,
                                      fingerprint=Fingerprint(icon, check=False))),
            Action(id="k1", name="Skill", schedule=Schedule(2.0), enabled=False,
                   target=KeyTarget(key=Key(0x7B, "F12"), method_id="key.sendinput_scan")),
        ],
    )


class ProfileStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "profiles"
        self.store = ProfileStore(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_profile_loads_back_identical(self):
        profile = sample_profile()
        self.store.save(profile)

        self.assertEqual(ProfileStore(self.root).load(profile.name), profile)

    def test_lists_profiles_by_their_user_given_names(self):
        self.store.save(sample_profile("BD фарм: 1/2"))
        self.store.save(sample_profile("Farm"))

        self.assertEqual(sorted(self.store.list_names()), ["BD фарм: 1/2", "Farm"])

    def test_profiles_live_inside_the_given_folder(self):
        self.store.save(sample_profile())

        files = [p for p in Path(self.tmp.name).rglob("*") if p.is_file()]
        self.assertTrue(files)
        self.assertTrue(all(self.root in p.parents for p in files))

    def test_delete_removes_profile_and_its_fingerprints(self):
        self.store.save(sample_profile())
        self.store.delete("BD фарм: 1/2")

        self.assertEqual(self.store.list_names(), [])
        self.assertEqual([p for p in self.root.rglob("*") if p.is_file()], [])

    def test_rename_keeps_actions(self):
        self.store.save(sample_profile("Old"))
        self.store.rename("Old", "New")

        self.assertEqual(self.store.list_names(), ["New"])
        self.assertEqual(len(self.store.load("New").actions), 2)

    def test_saving_again_drops_fingerprints_of_removed_actions(self):
        profile = sample_profile()
        self.store.save(profile)
        profile.actions = profile.actions[1:]
        self.store.save(profile)

        self.assertEqual([p for p in self.root.rglob("*.png")], [])


if __name__ == "__main__":
    unittest.main()
