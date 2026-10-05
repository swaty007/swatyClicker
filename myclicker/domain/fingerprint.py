"""Slot Fingerprint: take a snapshot around a Target point, later check the slot still looks the same,
and find the slot again nearby when the program moved its window."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from myclicker.domain.model import Fingerprint, Image, Point, Rect
from myclicker.domain.pixels import half, nearest_offsets, similarity

__all__ = ["FingerprintMatcher", "SlotCheck", "similarity"]


@dataclass(frozen=True)
class SlotCheck:
    """Outcome of checking a Slot Fingerprint: where the slot is now (None: not there) and where it was."""
    point: Optional[Point]
    was: Point

    @property
    def shift(self) -> Optional[tuple[int, int]]:
        if self.point is None:
            return None
        return self.point.x - self.was.x, self.point.y - self.was.y

    @property
    def moved(self) -> bool:
        return self.point is not None and self.point != self.was


class FingerprintMatcher:
    MAX_CANDIDATES = 10   # distinct coarse-pass places examined pixel by pixel when searching for a moved slot

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

    def check(self, window, point: Point, fingerprint: Fingerprint, relocate: bool) -> SlotCheck:
        """Is the slot still at `point`; with `relocate`, where within `search_radius` it is now.
        Costs one capture of the window either way."""
        icon = fingerprint.image
        home = self._rect(point, icon)
        if not relocate:
            current = window.capture(home)
            here = current is not None and similarity(current, icon, self.tolerance) >= self.min_similarity
            return SlotCheck(point if here else None, point)
        bounds = self._search_rect(window, home)
        area = window.capture(bounds) if bounds is not None else None
        if area is None:
            return SlotCheck(None, point)
        current = area.crop(Rect(home.x - bounds.x, home.y - bounds.y, icon.width, icon.height))
        if current is not None and similarity(current, icon, self.tolerance) >= self.min_similarity:
            return SlotCheck(point, point)
        found = self._search(area, icon)
        if found is None:
            return SlotCheck(None, point)
        return SlotCheck(Point(bounds.x + found[0] + icon.width // 2, bounds.y + found[1] + icon.height // 2), point)

    def _search_rect(self, window, home: Rect) -> Optional[Rect]:
        """`home` grown by `search_radius` on every side, clipped to the client area."""
        width, height = window.client_size()
        left, top = max(0, home.x - self.search_radius), max(0, home.y - self.search_radius)
        right = min(width, home.x + home.width + self.search_radius)
        bottom = min(height, home.y + home.height + self.search_radius)
        if right - left < home.width or bottom - top < home.height:
            return None
        return Rect(left, top, right - left, bottom - top)

    def _search(self, area: Image, icon: Image) -> Optional[tuple[int, int]]:
        """Top-left offset in `area` where `icon` is, or None.

        Coarse pass: every offset of the half-size icon in the half-size area, ranked by colour difference
        (half size is robust to one-pixel offsets and four times cheaper). Fine pass: full resolution,
        two pixels around each of the best MAX_CANDIDATES coarse offsets, scored by `similarity`."""
        small_area, small_icon = half(area), half(icon)
        if small_icon.width == 0 or small_icon.height == 0:
            return None
        best_score, best = 0.0, None
        checked = set()
        for sx, sy in nearest_offsets(small_area, small_icon, self.MAX_CANDIDATES, spacing=2):
            if best_score >= 0.98:
                break
            cx, cy = 2 * sx, 2 * sy
            for oy in range(max(0, cy - 2), min(area.height - icon.height, cy + 2) + 1):
                for ox in range(max(0, cx - 2), min(area.width - icon.width, cx + 2) + 1):
                    if (ox, oy) in checked:
                        continue
                    checked.add((ox, oy))
                    score = similarity(area.crop(Rect(ox, oy, icon.width, icon.height)), icon, self.tolerance)
                    if score > best_score:
                        best_score, best = score, (ox, oy)
        if best is None or best_score < self.min_similarity:
            return None
        return best
