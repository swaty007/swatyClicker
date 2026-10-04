"""Which Input Method works in which program: built-in research results plus the user's own marks."""
from __future__ import annotations

import enum
from dataclasses import dataclass


class Status(enum.Enum):
    WORKS = "works"
    PARTIAL = "partial"
    FAILS = "fails"
    UNTESTED = "untested"


@dataclass(frozen=True)
class Entry:
    app: str
    method_id: str
    status: Status
    note: str = ""


class CompatibilityTable:
    def __init__(self, builtin: list[Entry], store):
        self._builtin = {(e.app, e.method_id): e for e in builtin}
        self._store = store
        self._user = {(e.app, e.method_id): e for e in store.load()}

    def apps(self) -> list[str]:
        return sorted({app for app, _ in self._builtin} | {app for app, _ in self._user})

    def entry(self, app: str, method_id: str) -> Entry:
        key = (app, method_id)
        return self._user.get(key) or self._builtin.get(key) or Entry(app, method_id, Status.UNTESTED)

    def is_user_marked(self, app: str, method_id: str) -> bool:
        return (app, method_id) in self._user

    def mark(self, app: str, method_id: str, status: Status, note: str) -> None:
        self._user[(app, method_id)] = Entry(app, method_id, status, note)
        self._store.save(list(self._user.values()))

    def reset(self, app: str, method_id: str) -> None:
        self._user.pop((app, method_id), None)
        self._store.save(list(self._user.values()))
