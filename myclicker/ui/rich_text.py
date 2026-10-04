"""Read-only wrapped text where `backticked` fragments (hotkeys, API names) are shown in bold."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

_CODE = re.compile(r"`([^`]+)`")


def configure_code_tag(text: tk.Text) -> None:
    """Bold version of the widget's own font for the "kbd" tag."""
    family, size = text.cget("font").rsplit(" ", 1) if " " in str(text.cget("font")) else ("Segoe UI", "9")
    family = family.strip("{}")
    text.tag_configure("kbd", font=(family, int(size), "bold"), foreground="#1f2328")


def insert_marked(text: tk.Text, content: str, *tags: str) -> None:
    """Insert `content` at the end, turning `fragments` into the bold "kbd" style (plus any extra `tags`)."""
    position = 0
    for match in _CODE.finditer(content):
        text.insert("end", content[position:match.start()], tags)
        text.insert("end", match.group(1), tags + ("kbd",))
        position = match.end()
    text.insert("end", content[position:], tags)


class RichLabel(tk.Text):
    """A label-like Text widget: no border, no cursor, wraps words, styles `code` fragments."""

    def __init__(self, parent, lines: int = 2, foreground: str = "#57606a"):
        background = ttk.Style(parent).lookup("TFrame", "background") or "SystemButtonFace"
        super().__init__(parent, height=lines, wrap="word", relief="flat", borderwidth=0, highlightthickness=0,
                         background=background, foreground=foreground, font=("Segoe UI", 9), cursor="arrow",
                         takefocus=False, padx=0, pady=2)
        configure_code_tag(self)
        self.configure(state="disabled")
        self._content = None

    def set(self, content: str) -> None:
        if content == self._content:
            return
        self._content = content
        self.configure(state="normal")
        self.delete("1.0", "end")
        insert_marked(self, content)
        self.configure(state="disabled")
