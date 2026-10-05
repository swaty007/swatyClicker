"""Section «Способы ввода»: every Input Method and what is known about it for a program."""
from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk
from typing import Optional, TYPE_CHECKING

from myclicker.domain.compatibility import Status
from myclicker.ui.dialogs import NoteDialog, Tooltip
from myclicker.ui.texts import COMPAT
from myclicker.ui.widgets import tree_table

if TYPE_CHECKING:
    from myclicker.ui.main_window import MainWindow


class CompatibilityTab(ttk.Frame):
    """All Input Methods with what is known about them for a program; the user can add their own marks."""

    def __init__(self, parent, window: "MainWindow"):
        super().__init__(parent, padding=6)
        self.w = window
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Программа:").pack(side="left")
        self.app = tk.StringVar(value=self.w.c.settings.compatibility_app)
        self.apps = ttk.Combobox(top, textvariable=self.app, state="readonly", width=20)
        self.apps.pack(side="left", padx=6)
        self.apps.bind("<<ComboboxSelected>>", lambda e: self.reload())
        ttk.Button(top, text="Добавить программу", command=self.add_app).pack(side="left")
        ttk.Button(top, text="Проверить доступность", command=self.reload).pack(side="left", padx=6)
        ttk.Label(self, wraplength=900, foreground="#57606a",
                  text="Статусы LU4 — результаты нашего исследования (docs/research/lu4-input-methods.md). "
                       "Свои результаты отмечайте кнопками ниже — они хранятся в data/compatibility.json. "
                       "«Тест» отправляет выбранное действие текущего профиля этим способом один раз."
                  ).pack(fill="x", pady=6)
        self.tree = tree_table(self, [("device", "Устройство", 85), ("method", "Способ ввода", 220),
                                 ("mode", "Режим", 95), ("available", "Доступен", 150),
                                 ("status", "Статус", 120), ("note", "Комментарий", 330), ("source", "Источник", 95)])
        self.tree.bind("<Double-1>", lambda e: self.comment())
        Tooltip(self.tree, self._hover_text)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(6, 0))
        for status in (Status.WORKS, Status.PARTIAL, Status.FAILS, Status.UNTESTED):
            ttk.Button(buttons, text=COMPAT[status], command=lambda s=status: self.mark(s)).pack(side="left",
                                                                                                padx=(0, 4))
        ttk.Button(buttons, text="Комментарий…", command=self.comment).pack(side="left", padx=(8, 4))
        ttk.Button(buttons, text="Сбросить", command=self.reset).pack(side="left", padx=(0, 4))
        ttk.Button(buttons, text="Тест", command=self.test).pack(side="left", padx=(8, 0))
        self.reload()

    def reload(self):
        table = self.w.c.compatibility
        apps = table.apps()
        if self.app.get() not in apps:
            apps.append(self.app.get())
        self.apps.configure(values=apps)
        selected = (self.tree.selection() or [None])[0]
        self.tree.delete(*self.tree.get_children())
        for method in self.w.c.methods.values():
            info = method.info
            ok, why = method.available()
            entry = table.entry(self.app.get(), info.id)
            source = "моя отметка" if table.is_user_marked(self.app.get(), info.id) else (
                "исследование" if entry.status != Status.UNTESTED or entry.note else "")
            self.tree.insert("", "end", iid=info.id, values=(
                "Мышь" if info.device == "mouse" else "Клавиатура", info.name,
                "нужен фокус" if info.needs_focus else "фон", "да" if ok else f"нет: {why}",
                COMPAT[entry.status], entry.note, source))
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)

    def _selected(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def mark(self, status: Status):
        method_id = self._selected()
        if method_id:
            note = self.w.c.compatibility.entry(self.app.get(), method_id).note
            self.w.c.compatibility.mark(self.app.get(), method_id, status, note)
            self.reload()

    def _hover_text(self, event) -> str:
        """Full description, availability and comment of the row under the cursor."""
        method_id = self.tree.identify_row(event.y)
        if not method_id:
            return ""
        method = self.w.c.methods[method_id]
        entry = self.w.c.compatibility.entry(self.app.get(), method_id)
        ok, why = method.available()
        lines = [method.info.name, method.info.description]
        if not ok:
            lines.append(f"Недоступен: {why}")
        lines.append(f"{self.app.get()}: {COMPAT[entry.status]}")
        if entry.note:
            lines.append(entry.note)
        lines.append("Двойной щелчок — изменить комментарий")
        return "\n".join(line for line in lines if line)

    def comment(self):
        method_id = self._selected()
        if not method_id:
            return
        entry = self.w.c.compatibility.entry(self.app.get(), method_id)
        dialog = NoteDialog(self, "Комментарий",
                            f"{self.w.c.methods[method_id].info.name} — {self.app.get()}", entry.note)
        self.wait_window(dialog)
        if dialog.text is not None:
            self.w.c.compatibility.mark(self.app.get(), method_id, entry.status, dialog.text)
            self.reload()

    def reset(self):
        method_id = self._selected()
        if method_id:
            self.w.c.compatibility.reset(self.app.get(), method_id)
            self.reload()

    def add_app(self):
        name = simpledialog.askstring("Программа", "Название программы или игры:", parent=self)
        if name and name.strip():
            self.app.set(name.strip())
            self.w.c.settings.compatibility_app = name.strip()
            self.w.c.save_settings()
            self.reload()

    def test(self):
        method_id = self._selected()
        if not method_id:
            return
        device = self.w.c.methods[method_id].info.device
        tab = self.w.mouse_tab if device == "mouse" else self.w.keyboard_tab
        action = tab.selected()
        if action is None:
            self.w.show(f"Выберите действие на вкладке «{'Мышь' if device == 'mouse' else 'Клавиатура'}».",
                        error=True)
            return
        if self.w.guard(lambda: self.w.c.test_action(self.w.profile_name, action.id, method_id)):
            self.w.show(f"Отправлено способом «{self.w.c.methods[method_id].info.name}». "
                        f"Проверьте игру и отметьте результат.")
