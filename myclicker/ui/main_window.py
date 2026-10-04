"""Main window: profiles on the left; tabs for mouse Actions, keyboard Actions, Input Methods and settings."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Optional

from myclicker.domain.compatibility import Status
from myclicker.domain.engine import ActionState
from myclicker.domain.keys import key_by_name, parse_hotkey
from myclicker.domain.model import Action, KeyTarget, MouseTarget, Schedule
from myclicker.ui.dialogs import ActionDialog
from myclicker.ui.texts import BUTTONS, COMPAT, schedule_text, status_text


def _tree(parent, columns: list[tuple[str, str, int]], height=12) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height,
                        selectmode="browse")
    for column, title, width in columns:
        tree.heading(column, text=title)
        tree.column(column, width=width, stretch=column in ("status", "note", "name", "window"))
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


class ProfilesPanel(ttk.LabelFrame):
    def __init__(self, parent, window: "MainWindow"):
        super().__init__(parent, text="Профили", padding=6)
        self.w = window
        self.tree = _tree(self, [("name", "Профиль", 120), ("window", "Окно", 150), ("state", "Статус", 90)], 14)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.w.on_profile_selected(self.selected()))
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(6, 0))
        for text, command in (("Новый", self.new), ("Переименовать", self.rename), ("Удалить", self.delete)):
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 4))
        bind = ttk.Frame(self)
        bind.pack(fill="x", pady=(6, 0))
        self.bind_hint = ttk.Label(bind, wraplength=330, foreground="#57606a")
        self.bind_hint.pack(fill="x")
        row = ttk.Frame(bind)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Найти окно по заголовку", command=self.find).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Отвязать окно", command=self.unbind).pack(side="left")

    def selected(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def reload(self, select: Optional[str] = None):
        current = select or self.selected()
        self.tree.delete(*self.tree.get_children())
        for name in self.w.c.profile_names():
            self.tree.insert("", "end", iid=name, values=(name, "", ""))
        self.refresh()
        if current and self.tree.exists(current):
            self.tree.selection_set(current)
            self.tree.see(current)
        elif not current:
            self.w.on_profile_selected(None)

    def refresh(self):
        self.bind_hint.configure(text=f"Привязать окно: выберите профиль, наведите мышь на окно игры и нажмите "
                                      f"{self.w.c.settings.hotkey_bind_window}")
        for name in self.tree.get_children():
            window = self.w.c.bound_window(name)
            state = "—"
            if window is not None:
                profile = self.w.c.profile(name)
                states = [self.w.c.status(name, a.id).state for a in profile.actions if a.enabled]
                state = (f"▶ {states.count(ActionState.RUNNING)}  ⏸ {states.count(ActionState.PAUSED)}"
                         if self.w.c.running else f"готов ({len(states)})")
            self.tree.item(name, values=(name, window.title if window is not None else "не выбрано", state))

    def new(self):
        name = simpledialog.askstring("Новый профиль", "Название профиля:", parent=self)
        if name:
            self.w.guard(lambda: self.w.c.create_profile(name))
            self.reload(select=name.strip())

    def rename(self):
        old = self.selected()
        if not old:
            return
        new = simpledialog.askstring("Переименовать", "Новое название:", initialvalue=old, parent=self)
        if new and new != old:
            if self.w.guard(lambda: self.w.c.rename_profile(old, new)):
                self.reload(select=new.strip())

    def delete(self):
        name = self.selected()
        if name and messagebox.askyesno("Удалить профиль", f"Удалить профиль «{name}» и все его действия?",
                                        parent=self):
            self.w.guard(lambda: self.w.c.delete_profile(name))
            self.reload()

    def find(self):
        name = self.selected()
        if name and self.w.guard(lambda: self.w.c.find_window_by_title(name)):
            self.refresh()

    def unbind(self):
        name = self.selected()
        if name:
            self.w.c.unbind_window(name)
            self.refresh()


class ActionsTab(ttk.Frame):
    """Actions of the selected profile for one device ("mouse" or "keyboard")."""

    def __init__(self, parent, window: "MainWindow", device: str):
        super().__init__(parent, padding=6)
        self.w, self.device = window, device
        self.target_type = MouseTarget if device == "mouse" else KeyTarget
        columns = [("on", "Вкл", 40), ("name", "Название", 130)]
        columns += ([("point", "Точка", 80), ("button", "Кнопка", 70)] if device == "mouse"
                    else [("key", "Клавиша", 80)])
        columns += [("method", "Способ ввода", 170), ("interval", "Интервал", 80), ("status", "Статус", 200)]
        self.hint = ttk.Label(self, foreground="#57606a", wraplength=700)
        self.hint.pack(fill="x", pady=(0, 6))
        self.tree = _tree(self, columns)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(6, 0))
        commands = [("Изменить", self.edit), ("Удалить", self.remove), ("Вкл/Выкл", self.toggle),
                    ("Тест (1 раз)", self.test)]
        if device == "mouse":
            commands.insert(3, ("Обновить отпечаток", self.refresh_fingerprint))
        else:
            commands.insert(0, ("Добавить", self.add))
        for text, command in commands:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 4))

    def actions(self) -> list[Action]:
        name = self.w.profile_name
        if not name:
            return []
        return [a for a in self.w.c.profile(name).actions if isinstance(a.target, self.target_type)]

    def selected(self) -> Optional[Action]:
        selection = self.tree.selection()
        return next((a for a in self.actions() if a.id == selection[0]), None) if selection else None

    def reload(self, select: Optional[str] = None):
        current = select or (self.tree.selection() or [None])[0]
        self.tree.delete(*self.tree.get_children())
        for action in self.actions():
            self.tree.insert("", "end", iid=action.id, values=self._row(action))
        if current and self.tree.exists(current):
            self.tree.selection_set(current)
            self.tree.see(current)
        self._update_hint()

    def _update_hint(self):
        s = self.w.c.settings
        if not self.w.profile_name:
            text = "Создайте или выберите профиль слева."
        elif self.device == "mouse":
            text = (f"Добавить клик: наведите мышь на ячейку с игровым макросом и нажмите {s.hotkey_capture}. "
                    f"Профиль сам привяжется к этому окну. По умолчанию — фоновый PostMessage (работает в LU4).")
        else:
            text = ("Нажатия клавиш. В LU4 программные нажатия не доходят до игровых действий "
                    "(см. вкладку «Способы ввода»), но в других программах могут работать.")
        self.hint.configure(text=text)

    def _row(self, action: Action) -> tuple:
        target = action.target
        method = self.w.c.methods.get(target.method_id)
        method_name = method.info.name if method else f"? {target.method_id}"
        status = status_text(self.w.c.status(self.w.profile_name, action.id), action.enabled)
        head = ("✔" if action.enabled else "", action.name)
        if isinstance(target, MouseTarget):
            middle = (f"{target.point.x}, {target.point.y}",
                      BUTTONS[target.button] + (" ×2" if target.double else ""))
        else:
            middle = (target.key.name,)
        return head + middle + (method_name, schedule_text(action.schedule), status)

    def refresh(self):
        ids = [a.id for a in self.actions()]
        if ids != list(self.tree.get_children()):
            self.reload()
            return
        for action in self.actions():
            self.tree.item(action.id, values=self._row(action))

    def _save(self):
        self.w.guard(lambda: self.w.c.save_profile(self.w.profile_name))
        self.reload()

    def edit(self):
        action = self.selected()
        if action is None:
            return
        dialog = ActionDialog(self, action, self.w.c.methods_for(self.device), "Действие")
        self.wait_window(dialog)
        if dialog.ok:
            self._save()

    def add(self):
        name = self.w.profile_name
        if not name:
            return
        s = self.w.c.settings
        draft = Action(id="", name="Клавиша", schedule=Schedule(s.default_interval, s.default_jitter),
                       target=KeyTarget(key_by_name("F1"), s.default_key_method))
        dialog = ActionDialog(self, draft, self.w.c.methods_for("keyboard"), "Новое нажатие клавиши")
        self.wait_window(dialog)
        if not dialog.ok:
            return
        action = self.w.c.add_key_action(name, draft.target.key, draft.target.method_id)
        action.name, action.schedule, action.enabled = draft.name, draft.schedule, draft.enabled
        self._save()
        self.reload(select=action.id)

    def remove(self):
        action = self.selected()
        if action and messagebox.askyesno("Удалить", f"Удалить «{action.name}»?", parent=self):
            self.w.c.remove_action(self.w.profile_name, action.id)
            self.reload()

    def toggle(self):
        action = self.selected()
        if action:
            action.enabled = not action.enabled
            self._save()

    def refresh_fingerprint(self):
        action = self.selected()
        if action and self.w.guard(lambda: self.w.c.refresh_fingerprint(self.w.profile_name, action.id)):
            self.w.show("Отпечаток ячейки обновлён.")

    def test(self):
        action = self.selected()
        if action and self.w.guard(lambda: self.w.c.test_action(self.w.profile_name, action.id)):
            self.w.show(f"«{action.name}» отправлено один раз — проверьте результат в игре.")


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
        self.tree = _tree(self, [("device", "Устройство", 85), ("method", "Способ ввода", 220),
                                 ("mode", "Режим", 95), ("available", "Доступен", 150),
                                 ("status", "Статус", 120), ("note", "Комментарий", 330), ("source", "Источник", 95)])
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

    def comment(self):
        method_id = self._selected()
        if not method_id:
            return
        entry = self.w.c.compatibility.entry(self.app.get(), method_id)
        note = simpledialog.askstring("Комментарий", "Комментарий:", initialvalue=entry.note, parent=self)
        if note is not None:
            self.w.c.compatibility.mark(self.app.get(), method_id, entry.status, note)
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


class SettingsTab(ttk.Frame):
    FIELDS = [
        ("hotkey_toggle", "Старт/Стоп", str),
        ("hotkey_capture", "Добавить клик под курсором", str),
        ("hotkey_bind_window", "Привязать профиль к окну под курсором", str),
        ("default_interval", "Интервал по умолчанию, сек", float),
        ("default_jitter", "Разброс по умолчанию ±, сек", float),
        ("fingerprint_size", "Размер отпечатка ячейки, пикс.", int),
        ("fingerprint_tolerance", "Допуск цвета отпечатка (0–255)", int),
        ("fingerprint_min_similarity", "Мин. совпадение отпечатка (0–1)", float),
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


class MainWindow:
    def __init__(self, root: tk.Tk, controller, on_toggle: Callable, on_settings_saved: Callable):
        self.root, self.c = root, controller
        self.profile_name: Optional[str] = None
        root.title("MyClicker")
        root.geometry("1180x640")
        root.minsize(900, 500)

        body = ttk.PanedWindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self.profiles = ProfilesPanel(body, self)
        body.add(self.profiles, weight=1)
        self.tabs = ttk.Notebook(body)
        body.add(self.tabs, weight=3)
        self.mouse_tab = ActionsTab(self.tabs, self, "mouse")
        self.keyboard_tab = ActionsTab(self.tabs, self, "keyboard")
        self.compat_tab = CompatibilityTab(self.tabs, self)
        self.settings_tab = SettingsTab(self.tabs, self, on_settings_saved)
        self.tabs.add(self.mouse_tab, text="Мышь")
        self.tabs.add(self.keyboard_tab, text="Клавиатура")
        self.tabs.add(self.compat_tab, text="Способы ввода")
        self.tabs.add(self.settings_tab, text="Настройки")
        if not self.c.profile_names():
            self.tabs.select(self.compat_tab)

        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        self.toggle_button = ttk.Button(bar, text="", command=on_toggle, width=26)
        self.toggle_button.pack(side="left")
        self.message = ttk.Label(bar, text="")
        self.message.pack(side="left", padx=12)

        self.profiles.reload()
        names = self.c.profile_names()
        if names:
            self.profiles.tree.selection_set(names[0])

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
