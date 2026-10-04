"""Controller: everything the UI can ask for. The UI holds no logic of its own; tests drive this class
with fake platform services."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from myclicker.domain.compatibility import CompatibilityTable
from myclicker.domain.engine import ActionState, ActionStatus, Engine
from myclicker.domain.fingerprint import FingerprintMatcher
from myclicker.domain.model import Action, Key, KeyTarget, MouseTarget, Profile, Schedule
from myclicker.domain.research import BUILTIN_COMPATIBILITY
from myclicker.persistence.compatibility import CompatibilityStore
from myclicker.persistence.profiles import ProfileStore
from myclicker.persistence.settings import SettingsStore

log = logging.getLogger(__name__)


@dataclass
class PlatformServices:
    methods: list                                   # Input Method implementations
    finder: object                                  # find_by_title(title) -> window | None
    window_under_cursor: Callable[[], tuple]        # () -> (window | None, client Point | None)
    monotonic: Callable[[], float] = field(default=time.monotonic)


@dataclass(frozen=True)
class Summary:
    running: bool
    profiles: int        # bound profiles taking part
    active: int          # actions delivering input
    paused: int
    errors: int


class _EngineThread(threading.Thread):
    TICK = 0.02

    def __init__(self, engine: Engine, monotonic):
        super().__init__(name="engine", daemon=True)
        self._engine, self._monotonic = engine, monotonic
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                self._engine.tick(self._monotonic())
            except Exception:
                log.exception("engine tick failed")
            self._stop.wait(self.TICK)

    def stop(self):
        self._stop.set()
        self.join(2.0)


class Controller:
    def __init__(self, data_dir: Path, platform: PlatformServices):
        self.data_dir = Path(data_dir)
        self._platform = platform
        self._settings_store = SettingsStore(self.data_dir / "settings.json")
        self.settings = self._settings_store.load()
        self._store = ProfileStore(self.data_dir / "profiles")
        self.compatibility = CompatibilityTable(BUILTIN_COMPATIBILITY,
                                                CompatibilityStore(self.data_dir / "compatibility.json"))
        self.methods = {m.info.id: m for m in platform.methods}
        self.matcher = FingerprintMatcher(self.settings.fingerprint_size, self.settings.fingerprint_tolerance,
                                          self.settings.fingerprint_min_similarity)
        self.engine = Engine(platform.methods, platform.finder, fingerprint_matcher=self.matcher)
        self._profiles: dict[str, Profile] = {}
        self._thread: Optional[_EngineThread] = None
        self._lock = threading.RLock()

    # ----- settings -----
    def save_settings(self) -> None:
        self.matcher.size = self.settings.fingerprint_size
        self.matcher.tolerance = self.settings.fingerprint_tolerance
        self.matcher.min_similarity = self.settings.fingerprint_min_similarity
        self._settings_store.save(self.settings)

    # ----- input methods -----
    def methods_for(self, device: str) -> list:
        return [m for m in self.methods.values() if m.info.device == device]

    # ----- profiles -----
    def profile_names(self) -> list[str]:
        return sorted(set(self._store.list_names()) | set(self._profiles), key=str.lower)

    def profile(self, name: str) -> Profile:
        with self._lock:
            if name not in self._profiles:
                self._profiles[name] = self._store.load(name)
            return self._profiles[name]

    def create_profile(self, name: str) -> Profile:
        name = name.strip()
        if not name:
            raise ValueError("имя профиля не может быть пустым")
        if name in self.profile_names():
            raise ValueError(f"профиль «{name}» уже есть")
        profile = Profile(name=name)
        self._profiles[name] = profile
        self._store.save(profile)
        return profile

    def rename_profile(self, old: str, new: str) -> None:
        new = new.strip()
        if not new or new in self.profile_names():
            raise ValueError(f"имя «{new}» пустое или уже занято")
        with self._lock:
            window = self.bound_window(old)
            self.engine.unbind(old)
            self._store.rename(old, new)
            self._profiles.pop(old, None)
            if window is not None:
                self.bind_window(new, window)

    def delete_profile(self, name: str) -> None:
        with self._lock:
            self.engine.unbind(name)
            self._profiles.pop(name, None)
            self._store.delete(name)

    def save_profile(self, name: str) -> None:
        self._store.save(self.profile(name))

    # ----- window binding -----
    def bound_window(self, name: str):
        return self.engine.bound_window(name)

    def bind_window(self, name: str, window) -> None:
        profile = self.profile(name)
        self.engine.bind(profile, window)
        self._store.save(profile)

    def bind_window_under_cursor(self, name: str):
        window, _ = self._platform.window_under_cursor()
        if window is None:
            raise ValueError("под курсором нет окна")
        self.bind_window(name, window)
        return window

    def unbind_window(self, name: str) -> None:
        self.engine.unbind(name)

    def find_window_by_title(self, name: str):
        """Bind to the window whose title matches the one remembered in the profile."""
        title = self.profile(name).window_title
        window = self._platform.finder.find_by_title(title) if title else None
        if window is None:
            raise ValueError(f"окно «{title}» не найдено" if title else "профиль ещё не был привязан к окну")
        self.bind_window(name, window)
        return window

    # ----- actions -----
    def _new_action(self, profile: Profile, prefix: str, target) -> Action:
        number = sum(1 for a in profile.actions if type(a.target) is type(target)) + 1
        action = Action(id=uuid.uuid4().hex[:8], name=f"{prefix} {number}",
                        schedule=Schedule(self.settings.default_interval, self.settings.default_jitter),
                        target=target)
        profile.actions.append(action)
        self._store.save(profile)
        return action

    def capture_mouse_action(self, name: str) -> Action:
        """Add a mouse Action at the cursor position, with a Slot Fingerprint of what is there now."""
        window, point = self._platform.window_under_cursor()
        if window is None:
            raise ValueError("под курсором нет окна")
        bound = self.bound_window(name)
        if bound is not None and bound != window:
            raise ValueError(f"курсор над окном «{window.title}», а профиль «{name}» привязан к «{bound.title}»")
        if bound is None:
            self.bind_window(name, window)
        target = MouseTarget(point=point, method_id=self.settings.default_mouse_method,
                             fingerprint=self.matcher.take(window, point))
        return self._new_action(self.profile(name), "Клик", target)

    def add_key_action(self, name: str, key: Key, method_id: Optional[str] = None) -> Action:
        target = KeyTarget(key=key, method_id=method_id or self.settings.default_key_method)
        return self._new_action(self.profile(name), "Клавиша", target)

    def action(self, name: str, action_id: str) -> Action:
        return next(a for a in self.profile(name).actions if a.id == action_id)

    def remove_action(self, name: str, action_id: str) -> None:
        profile = self.profile(name)
        profile.actions = [a for a in profile.actions if a.id != action_id]
        self._store.save(profile)

    def refresh_fingerprint(self, name: str, action_id: str) -> None:
        action = self.action(name, action_id)
        window = self.bound_window(name)
        if window is None or not isinstance(action.target, MouseTarget):
            raise ValueError("профиль не привязан к окну")
        fingerprint = self.matcher.take(window, action.target.point)
        if fingerprint is None:
            raise ValueError("не удалось снять окно (оно свёрнуто?)")
        if action.target.fingerprint is not None:
            fingerprint.check = action.target.fingerprint.check
        action.target.fingerprint = fingerprint
        self._store.save(self.profile(name))

    def test_action(self, name: str, action_id: str, method_id: Optional[str] = None) -> None:
        """Deliver the action's input once right now, optionally through another Input Method."""
        action = self.action(name, action_id)
        window = self.bound_window(name)
        if window is None:
            raise ValueError("сначала привяжите профиль к окну")
        method = self.methods[method_id or action.target.method_id]
        target = action.target
        if isinstance(target, MouseTarget):
            if method.info.device != "mouse":
                raise ValueError("для клика нужен способ ввода мыши")
            method.click(window, target.point, target.button, target.double)
        else:
            if method.info.device != "keyboard":
                raise ValueError("для клавиши нужен способ ввода клавиатуры")
            method.press(window, target.key)

    # ----- running -----
    @property
    def running(self) -> bool:
        return self.engine.running

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self.engine.start(self._platform.monotonic())
            self._thread = _EngineThread(self.engine, self._platform.monotonic)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self.engine.stop()
            if self._thread is not None:
                self._thread.stop()
                self._thread = None

    def toggle(self) -> bool:
        if self.running:
            self.stop()
        else:
            self.start()
        return self.running

    def status(self, name: str, action_id: str) -> ActionStatus:
        return self.engine.status(name, action_id)

    def summary(self) -> Summary:
        profiles = active = paused = errors = 0
        for name in list(self._profiles):
            if self.bound_window(name) is None:
                continue
            profiles += 1
            for action in self._profiles[name].actions:
                if not action.enabled:
                    continue
                state = self.status(name, action.id).state
                active += state == ActionState.RUNNING
                paused += state == ActionState.PAUSED
                errors += state == ActionState.ERROR
        return Summary(self.running, profiles, active, paused, errors)

    def shutdown(self) -> None:
        self.stop()
        self.settings.last_profiles = [n for n in self._profiles if self.bound_window(n) is not None]
        self.save_settings()
