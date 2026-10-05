"""Section «Info»: how each Input Method works."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from myclicker.ui import method_docs
from myclicker.ui.rich_text import configure_code_tag, insert_marked
from myclicker.ui.texts import COMPAT

if TYPE_CHECKING:
    from myclicker.ui.main_window import MainWindow


class InfoTab(ttk.Frame):
    """Reference: general principles of input emulation and an article for every Input Method."""

    def __init__(self, parent, window: "MainWindow"):
        super().__init__(parent, padding=6)
        self.w = window
        left = ttk.Frame(self)
        left.pack(side="left", fill="y")
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse", height=24)
        self.tree.column("#0", width=260)
        self.tree.pack(fill="y", expand=True)
        self.tree.insert("", "end", iid="general", text=method_docs.GENERAL_TITLE)
        for device, title in (("mouse", "Мышь"), ("keyboard", "Клавиатура")):
            group = self.tree.insert("", "end", iid=device, text=title, open=True)
            for method in self.w.c.methods_for(device):
                self.tree.insert(group, "end", iid=method.info.id, text=method.info.name)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show(self.tree.selection()[0]))

        box = ttk.Frame(self)
        box.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.text = tk.Text(box, wrap="word", font=("Segoe UI", 10), padx=14, pady=10, relief="flat",
                            background="#ffffff", cursor="arrow")
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.text.tag_configure("h1", font=("Segoe UI", 14, "bold"), spacing3=6)
        self.text.tag_configure("h2", font=("Segoe UI", 10, "bold"), spacing1=10, spacing3=2)
        self.text.tag_configure("meta", foreground="#57606a")
        self.text.tag_configure("body", spacing3=4)
        configure_code_tag(self.text)
        self.tree.selection_set("general")

    # Windows API names in the articles are shown like code.
    _API = re.compile(r"(?<![`\w])(WM_[A-Z]+|[A-Z]+_[A-Z_]+|mouse_event|keybd_event|"
                      r"(?:Get|Set|Send|Post|Print|Map|Window|Client|Screen|Is|Register)[A-Z]\w*|"
                      r"PostMessage|SendMessage|SendInput|PrintWindow|INJECTED|DirectInput|Raw Input|"
                      r"interception\.dll)(?![`\w])")

    def _write(self, parts):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for text, tag in parts:
            if tag in ("body", "meta"):
                insert_marked(self.text, self._API.sub(r"`\1`", text) + "\n", tag)
            else:
                self.text.insert("end", text + "\n", tag)
        self.text.configure(state="disabled")

    def show(self, item: str):
        if item in ("mouse", "keyboard"):
            return
        if item == "general":
            parts = [(method_docs.GENERAL_TITLE, "h1")]
            for heading, body in method_docs.GENERAL:
                parts += [(heading, "h2"), (body, "body")]
            self._write(parts)
            return
        method = self.w.c.methods[item]
        info, doc = method.info, method_docs.METHODS.get(item, {})
        ok, why = method.available()
        app = self.w.c.settings.compatibility_app
        entry = self.w.c.compatibility.entry(app, item)
        meta = (f"{'Мышь' if info.device == 'mouse' else 'Клавиатура'} · "
                f"{'нужен фокус (окно на мгновение становится активным)' if info.needs_focus else 'работает в фоне'}"
                f" · {'доступен' if ok else 'недоступен: ' + why}")
        parts = [(info.name, "h1"), (meta, "meta")]
        for heading, key in (("Как работает", "how"), ("Плюсы", "pros"), ("Минусы и особенности", "cons")):
            if doc.get(key):
                parts += [(heading, "h2"), (doc[key], "body")]
        parts += [(f"{app}: {COMPAT[entry.status]}", "h2"), (entry.note or "Результатов пока нет.", "body")]
        self._write(parts)
