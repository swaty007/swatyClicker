"""Performance probe for Slot Fingerprint checks on live Clients. Sends no input: it only captures.

    probe/run.ps1 perf_fingerprint.py [profile name] [seconds]

Prints the cost of a capture and, for every mouse Action of the profile, the time of
`FingerprintMatcher.check` and how often it finds the slot in place, finds it moved (and by how far)
or does not find it — the same decision the engine makes before each Mouse Click.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from myclicker.domain.fingerprint import FingerprintMatcher  # noqa: E402
from myclicker.domain.model import MouseTarget, Rect  # noqa: E402
from myclicker.paths import data_dir  # noqa: E402
from myclicker.persistence.profiles import ProfileStore  # noqa: E402
from myclicker.persistence.settings import SettingsStore  # noqa: E402
from myclicker.platform_win.api import enable_dpi_awareness  # noqa: E402
from myclicker.platform_win.windows import Win32WindowFinder  # noqa: E402

def timed(fn, repeat=1):
    start = time.perf_counter()
    for _ in range(repeat):
        result = fn()
    return result, (time.perf_counter() - start) / repeat * 1000


def main():
    enable_dpi_awareness()
    name = sys.argv[1] if len(sys.argv) > 1 else "BD"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    settings = SettingsStore(data_dir() / "settings.json").load()
    profile = ProfileStore(data_dir() / "profiles").load(name)
    window = Win32WindowFinder().find_by_title(profile.window_title)
    if window is None:
        print(f"window {profile.window_title!r} not found")
        return 1
    width, height = window.client_size()
    print(f"profile {name!r}, window {window.title!r}, client {width}x{height}")

    image, ms = timed(lambda: window.capture(Rect(width // 2, height // 2, 20, 20)), 30)
    print(f"capture 20x20:    {ms:7.1f} ms   ok={image is not None}")
    _, ms = timed(lambda: window.capture(Rect(width // 2 - 160, height // 2 - 160, 320, 320)), 30)
    print(f"capture 320x320:  {ms:7.1f} ms")

    matcher = FingerprintMatcher(settings.fingerprint_size, settings.fingerprint_tolerance,
                                 settings.fingerprint_min_similarity, settings.fingerprint_search_radius)
    actions = [a for a in profile.actions if isinstance(a.target, MouseTarget) and a.target.fingerprint]
    print(f"\nrepeated checks for {seconds:g} s, search radius {matcher.search_radius} px:")
    stats = {a.id: {"checks": 0, "here": 0, "moved": {}, "lost": 0, "ms": []} for a in actions}
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for action in actions:
            target, s = action.target, stats[action.id]
            check, ms = timed(lambda: matcher.check(window, target.point, target.fingerprint, relocate=True))
            s["checks"] += 1
            s["ms"].append(ms)
            if check.point is None:
                s["lost"] += 1
            elif check.moved:
                s["moved"][check.shift] = s["moved"].get(check.shift, 0) + 1
            else:
                s["here"] += 1
        time.sleep(0.2)
    for action in actions:
        s = stats[action.id]
        print(f"  {action.name} at {action.target.point.x},{action.target.point.y}: {s['checks']} checks, "
              f"in place {s['here']}, moved {dict(s['moved'])}, not found {s['lost']}, "
              f"{min(s['ms']):.0f}..{max(s['ms']):.0f} ms per check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
