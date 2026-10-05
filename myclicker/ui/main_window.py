"""Main window: profiles on the left; sections for mouse Actions, keyboard Actions, Input Methods,
settings and info."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from myclicker.ui.actions_tab import ActionsTab
from myclicker.ui.compatibility_tab import CompatibilityTab
from myclicker.ui.info_tab import InfoTab
from myclicker.ui.profiles_panel import ProfilesPanel
from myclicker.ui.settings_tab import SettingsTab
from myclicker.ui.widgets import TabBar


class MainWindow:
    def __init__(self, root: tk.Tk, controller, on_toggle: Callable, on_settings_saved: Callable,
                 on_show_mini: Callable):
        self.root, self.c = root, controller
        self.profile_name: Optional[str] = None
        root.title("MyClicker")
        root.geometry("1180x640")
        root.minsize(900, 500)

        self.tab_bar = TabBar(root, self.select_tab)
        self.tab_bar.pack(fill="x")
        body = ttk.PanedWindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self.profiles = ProfilesPanel(body, self)
        body.add(self.profiles, weight=1)
        self.pages = ttk.Frame(body)
        body.add(self.pages, weight=3)
        self.mouse_tab = ActionsTab(self.pages, self, "mouse")
        self.keyboard_tab = ActionsTab(self.pages, self, "keyboard")
        self.compat_tab = CompatibilityTab(self.pages, self)
        self.settings_tab = SettingsTab(self.pages, self, on_settings_saved)
        self.info_tab = InfoTab(self.pages, self)
        self._tabs = {"Мышь": self.mouse_tab, "Клавиатура": self.keyboard_tab,
                      "Способы ввода": self.compat_tab, "Настройки": self.settings_tab, "Info": self.info_tab}
        for title in self._tabs:
            self.tab_bar.add(title)
        self.select_tab("Мышь" if self.c.profile_names() else "Способы ввода")

        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        self.toggle_button = ttk.Button(bar, text="", command=on_toggle, width=26)
        self.toggle_button.pack(side="left")
        ttk.Button(bar, text="Мини-панель", command=on_show_mini).pack(side="left", padx=(8, 0))
        self.message = ttk.Label(bar, text="")
        self.message.pack(side="left", padx=12)

        self.profiles.reload()
        names = self.c.profile_names()
        if names:
            self.profiles.tree.selection_set(names[0])

    def select_tab(self, title: str):
        for name, page in self._tabs.items():
            if name == title:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        self.tab_bar.set_active(title)

    # ----- shared helpers -----
    def show(self, text: str, error: bool = False):
        self.message.configure(text=text, foreground="#b00020" if error else "#1a7f37")

    def guard(self, fn) -> bool:
        """Run `fn`; report a failure in the status bar instead of crashing the UI."""
        try:
            fn()
            return True
        except (ValueError, OSError, LookupError, NotImplementedError) as error:
            self.show(str(error), error=True)
            return False

    def on_profile_selected(self, name: Optional[str]):
        self.profile_name = name
        self.mouse_tab.reload()
        self.keyboard_tab.reload()

    def refresh(self):
        running = self.c.running
        hotkey = self.c.settings.hotkey_toggle
        self.toggle_button.configure(text=f"■ Стоп ({hotkey})" if running else f"▶ Старт ({hotkey})")
        self.profiles.refresh()
        self.mouse_tab.refresh()
        self.keyboard_tab.refresh()
