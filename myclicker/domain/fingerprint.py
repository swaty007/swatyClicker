"""Slot Fingerprint: take a snapshot around a Target point and later check the slot still looks the same."""
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


class FingerprintMatcher:
    def __init__(self, size: int = 20, tolerance: int = 24, min_similarity: float = 0.85):
        self.size = size
        self.tolerance = tolerance
        self.min_similarity = min_similarity

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
