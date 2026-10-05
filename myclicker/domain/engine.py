"""Engine: runs the Actions of every bound Profile on schedule through their Input Methods.

Time is passed in explicitly (`now`, seconds from a monotonic clock), so the engine is
driven by a background thread in production and by plain calls in tests.

An Action whose Client cannot take input right now (minimized, closed, Slot Fingerprint
mismatch) is PAUSED and retried every RETRY_DELAY seconds; it resumes by itself. A slot that is not found
is searched for less and less often (RETRY_DELAY doubled up to MAX_SEARCH_DELAY): every search captures
the window and scans `search_radius` pixels around the point.
"""
from __future__ import annotations

import enum
import random
import threading
from dataclasses import dataclass, field
from typing import Optional

from myclicker.domain.fingerprint import SlotCheck
from myclicker.domain.input import deliver
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
    checks: int = 0                                  # Slot Fingerprint checks since Start
    moves: int = 0                                   # of them: the slot was found elsewhere and followed
    last_shift: Optional[tuple[int, int]] = None     # (dx, dy) of the latest move, in pixels


class _Pause(Exception):
    """The Client can't take input right now."""

    def __init__(self, reason: str, check: Optional[SlotCheck] = None):
        super().__init__(reason)
        self.check = check


class _Cancelled(Exception):
    """The run ended or the Profile was unbound while the attempt was under way."""


@dataclass
class _Attempt:
    """What one try to deliver an action's input came to."""
    state: ActionState = ActionState.RUNNING
    reason: str = ""
    window: object = None               # the window the input went to, if one was found
    check: Optional[SlotCheck] = None   # the Slot Fingerprint check, if one was made

    @property
    def slot_missing(self) -> bool:
        return self.check is not None and self.check.point is None

    def status(self, previous: ActionStatus, now: float) -> ActionStatus:
        checks, moves, last_shift = previous.checks, previous.moves, previous.last_shift
        if self.check is not None:
            checks += 1
            if self.check.moved:
                moves, last_shift = moves + 1, self.check.shift
        if self.state == ActionState.RUNNING:
            return ActionStatus(self.state, "", previous.fired + 1, now, checks, moves, last_shift)
        return ActionStatus(self.state, self.reason, previous.fired, previous.last_fired, checks, moves, last_shift)


@dataclass
class _Session:
    profile: Profile
    window: object
    next_due: dict[str, float] = field(default_factory=dict)
    statuses: dict[str, ActionStatus] = field(default_factory=dict)
    misses: dict[str, int] = field(default_factory=dict)   # searches in a row that did not find the slot


class Engine:
    RETRY_DELAY = 1.0
    MAX_SEARCH_DELAY = 8.0

    def __init__(self, methods, finder, rng=None, fingerprint_matcher=None, on_target_moved=None):
        self._methods = {m.info.id: m for m in methods}
        self._finder = finder
        self._rng = rng or random.Random()
        self._matcher = fingerprint_matcher
        self._on_target_moved = on_target_moved   # (profile, action) -> None, e.g. to save the new point
        self._sessions: dict[str, _Session] = {}
        self._running = False
        self._run = 0   # increases on every Start: an attempt begun in an earlier run must not send anything
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
            self._run += 1
            for session in self._sessions.values():
                session.next_due = {}
                session.statuses = {}
                session.misses = {}

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
        """Attempt every due action. The lock guards only the bookkeeping: window lookup, the Slot Fingerprint
        check and the Mouse Click itself run outside it, so the UI and Stop never wait for a click.

        Stop, a new Start or unbinding the Profile may come while an attempt is under way; the attempt then
        sends nothing and changes nothing (see `_current`)."""
        run, due = self._due(now)
        for session, action in due:
            attempt = self._attempt(session, action, run)
            with self._lock:
                if attempt is None or not self._current(session, run):
                    continue
                if attempt.window is not None:
                    session.window = attempt.window
                session.statuses[action.id] = attempt.status(session.statuses.get(action.id, ActionStatus()), now)
                session.next_due[action.id] = now + self._reschedule(session, action, attempt)

    def _current(self, session: _Session, run: int) -> bool:
        """Still the same run of the engine, and the session still bound. Call under the lock."""
        return self._running and self._run == run and self._sessions.get(session.profile.name) is session

    def _still_current(self, session: _Session, run: int) -> bool:
        with self._lock:
            return self._current(session, run)

    def _reschedule(self, session: _Session, action: Action, attempt: _Attempt) -> float:
        """Delay until the next attempt; counts the searches in a row that did not find the slot."""
        if not attempt.slot_missing:
            session.misses.pop(action.id, None)
            if attempt.state == ActionState.PAUSED:
                return self.RETRY_DELAY
            return action.schedule.next_delay(self._rng)
        misses = session.misses.get(action.id, 0)
        session.misses[action.id] = misses + 1
        return min(self.MAX_SEARCH_DELAY, self.RETRY_DELAY * 2 ** misses)

    def _due(self, now: float) -> tuple[int, list[tuple[_Session, Action]]]:
        with self._lock:
            due = []
            if self._running:
                for session in self._sessions.values():
                    for action in list(session.profile.actions):
                        if action.enabled and now >= session.next_due.setdefault(action.id, now):
                            due.append((session, action))
            return self._run, due

    def _attempt(self, session: _Session, action: Action, run: int) -> Optional[_Attempt]:
        """Try to deliver the action's input once; None when the run ended or the Profile was unbound meanwhile."""
        attempt = _Attempt()
        try:
            if not self._still_current(session, run):
                return None
            attempt.window = self._ready_window(session)
            attempt.check = self._check_fingerprint(attempt.window, session, action, run)
            if not self._still_current(session, run):
                return None
            self._deliver(attempt.window, action)
        except _Cancelled:
            return None
        except _Pause as pause:
            attempt.state, attempt.reason = ActionState.PAUSED, str(pause)
            attempt.check = attempt.check or pause.check
        except Exception as error:  # an Input Method failure must not stop the other actions
            attempt.state, attempt.reason = ActionState.ERROR, str(error) or type(error).__name__
        return attempt

    def _ready_window(self, session: _Session):
        window = session.window
        if window is None or not window.is_alive():
            title = session.profile.window_title
            window = self._finder.find_by_title(title) if title else None
            if window is None:
                raise _Pause(f"окно «{title}» не найдено")
        if window.is_minimized():
            raise _Pause("окно свёрнуто")
        return window

    def _check_fingerprint(self, window, session: _Session, action: Action, run: int) -> Optional[SlotCheck]:
        """None when this action has no Slot Fingerprint to check; pauses when the slot is not found."""
        target = action.target
        if not isinstance(target, MouseTarget) or self._matcher is None:
            return None
        fingerprint = target.fingerprint
        if fingerprint is None or not fingerprint.check:
            return None
        check = self._matcher.check(window, target.point, fingerprint, target.relocate)
        if check.point is None:
            raise _Pause("отпечаток ячейки не совпал", check)
        if check.moved:
            with self._lock:   # unbinding (deleting, renaming) the Profile must not interleave with the save
                if not self._current(session, run):
                    raise _Cancelled
                target.point = check.point
                if self._on_target_moved is not None:
                    self._on_target_moved(session.profile, action)
        return check

    def _deliver(self, window, action: Action) -> None:
        method = self._methods.get(action.target.method_id)
        if method is None:
            raise LookupError(f"способ ввода «{action.target.method_id}» не найден")
        deliver(method, window, action.target)
