"""Modal dialog for editing an Action."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from myclicker.domain.keys import key_by_name, key_by_vk, key_names
from myclicker.domain.model import Action, KeyTarget, MouseTarget, Point, Schedule
from myclicker.ui.texts import BUTTONS, BUTTONS_BY_TEXT


class ActionDialog(tk.Toplevel):
    """Edits `action` in place when the user presses OK; `self.ok` tells whether they did."""

    def __init__(self, parent, action: Action, methods: list, title: str):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.action = action
        self.ok = False
        self._methods = {m.info.name: m.info.id for m in methods}
        self._method_names = {m.info.id: m.info.name for m in methods}
        target = action.target

        form = ttk.Frame(self, padding=12)
        form.pack(fill="both", expand=True)
        row = 0

        def add(label, widget):
            nonlocal row
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 10))
            widget.grid(row=row, column=1, sticky="we", pady=3)
            row += 1

        self.name = tk.StringVar(value=action.name)
        add("Название", ttk.Entry(form, textvariable=self.name, width=34))

        self.method = tk.StringVar(value=self._method_names.get(target.method_id, target.method_id))
        add("Способ ввода", ttk.Combobox(form, textvariable=self.method, values=list(self._methods),
                                         state="readonly", width=32))

        self.interval = tk.StringVar(value=f"{action.schedule.interval:g}")
        add("Интервал, сек", ttk.Entry(form, textvariable=self.interval, width=10))
        self.jitter = tk.StringVar(value=f"{action.schedule.jitter:g}")
        add("Случайный разброс ±, сек", ttk.Entry(form, textvariable=self.jitter, width=10))

        if isinstance(target, MouseTarget):
            point = ttk.Frame(form)
            self.x = tk.StringVar(value=str(target.point.x))
            self.y = tk.StringVar(value=str(target.point.y))
            ttk.Label(point, text="X").pack(side="left")
            ttk.Entry(point, textvariable=self.x, width=7).pack(side="left", padx=(2, 10))
            ttk.Label(point, text="Y").pack(side="left")
            ttk.Entry(point, textvariable=self.y, width=7).pack(side="left", padx=2)
            add("Точка в окне", point)
            self.button = tk.StringVar(value=BUTTONS[target.button])
            add("Кнопка мыши", ttk.Combobox(form, textvariable=self.button, values=list(BUTTONS_BY_TEXT),
                                            state="readonly", width=12))
            self.double = tk.BooleanVar(value=target.double)
            add("", ttk.Checkbutton(form, text="Двойной клик", variable=self.double))
            self.check = tk.BooleanVar(value=bool(target.fingerprint and target.fingerprint.check))
            check = ttk.Checkbutton(form, text="Проверять отпечаток ячейки перед кликом", variable=self.check)
            if target.fingerprint is None:
                check.state(["disabled"])
            add("", check)
        else:
            keys = ttk.Frame(form)
            self.key = tk.StringVar(value=target.key.name)
            ttk.Combobox(keys, textvariable=self.key, values=key_names(), width=14).pack(side="left")
            self._press_button = ttk.Button(keys, text="Нажать клавишу…", command=self._wait_for_key)
            self._press_button.pack(side="left", padx=6)
            add("Клавиша", keys)

        self.enabled = tk.BooleanVar(value=action.enabled)
        add("", ttk.Checkbutton(form, text="Включено", variable=self.enabled))

        self.error = ttk.Label(form, foreground="#b00020")
        self.error.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        buttons = ttk.Frame(form)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="OK", command=self._accept).pack(side="left", padx=4)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left")
        self.bind("<Return>", lambda e: self._accept())
        self.bind("<Escape>", lambda e: self.destroy())

        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _wait_for_key(self):
        self._press_button.configure(text="…нажмите")

        def on_key(event):
            self.key.set(key_by_vk(event.keycode).name)   # on Windows keycode is the virtual-key code
            self._press_button.configure(text="Нажать клавишу…")
            self.unbind("<KeyPress>")
            self.bind("<Return>", lambda e: self._accept())
            return "break"

        self.unbind("<Return>")
        self.bind("<KeyPress>", on_key)

    def _parse(self) -> Optional[str]:
        """Apply the form to the action; return an error message instead if something is wrong."""
        try:
            interval = float(self.interval.get().replace(",", "."))
            jitter = float(self.jitter.get().replace(",", "."))
        except ValueError:
            return "интервал и разброс — числа, например 5 или 0.5"
        if interval < Schedule.MIN_DELAY or jitter < 0:
            return f"интервал не меньше {Schedule.MIN_DELAY} с, разброс не отрицательный"
        method_id = self._methods.get(self.method.get())
        if method_id is None:
            return "выберите способ ввода"
        target = self.action.target
        if isinstance(target, MouseTarget):
            try:
                point = Point(int(self.x.get()), int(self.y.get()))
            except ValueError:
                return "координаты — целые числа"
            target.point = point
            target.button = BUTTONS_BY_TEXT[self.button.get()]
            target.double = self.double.get()
            if target.fingerprint is not None:
                target.fingerprint.check = self.check.get()
        else:
            try:
                key = key_by_name(self.key.get())
            except ValueError as error:
                return str(error)
            self.action.target = KeyTarget(key=key, method_id=method_id)
            target = self.action.target
        target.method_id = method_id
        self.action.name = self.name.get().strip() or self.action.name
        self.action.schedule = Schedule(interval, jitter)
        self.action.enabled = self.enabled.get()
        return None

    def _accept(self):
        problem = self._parse()
        if problem:
            self.error.configure(text=problem)
            return
        self.ok = True
        self.destroy()
