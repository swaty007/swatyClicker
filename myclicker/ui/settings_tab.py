"""Section «Настройки»."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, TYPE_CHECKING

from myclicker.domain.keys import parse_hotkey

if TYPE_CHECKING:
    from myclicker.ui.main_window import MainWindow


class SettingsTab(ttk.Frame):
    FIELDS = [
        ("hotkey_toggle", "Старт/Стоп", str),
        ("hotkey_capture", "Добавить клик под курсором", str),
        ("hotkey_bind_window", "Привязать профиль к окну под курсором", str),
        ("default_interval", "Интервал по умолчанию, сек", float),
        ("default_jitter", "Разброс по умолчанию ±, сек", float),
        ("default_hover_delay", "Пауза после наведения перед кликом, сек", float),
        ("default_hold", "Удержание кнопки мыши, сек", float),
        ("fingerprint_size", "Размер отпечатка ячейки, пикс.", int),
        ("fingerprint_tolerance", "Допуск цвета отпечатка (0–255)", int),
        ("fingerprint_min_similarity", "Мин. совпадение отпечатка (0–1)", float),
        ("fingerprint_search_radius", "Радиус поиска сдвинутой ячейки, пикс.", int),
    ]

    def __init__(self, parent, window: "MainWindow", on_saved: Callable[[], None]):
        super().__init__(parent, padding=12)
        self.w, self.on_saved = window, on_saved
        s = self.w.c.settings
        self.vars = {}
        for row, (field, label, _) in enumerate(self.FIELDS):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 12))
            var = tk.StringVar(value=str(getattr(s, field)))
            ttk.Entry(self, textvariable=var, width=18).grid(row=row, column=1, sticky="w")
            self.vars[field] = var
        row = len(self.FIELDS)
        self.method_vars = {}
        for device, field, label in (("mouse", "default_mouse_method", "Способ мыши по умолчанию"),
                                     ("keyboard", "default_key_method", "Способ клавиатуры по умолчанию")):
            names = {m.info.name: m.info.id for m in self.w.c.methods_for(device)}
            current = next((n for n, i in names.items() if i == getattr(s, field)), "")
            var = tk.StringVar(value=current)
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Combobox(self, textvariable=var, values=list(names), state="readonly", width=34).grid(
                row=row, column=1, sticky="w")
            self.method_vars[field] = (var, names)
            row += 1
        ttk.Button(self, text="Сохранить", command=self.save).grid(row=row, column=1, sticky="w", pady=(12, 0))
        row += 1
        folder = ttk.Frame(self)
        folder.grid(row=row, column=0, columnspan=2, sticky="w", pady=(18, 0))
        ttk.Label(folder, text=f"Папка данных: {self.w.c.data_dir}").pack(side="left")
        ttk.Button(folder, text="Открыть", command=self.open_folder).pack(side="left", padx=8)

    def save(self):
        s = self.w.c.settings
        try:
            values = {}
            for field, label, kind in self.FIELDS:
                raw = self.vars[field].get().strip().replace(",", ".")
                values[field] = kind(raw)
                if field.startswith("hotkey_"):
                    values[field] = str(parse_hotkey(raw))
        except ValueError as error:
            messagebox.showerror("Настройки", f"Неверное значение: {error}", parent=self)
            return
        for field, value in values.items():
            setattr(s, field, value)
            self.vars[field].set(str(value))
        for field, (var, names) in self.method_vars.items():
            if var.get() in names:
                setattr(s, field, names[var.get()])
        self.w.c.save_settings()
        self.on_saved()
        self.w.show("Настройки сохранены.")

    def open_folder(self):
        self.w.c.data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.w.c.data_dir)
