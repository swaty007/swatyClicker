"""Slot Fingerprint: take a snapshot around a Target point, later check the slot still looks the same,
and find the slot again nearby when the program moved its window."""
from __future__ import annotations

from typing import Optional

from myclicker.domain.model import Fingerprint, Image, Point, Rect


def similarity(a: Image, b: Image, tolerance: int) -> float:
    """Share of pixels whose B, G and R channels all differ by at most `tolerance` (0..1)."""
    if (a.width, a.height) != (b.width, b.height):
        return 0.0
    pa, pb = a.bgra, b.bgra
    total = a.width * a.height
    if total == 0:
        return 0.0
    close = 0
    for i in range(0, total * 4, 4):
        if (abs(pa[i] - pb[i]) <= tolerance and abs(pa[i + 1] - pb[i + 1]) <= tolerance
                and abs(pa[i + 2] - pb[i + 2]) <= tolerance):
            close += 1
    return close / total


def _half(image: Image) -> Image:
    """Half-size copy: every 2x2 block averaged. A one-pixel shift barely changes it."""
    w, h, p = image.width // 2, image.height // 2, image.bgra
    stride = image.width * 4
    out = bytearray(w * h * 4)
    for y in range(h):
        row = 2 * y * stride
        for x in range(w):
            i = row + 8 * x
            k = (y * w + x) * 4
            for c in range(3):
                out[k + c] = (p[i + c] + p[i + 4 + c] + p[i + stride + c] + p[i + stride + 4 + c]) // 4
            out[k + 3] = 255
    return Image(w, h, bytes(out))


def _sample_offsets(image: Image, count: int = 5) -> list[tuple[int, int]]:
    """Byte offsets of a count x count grid of pixels used for the quick first pass of the search."""
    xs = [round(i * (image.width - 1) / (count - 1)) for i in range(count)]
    ys = [round(i * (image.height - 1) / (count - 1)) for i in range(count)]
    return [(y, x) for y in ys for x in xs]


class FingerprintMatcher:
    MAX_CANDIDATES = 30   # coarse-pass positions examined pixel by pixel when searching for a moved slot

    def __init__(self, size: int = 20, tolerance: int = 24, min_similarity: float = 0.85,
                 search_radius: int = 150):
        self.size = size
        self.tolerance = tolerance
        self.min_similarity = min_similarity
        self.search_radius = search_radius

    def _rect(self, point: Point, image: Optional[Image] = None) -> Rect:
        if image is not None:
            return Rect.centered(point, image.width, image.height)
        return Rect.centered(point, self.size, self.size)

    def take(self, window, point: Point) -> Optional[Fingerprint]:
        image = window.capture(self._rect(point))
        return Fingerprint(image) if image is not None else None

    def matches(self, window, point: Point, fingerprint: Fingerprint) -> bool:
        current = window.capture(self._rect(point, fingerprint.image))
        if current is None:
            return False
        return similarity(current, fingerprint.image, self.tolerance) >= self.min_similarity

    def locate(self, window, point: Point, fingerprint: Fingerprint) -> Optional[Point]:
        """Where the slot is now, searching `search_radius` pixels around `point`; None if not found."""
        icon = fingerprint.image
        width, height = window.client_size()
        left = max(0, point.x - icon.width // 2 - self.search_radius)
        top = max(0, point.y - icon.height // 2 - self.search_radius)
        right = min(width, point.x - icon.width // 2 + icon.width + self.search_radius)
        bottom = min(height, point.y - icon.height // 2 + icon.height + self.search_radius)
        if right - left < icon.width or bottom - top < icon.height:
            return None
        area = window.capture(Rect(left, top, right - left, bottom - top))
        if area is None:
            return None

        # Coarse pass on half-size copies (robust to one-pixel offsets), ranked by colour difference.
        small_area, small_icon = _half(area), _half(icon)
        if small_icon.width == 0 or small_icon.height == 0:
            return None
        samples = _sample_offsets(small_icon)
        pa, pi, aw, iw, tol = small_area.bgra, small_icon.bgra, small_area.width, small_icon.width, self.tolerance
        candidates = []
        for oy in range(0, small_area.height - small_icon.height + 1):
            for ox in range(0, small_area.width - small_icon.width + 1):
                diff = 0
                for y, x in samples:
                    i, j = ((oy + y) * aw + ox + x) * 4, (y * iw + x) * 4
                    diff += abs(pa[i] - pi[j]) + abs(pa[i + 1] - pi[j + 1]) + abs(pa[i + 2] - pi[j + 2])
                candidates.append((diff, 2 * ox, 2 * oy))
        candidates.sort()                                             # most similar colours first

        # Fine pass at full resolution around the best coarse hits.
        best_score, best = 0.0, None
        checked = set()
        for _, cx, cy in candidates[:self.MAX_CANDIDATES]:
            if best_score >= 0.98:
                break
            for oy in range(max(0, cy - 2), min(area.height - icon.height, cy + 2) + 1):
                for ox in range(max(0, cx - 2), min(area.width - icon.width, cx + 2) + 1):
                    if (ox, oy) in checked:
                        continue
                    checked.add((ox, oy))
                    score = similarity(area.crop(Rect(ox, oy, icon.width, icon.height)), icon, tol)
                    if score > best_score:
                        best_score, best = score, (ox, oy)
        if best is None or best_score < self.min_similarity:
            return None
        return Point(left + best[0] + icon.width // 2, top + best[1] + icon.height // 2)
