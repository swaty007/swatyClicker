"""Engine: runs the Actions of every bound Profile on schedule through their Input Methods.

Time is passed in explicitly (`now`, seconds from a monotonic clock), so the engine is
driven by a background thread in production and by plain calls in tests.

An Action whose Client cannot take input right now (minimized, closed, Slot Fingerprint
mismatch) is PAUSED and retried every RETRY_DELAY seconds; it resumes by itself.
"""
from __future__ import annotations

import enum
import random
import threading
from dataclasses import dataclass, field
from typing import Optional

from myclicker.domain.model import Action, MouseTarget, Profile


class ActionState(enum.Enum):
    IDLE = "idle"          # engine stopped or not yet due
    RUNNING = "running"    # last attempt delivered the input
    PAUSED = "paused"      # Client can't take input now; retried automatically
    ERROR = "error"        # the Input Method failed or is missing


@dataclass(frozen=True)
class ActionStatus:
    state: ActionState = ActionState.IDLE
    reason: str = ""
    fired: int = 0
    last_fired: Optional[float] = None


class _Pause(Exception):
    """The Client can't take input right now."""


@dataclass
class _Session:
    profile: Profile
    window: object
    next_due: dict[str, float] = field(default_factory=dict)
    statuses: dict[str, ActionStatus] = field(default_factory=dict)


class Engine:
    RETRY_DELAY = 1.0

    def __init__(self, methods, finder, rng=None, fingerprint_matcher=None):
        self._methods = {m.info.id: m for m in methods}
        self._finder = finder
        self._rng = rng or random.Random()
        self._matcher = fingerprint_matcher
        self._sessions: dict[str, _Session] = {}
        self._running = False
        self._lock = threading.RLock()

    # ----- sessions -----
    def bind(self, profile: Profile, window) -> None:
        with self._lock:
            if window is not None and getattr(window, "title", ""):
                profile.window_title = window.title
            self._sessions[profile.name] = _Session(profile, window)

    def unbind(self, profile_name: str) -> None:
        with self._lock:
            self._sessions.pop(profile_name, None)

    def bound_window(self, profile_name: str):
        with self._lock:
            session = self._sessions.get(profile_name)
            return session.window if session else None

    # ----- lifecycle -----
    @property
    def running(self) -> bool:
        return self._running

    def start(self, now: float) -> None:
        with self._lock:
            self._running = True
            for session in self._sessions.values():
                session.next_due = {}
                session.statuses = {}

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def status(self, profile_name: str, action_id: str) -> ActionStatus:
        with self._lock:
            session = self._sessions.get(profile_name)
            if session is None:
                return ActionStatus()
            return session.statuses.get(action_id, ActionStatus())

    # ----- the loop -----
    def tick(self, now: float) -> None:
        with self._lock:
            if not self._running:
                return
            for session in self._sessions.values():
                for action in session.profile.actions:
                    if not action.enabled:
                        continue
                    due = session.next_due.setdefault(action.id, now)
                    if now >= due:
                        session.next_due[action.id] = now + self._attempt(session, action, now)

    def _attempt(self, session: _Session, action: Action, now: float) -> float:
        """Try to deliver the action's input; return the delay until the next attempt."""
        previous = session.statuses.get(action.id, ActionStatus())
        try:
            window = self._ready_window(session)
            self._check_fingerprint(window, action)
            self._deliver(window, action)
        except _Pause as pause:
            session.statuses[action.id] = ActionStatus(ActionState.PAUSED, str(pause), previous.fired, previous.last_fired)
            return self.RETRY_DELAY
        except Exception as error:  # an Input Method failure must not stop the other actions
            session.statuses[action.id] = ActionStatus(ActionState.ERROR, str(error) or type(error).__name__,
                                                       previous.fired, previous.last_fired)
            return action.schedule.next_delay(self._rng)
        session.statuses[action.id] = ActionStatus(ActionState.RUNNING, "", previous.fired + 1, now)
        return action.schedule.next_delay(self._rng)

    def _ready_window(self, session: _Session):
        window = session.window
        if window is None or not window.is_alive():
            title = session.profile.window_title
            window = self._finder.find_by_title(title) if title else None
            if window is None:
                raise _Pause(f"окно «{title}» не найдено")
            session.window = window
        if window.is_minimized():
            raise _Pause("окно свёрнуто")
        return window

    def _check_fingerprint(self, window, action: Action) -> None:
        target = action.target
        if not isinstance(target, MouseTarget) or self._matcher is None:
            return
        fingerprint = target.fingerprint
        if fingerprint is None or not fingerprint.check:
            return
        if not self._matcher.matches(window, target.point, fingerprint):
            raise _Pause("отпечаток ячейки не совпал")

    def _deliver(self, window, action: Action) -> None:
        target = action.target
        method = self._methods.get(target.method_id)
        if method is None:
            raise LookupError(f"способ ввода «{target.method_id}» не найден")
        if isinstance(target, MouseTarget):
            method.click(window, target.point, target.button, target.double)
        else:
            method.press(window, target.key)
