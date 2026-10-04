import unittest

from myclicker.domain.keys import Hotkey, MOD_ALT, MOD_CONTROL, MOD_SHIFT, key_by_name, key_by_vk, parse_hotkey


class KeysTest(unittest.TestCase):
    def test_function_and_letter_keys_have_windows_vk_codes(self):
        self.assertEqual(key_by_name("F12").vk, 0x7B)
        self.assertEqual(key_by_name("s").vk, 0x53)
        self.assertEqual(key_by_vk(0x0D).name, "Enter")

    def test_unknown_vk_gets_a_readable_name(self):
        self.assertEqual(key_by_vk(0xE9).name, "VK_E9")

    def test_parse_hotkey(self):
        self.assertEqual(parse_hotkey("Ctrl+Alt+S"), Hotkey(MOD_CONTROL | MOD_ALT, 0x53))
        self.assertEqual(parse_hotkey("shift + f9"), Hotkey(MOD_SHIFT, 0x78))

    def test_hotkey_text_round_trips(self):
        self.assertEqual(str(parse_hotkey("alt+ctrl+c")), "Ctrl+Alt+C")

    def test_invalid_hotkey_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hotkey("ctrl+alt")
        with self.assertRaises(ValueError):
            parse_hotkey("ctrl+nosuchkey")


if __name__ == "__main__":
    unittest.main()
