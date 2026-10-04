"""Do our clicks drag game windows? Click a saved action a few times and track where its slot icon ends up.

Usage: python probe/drift_check.py <profile> <action name> <method id> <n> [hover] [hold]
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from myclicker.domain.fingerprint import similarity  # noqa: E402
from myclicker.domain.model import ClickTiming, Point, Rect  # noqa: E402
from myclicker.persistence.profiles import ProfileStore  # noqa: E402
from myclicker.platform_win import api  # noqa: E402
from myclicker.platform_win.registry import build_input_methods  # noqa: E402
from myclicker.platform_win.windows import Win32WindowFinder  # noqa: E402


def locate(window, image, around, radius=120):
    """Offset (dx, dy) from `around` where the fingerprint image matches best, and the match score."""
    cw, ch = window.client_size()
    full = window.capture(Rect(0, 0, cw, ch))
    best = (0.0, None)
    for dy in range(-radius, radius + 1, 2):
        for dx in range(-radius, radius + 1, 2):
            crop = full.crop(Rect.centered(Point(around.x + dx, around.y + dy), image.width, image.height))
            if crop is not None:
                score = similarity(crop, image, 24)
                if score > best[0]:
                    best = (score, (dx, dy))
    return best


profile_name, action_name, method_id, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
hover = float(sys.argv[5]) if len(sys.argv) > 5 else 0.1
hold = float(sys.argv[6]) if len(sys.argv) > 6 else 0.06
api.enable_dpi_awareness()
profile = ProfileStore(ROOT / "data" / "profiles").load(profile_name)
target = next(a for a in profile.actions if a.name == action_name).target
window = Win32WindowFinder().find_by_title(profile.window_title)
method = {m.info.id: m for m in build_input_methods(ROOT)}[method_id]
icon = target.fingerprint.image
print("start:", locate(window, icon, target.point))
for i in range(1, n + 1):
    method.click(window, target.point, target.button, target.double, ClickTiming(hover, hold))
    time.sleep(1.0)
    print(f"after click {i}:", locate(window, icon, target.point))
