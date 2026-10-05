"""Fast pixel arithmetic for Slot Fingerprints in pure Python.

A Python loop over pixels costs about a microsecond per pixel, and the search for a slot that moved looks at
hundreds of thousands of them. Here the per-pixel work runs inside C instead:

- `bytes.translate` with a 256-entry table turns a whole row of pixel values into |value - v| at once;
- a byte string widened into "lanes" (each byte padded with zero bytes) and read as one big integer lets
  ordinary integer addition, subtraction and masks act on every lane at once (SWAR: SIMD within a register).
  Lanes never carry into each other because every intermediate value is kept below the lane size.
"""
from __future__ import annotations

import heapq
from functools import lru_cache

from myclicker.domain.model import Image

ABS_DIFF = [bytes(abs(b - v) for b in range(256)) for v in range(256)]   # ABS_DIFF[v][b] == |b - v|


def _lanes(data: bytes, width: int) -> int:
    """`data` with every byte widened to a `width`-byte lane, as one little-endian integer."""
    wide = bytearray(len(data) * width)
    wide[0::width] = data
    return int.from_bytes(wide, "little")


@lru_cache(maxsize=64)
def _repeat(lane: bytes, count: int) -> int:
    """An integer holding `lane` (little-endian bytes) `count` times in a row."""
    return int.from_bytes(lane * count, "little")


def similarity(a: Image, b: Image, tolerance: int) -> float:
    """Share of pixels whose B, G and R channels all differ by at most `tolerance` (0..1)."""
    if (a.width, a.height) != (b.width, b.height):
        return 0.0
    pixels = a.width * a.height
    if pixels == 0:
        return 0.0
    count = len(a.bgra)
    tolerance = max(0, min(255, tolerance))
    # 16-bit lanes. x = a - b + 256 lies in 1..511, so it never borrows from the next lane.
    x = _lanes(a.bgra, 2) + _repeat(b"\x00\x01", count) - _lanes(b.bgra, 2)
    # Bit 15 of a lane is set when x >= 256 - tolerance (first) and when x <= 256 + tolerance (second).
    low = x + _repeat((0x8000 - 256 + tolerance).to_bytes(2, "little"), count)
    high = _repeat((0x8000 + 256 + tolerance).to_bytes(2, "little"), count) - x
    close = low & high & _repeat(b"\x00\x80", count)
    # A pixel is four lanes (B, G, R, A): fold G and R onto B and keep only the B lane of every pixel.
    pixel_close = close & (close >> 16) & (close >> 32) & _repeat(b"\x00\x80" + bytes(6), pixels)
    return pixel_close.bit_count() / pixels


def half(image: Image) -> Image:
    """Half-size copy: every 2x2 block averaged. A one-pixel shift barely changes it."""
    w, h = image.width // 2, image.height // 2
    if w == 0 or h == 0:
        return Image(w, h, b"")
    stride, row = image.width * 4, w * 8
    p = image.bgra
    even = memoryview(b"".join(p[2 * y * stride:2 * y * stride + row] for y in range(h))).cast("I")
    odd = memoryview(b"".join(p[(2 * y + 1) * stride:(2 * y + 1) * stride + row] for y in range(h))).cast("I")
    count = w * h * 4
    # Four values of at most 255 add up to at most 1020: 16-bit lanes hold the sum.
    total = sum(_lanes(corner.tobytes(), 2) for corner in (even[0::2], even[1::2], odd[0::2], odd[1::2]))
    average = (total >> 2) & _repeat(b"\xff\x00", count)   # the shift drags 2 bits of each next lane in; masked
    return Image(w, h, average.to_bytes(count * 2, "little")[0::2])


def _grid(length: int, count: int) -> list[int]:
    """`count` evenly spread positions in range(length) (all of them when there are fewer)."""
    if length <= count:
        return list(range(length))
    return [round(i * (length - 1) / (count - 1)) for i in range(count)]


def nearest_offsets(area: Image, icon: Image, limit: int, spacing: int) -> list[tuple[int, int]]:
    """Top-left offsets in `area` where `icon` fits, best first by the sum of absolute colour differences
    over a grid of up to 8x8 of its pixels. At most `limit` offsets, each more than `spacing` pixels away
    from every better one."""
    aw = area.width
    columns, rows = aw - icon.width + 1, area.height - icon.height + 1
    if columns <= 0 or rows <= 0:
        return []
    # Offset (ox, oy) is index oy * aw + ox of the flattened area, so the icon pixel (x, y) is compared with
    # area index + y * aw + x: one slice of a channel plane, shifted by a constant, covers every offset.
    span = (rows - 1) * aw + columns
    total = 0
    for c in range(3):
        plane, icon_plane = area.bgra[c::4], icon.bgra[c::4]
        for y in _grid(icon.height, 8):
            for x in _grid(icon.width, 8):
                start = y * aw + x
                diff = plane[start:start + span].translate(ABS_DIFF[icon_plane[y * icon.width + x]])
                total += _lanes(diff, 2)   # 16-bit lanes: 3 channels * 64 pixels * 255 < 65536
    costs = memoryview(total.to_bytes(span * 2, "little")).cast("H")
    # Indices past `columns` in a row are not offsets (the icon would wrap onto the next row): leave them out.
    valid = [(costs[i], i) for oy in range(rows) for i in range(oy * aw, oy * aw + columns)]
    # Each chosen place hides up to (2 * spacing + 1) ** 2 neighbours, so rank enough offsets to fill `limit`.
    pool = limit * (2 * spacing + 1) ** 2
    ranked = sorted(valid) if len(valid) <= pool else heapq.nsmallest(pool, valid)
    chosen: list[tuple[int, int]] = []
    for _, i in ranked:
        ox, oy = i % aw, i // aw
        if all(abs(ox - cx) > spacing or abs(oy - cy) > spacing for cx, cy in chosen):
            chosen.append((ox, oy))
            if len(chosen) == limit:
                break
    return chosen
