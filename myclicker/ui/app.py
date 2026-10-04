"""Application shell: main window + Mini Panel + global hotkeys, all on the tkinter thread."""
from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import ttk

from myclicker.domain.keys import parse_hotkey
from myclicker.platform_win.hotkeys import HotkeyListener
from myclicker.ui.main_window import MainWindow
from myclicker.ui.mini_panel import MiniPanel

log = logging.getLogger(__name__)
REFRESH_MS = 300


class App:
    def __init__(self, controller, warnings: list[str] = ()):
        self.c = controller
        self.root = tk.Tk()
        ttk.Style(self.root).theme_use("vista" if "vista" in ttk.Style().theme_names() else "clam")
        self._events: queue.Queue[str] = queue.Queue()
        self._hotkeys = None

        self.main = MainWindow(self.root, controller, on_toggle=self.toggle, on_settings_saved=self.restart_hotkeys)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_main)
        s = controller.settings
        self.mini = MiniPanel(self.root, s.mini_panel_x, s.mini_panel_y, on_toggle=self.toggle,
                              on_open=self.show_main, on_exit=self.exit, on_moved=self._mini_moved)
        self.restart_hotkeys()
        for warning in warnings:
            self.main.show(warning, error=True)

    # ----- hotkeys (arrive on another thread, handled here) -----
    def restart_hotkeys(self):
        if self._hotkeys is not None:
            self._hotkeys.stop()
        s = self.c.settings
        hotkeys = {}
        for name, text in (("toggle", s.hotkey_toggle), ("capture", s.hotkey_capture),
                           ("bind", s.hotkey_bind_window)):
            try:
                hotkeys[name] = parse_hotkey(text)
            except ValueError as error:
                self.main.show(f"Горячая клавиша «{text}»: {error}", error=True)
        self._hotkeys = HotkeyListener(hotkeys, self._events.put)
        self._hotkeys.start()
        if self._hotkeys.failed:
            self.main.show("Занято другой программой: " + ", ".join(self._hotkeys.failed) +
                           " — смените сочетание в настройках.", error=True)

    def _handle(self, name: str):
        profile = self.main.profile_name
        if name == "toggle":
            self.toggle()
            return
        if not profile:
            self._report("Сначала выберите профиль в MyClicker.", error=True)
            return
        try:
            if name == "capture":
                action = self.c.capture_mouse_action(profile)
                self.main.mouse_tab.reload(select=action.id)
                self.main.profiles.refresh()
                self._report(f"Добавлено «{action.name}» в профиль «{profile}» "
                             f"({action.target.point.x}, {action.target.point.y}).")
            elif name == "bind":
                window = self.c.bind_window_under_cursor(profile)
                self.main.profiles.refresh()
                self._report(f"Профиль «{profile}» привязан к окну «{window.title}».")
        except (ValueError, OSError) as error:
            self._report(str(error), error=True)

    def _report(self, text: str, error: bool = False):
        self.main.show(text, error)
        self.mini.show_state(self.c.running, text[:60], alert=error)
        self._mini_message_until = 12   # keep the message for a few refreshes

    # ----- commands -----
    def toggle(self):
        self.c.toggle()
        self.refresh()

    def hide_main(self):
        self.root.withdraw()

    def show_main(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def exit(self):
        try:
            if self._hotkeys is not None:
                self._hotkeys.stop()
            self.c.shutdown()
        finally:
            self.root.destroy()

    def _mini_moved(self, x: int, y: int):
        self.c.settings.mini_panel_x, self.c.settings.mini_panel_y = x, y
        self.c.save_settings()

    # ----- periodic refresh -----
    _mini_message_until = 0

    def refresh(self):
        self.main.refresh()
        summary = self.c.summary()
        if self._mini_message_until > 0:
            self._mini_message_until -= 1
            return
        if summary.running:
            text = f"{summary.profiles} проф. · ▶ {summary.active}"
            if summary.paused:
                text += f" · ⏸ {summary.paused}"
            if summary.errors:
                text += f" · ⚠ {summary.errors}"
        else:
            text = f"остановлено · окон: {summary.profiles}"
        self.mini.show_state(summary.running, text, alert=bool(summary.paused or summary.errors))

    def _tick(self):
        try:
            while True:
                self._handle(self._events.get_nowait())
        except queue.Empty:
            pass
        except Exception:
            log.exception("UI event failed")
        try:
            self.refresh()
        except Exception:
            log.exception("UI refresh failed")
        self.root.after(REFRESH_MS, self._tick)

    def run(self):
        self.root.after(REFRESH_MS, self._tick)
        self.root.mainloop()
