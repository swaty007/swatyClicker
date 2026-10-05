"""Sections «Мышь» and «Клавиатура»: the Actions of the selected Profile."""
from __future__ import annotations

import base64
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, TYPE_CHECKING

from myclicker.domain.keys import key_by_name
from myclicker.domain.model import Action, KeyTarget, MouseTarget, Schedule
from myclicker.persistence import png
from myclicker.ui.dialogs import ActionDialog
from myclicker.ui.rich_text import RichLabel
from myclicker.ui.texts import BUTTONS, schedule_text, status_text
from myclicker.ui.widgets import tree_table

if TYPE_CHECKING:
    from myclicker.ui.main_window import MainWindow


PREVIEW_ZOOM = 3   # Slot Fingerprint preview under the mouse table
LARGE_ZOOM = 12    # the same picture opened in its own window


class ActionsTab(ttk.Frame):
    """Actions of the selected profile for one device ("mouse" or "keyboard")."""

    def __init__(self, parent, window: "MainWindow", device: str):
        super().__init__(parent, padding=6)
        self.w, self.device = window, device
        self.target_type = MouseTarget if device == "mouse" else KeyTarget
        columns = [("on", "Вкл", 40), ("name", "Название", 130)]
        columns += ([("point", "Точка", 80), ("button", "Кнопка", 70), ("hover", "Наведение", 75),
                     ("hold", "Удержание", 75)] if device == "mouse"
                    else [("key", "Клавиша", 80)])
        columns += [("method", "Способ ввода", 170), ("interval", "Интервал", 80), ("status", "Статус", 200)]
        self.hint = RichLabel(self, lines=3)
        self.hint.pack(fill="x", pady=(0, 6))
        # The bottom bar is packed before the table so a tall table can never push the buttons out of view.
        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(6, 0))
        self._thumbs: dict[str, tuple[int, tk.PhotoImage]] = {}   # action id -> (fingerprint id, picture)
        self.preview = None
        if device == "mouse":
            self.preview = tk.Label(bottom, text="нет\nотпечатка", width=10, height=3,
                                    relief="solid", borderwidth=1, cursor="hand2", font=("Segoe UI", 8),
                                    foreground="#57606a", background="#f6f8fa")
            self.preview.pack(side="left", padx=(0, 10))
            self.preview.bind("<Button-1>", lambda e: self.open_fingerprint())
        self.tree = tree_table(self, columns)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_preview())
        buttons = ttk.Frame(bottom)
        buttons.pack(side="left", fill="x", anchor="center")
        if device == "mouse":
            ttk.Label(bottom, text="◀ отпечаток: клик — увеличить", foreground="#57606a").pack(
                side="left", padx=(8, 0))
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
        self._update_preview()

    def _update_hint(self):
        s = self.w.c.settings
        if not self.w.profile_name:
            text = "Создайте или выберите профиль слева."
        elif self.device == "mouse":
            text = (f"Добавить клик: наведите мышь на ячейку с игровым макросом и нажмите `{s.hotkey_capture}`. "
                    f"Профиль сам привяжется к этому окну. Старт/Стоп — `{s.hotkey_toggle}`. "
                    f"По умолчанию — фоновый `PostMessage`. В LU4 игровые действия проходят только при живом "
                    f"вводе игрока — см. «Способы ввода».")
        else:
            text = (f"Нажатия клавиш: «Добавить» внизу. Старт/Стоп — `{s.hotkey_toggle}`. В LU4 программные "
                    f"нажатия не доходят до игровых действий (см. «Способы ввода»), но в других программах "
                    f"могут работать.")
        self.hint.set(text)

    def _row(self, action: Action) -> tuple:
        target = action.target
        method = self.w.c.methods.get(target.method_id)
        method_name = method.info.name if method else f"? {target.method_id}"
        status = status_text(self.w.c.status(self.w.profile_name, action.id), action.enabled)
        head = ("✔" if action.enabled else "", action.name)
        if isinstance(target, MouseTarget):
            middle = (f"{target.point.x}, {target.point.y}",
                      BUTTONS[target.button] + (" ×2" if target.double else ""),
                      f"{target.timing.hover:g} с", f"{target.timing.hold:g} с")
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
        self._update_preview()

    def _picture(self, action: Optional[Action], zoom: int):
        """The action's Slot Fingerprint as a Tk picture enlarged `zoom` times, or None."""
        if action is None or not isinstance(action.target, MouseTarget) or action.target.fingerprint is None:
            return None
        image = action.target.fingerprint.image
        key = f"{action.id}@{zoom}"
        cached = self._thumbs.get(key)
        if cached is None or cached[0] != id(image):
            picture = tk.PhotoImage(data=base64.b64encode(png.encode(image))).zoom(zoom)
            cached = (id(image), picture)
            self._thumbs[key] = cached
        return cached[1]

    def _update_preview(self):
        if self.preview is None:
            return
        picture = self._picture(self.selected(), PREVIEW_ZOOM)
        if picture is None:
            self.preview.configure(image="", text="нет\nотпечатка", width=10, height=3)
        else:
            self.preview.configure(image=picture, text="", width=picture.width(), height=picture.height())

    def open_fingerprint(self):
        """Show the selected action's Slot Fingerprint big, in its own window."""
        action = self.selected()
        picture = self._picture(action, LARGE_ZOOM)
        if picture is None:
            return
        window = tk.Toplevel(self)
        window.title(f"Отпечаток — {action.name}")
        window.transient(self.winfo_toplevel())
        window.resizable(False, False)
        big = tk.Label(window, image=picture, borderwidth=0, cursor="hand2")
        big.pack(padx=12, pady=(12, 6))
        big.bind("<Button-1>", lambda e: window.destroy())
        image = action.target.fingerprint.image
        ttk.Label(window, text=f"Точка клика {action.target.point.x}, {action.target.point.y} — в центре · "
                               f"снимок {image.width}×{image.height} пикс., увеличен в {LARGE_ZOOM} раз",
                  foreground="#57606a").pack(padx=12)
        ttk.Button(window, text="Закрыть", command=window.destroy).pack(pady=(6, 12))
        window.bind("<Escape>", lambda e: window.destroy())

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
