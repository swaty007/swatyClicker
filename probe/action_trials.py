"""Reliability trials: send one saved Action N times through the app's own Input Method code.

Usage:
  python probe/action_trials.py BD "Клик 1" --method mouse.postmessage --n 4 --hover 0.1 --hold 0.06 \
      --oracle 5,592,360,130 [--point 366,552] [--separator "оружие макрос"]

For every trial: optionally click the separator action first (a macro that writes a different chat line,
so repeated identical success messages stay countable), then the action under test; the oracle region
(client coordinates) is captured after each click. All captures go into one strip image for review.
Run elevated (the game runs as administrator).
"""
import argparse
import datetime
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from myclicker.domain.fingerprint import similarity  # noqa: E402
from myclicker.domain.model import ClickTiming, Image, Point, Rect  # noqa: E402
from myclicker.persistence import png  # noqa: E402
from myclicker.persistence.profiles import ProfileStore  # noqa: E402
from myclicker.platform_win import api, elevation  # noqa: E402
from myclicker.platform_win.registry import build_input_methods  # noqa: E402
from myclicker.platform_win.windows import Win32WindowFinder  # noqa: E402

SEPARATOR_TIMING = ClickTiming(0.1, 0.06)


def stack(images, colors):
    width = max(i.width for i in images)
    rows = []
    for image, color in zip(images, colors):
        pad = bytes([128, 128, 128, 255]) * (width - image.width)
        for y in range(image.height):
            rows.append(image.bgra[y * image.width * 4:(y + 1) * image.width * 4] + pad)
        rows += [bytes(color + [255]) * width] * 3
    return Image(width, len(rows), b"".join(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("action")
    parser.add_argument("--method", required=True)
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--hover", type=float, default=0.1)
    parser.add_argument("--hold", type=float, default=0.06)
    parser.add_argument("--oracle", required=True, help="x,y,w,h in client coordinates")
    parser.add_argument("--point", help="override the action's point: x,y")
    parser.add_argument("--separator", help="name of a separator action clicked before each trial")
    parser.add_argument("--wait", type=float, default=1.2)
    args = parser.parse_args()

    api.enable_dpi_awareness()
    print("admin:", elevation.is_admin())
    profile = ProfileStore(ROOT / "data" / "profiles").load(args.profile)
    actions = {a.name: a for a in profile.actions}
    target = actions[args.action].target
    point = Point(*map(int, args.point.split(","))) if args.point else target.point
    separator = actions[args.separator].target if args.separator else None
    timing = ClickTiming(args.hover, args.hold)
    window = Win32WindowFinder().find_by_title(profile.window_title)
    methods = {m.info.id: m for m in build_input_methods(ROOT)}
    method = methods[args.method]
    region = Rect(*map(int, args.oracle.split(",")))
    stamp = datetime.datetime.now().strftime("%H%M%S")
    name = f"trials-{stamp}-{args.action.replace(' ', '')}-{args.method.split('.')[1]}-h{args.hover}"
    out = ROOT / "probe" / "results" / name
    out.mkdir(parents=True, exist_ok=True)
    print(f"{args.action} @ {point} via {args.method} hover={args.hover} hold={args.hold}")

    images, colors = [window.capture(region)], [[128, 128, 128]]
    for i in range(1, args.n + 1):
        if separator is not None:
            methods[separator.method_id].click(window, separator.point, separator.button, separator.double,
                                               SEPARATOR_TIMING)
            time.sleep(args.wait)
            images.append(window.capture(region))
            colors.append([255, 0, 0])          # blue line: after separator
        before = window.capture(region)
        method.click(window, point, target.button, target.double, timing)
        time.sleep(args.wait)
        after = window.capture(region)
        images.append(after)
        colors.append([0, 0, 255])              # red line: after the click under test
        print(f"trial {i}: changed={1 - similarity(before, after, 8):.0%}")
        time.sleep(0.5)
    out.joinpath("strip.png").write_bytes(png.encode(stack(images, colors)))
    print("strip:", out / "strip.png")


main()
