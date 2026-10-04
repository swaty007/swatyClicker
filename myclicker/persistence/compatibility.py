"""User marks of Input Method compatibility, stored in data/compatibility.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

from myclicker.domain.compatibility import Entry, Status


class CompatibilityStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[Entry]:
        if not self.path.exists():
            return []
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [Entry(r["app"], r["method"], Status(r["status"]), r.get("note", "")) for r in rows]

    def save(self, entries: list[Entry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"app": e.app, "method": e.method_id, "status": e.status.value, "note": e.note}
                for e in sorted(entries, key=lambda e: (e.app, e.method_id))]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
