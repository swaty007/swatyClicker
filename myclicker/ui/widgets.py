"""Small widgets shared by the main window's sections."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable



def tree_table(parent, columns: list[tuple[str, str, int]], height=12, show="headings") -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show=show, height=height,
                        selectmode="browse")
    for column, title, width in columns:
        tree.heading(column, text=title)
        tree.column(column, width=width, stretch=column in ("status", "note", "name", "window"))
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


class TabBar(tk.Frame):
    """Top menu of sections; the active one is clearly highlighted (ttk.Notebook tabs are hard to tell apart)."""
    BG, IDLE, IDLE_HOVER, ACTIVE = "#24292f", "#24292f", "#32383f", "#0969da"

    def __init__(self, parent, on_select: Callable[[str], None]):
        super().__init__(parent, bg=self.BG)
        self._on_select = on_select
        self._buttons: dict[str, tk.Label] = {}
        self._active = None

    def add(self, title: str):
        label = tk.Label(self, text=title, bg=self.IDLE, fg="#d0d7de", padx=18, pady=8, cursor="hand2",
                         font=("Segoe UI", 10))
        label.pack(side="left")
        label.bind("<Button-1>", lambda e: self._on_select(title))
        label.bind("<Enter>", lambda e: title != self._active and label.configure(bg=self.IDLE_HOVER))
        label.bind("<Leave>", lambda e: title != self._active and label.configure(bg=self.IDLE))
        self._buttons[title] = label

    def set_active(self, title: str):
        self._active = title
        for name, label in self._buttons.items():
            active = name == title
            label.configure(bg=self.ACTIVE if active else self.IDLE, fg="white" if active else "#d0d7de",
                            font=("Segoe UI", 10, "bold" if active else "normal"))
