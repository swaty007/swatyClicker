"""Mini Panel: a small always-on-top window with Start/Stop, "open the app" and a status line."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

BG, FG, ACCENT, STOP = "#1f2328", "#e6edf3", "#2ea043", "#da3633"


class MiniPanel(tk.Toplevel):
    def __init__(self, root, x: int, y: int, on_toggle: Callable, on_open: Callable, on_close: Callable,
                 on_moved: Callable[[int, int], None]):
        super().__init__(root)
        self.overrideredirect(True)          # no title bar: dragged by its body instead
        self.attributes("-topmost", True)
        self.configure(bg=BG, highlightthickness=1, highlightbackground="#444c56")
        self._on_moved = on_moved
        self._drag_from = None

        self.toggle_button = tk.Button(self, text="▶ Старт", width=8, command=on_toggle, bg=ACCENT, fg="white",
                                       activebackground=ACCENT, relief="flat", font=("Segoe UI", 9, "bold"))
        self.toggle_button.pack(side="left", padx=(4, 2), pady=4)
        tk.Button(self, text="☰", width=3, command=on_open, bg="#30363d", fg=FG, relief="flat",
                  activebackground="#444c56").pack(side="left", padx=2, pady=4)
        self.status = tk.Label(self, text="", bg=BG, fg=FG, font=("Segoe UI", 9), anchor="w")
        self.status.pack(side="left", padx=6)
        tk.Button(self, text="✕", width=2, command=on_close, bg=BG, fg="#8b949e", relief="flat",
                  activebackground="#30363d").pack(side="right", padx=(2, 4), pady=4)

        for widget in (self, self.status):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)
        self.geometry(f"+{x}+{y}")

    def show_state(self, running: bool, text: str, alert: bool = False) -> None:
        if running:
            self.toggle_button.configure(text="■ Стоп", bg=STOP, activebackground=STOP)
        else:
            self.toggle_button.configure(text="▶ Старт", bg=ACCENT, activebackground=ACCENT)
        self.status.configure(text=text, fg="#f0883e" if alert else FG)

    def _start_drag(self, event):
        self._drag_from = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag(self, event):
        if self._drag_from:
            dx, dy = self._drag_from
            self.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _end_drag(self, _event):
        if self._drag_from:
            self._drag_from = None
            self._on_moved(self.winfo_x(), self.winfo_y())
