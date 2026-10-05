"""Left column of the main window: Profiles and the windows they are bound to."""
from __future__ import annotations

from tkinter import messagebox, simpledialog, ttk
from typing import Optional, TYPE_CHECKING

from myclicker.ui.rich_text import RichLabel
from myclicker.ui.widgets import tree_table

if TYPE_CHECKING:
    from myclicker.ui.main_window import MainWindow


class ProfilesPanel(ttk.LabelFrame):
    def __init__(self, parent, window: "MainWindow"):
        super().__init__(parent, text="Профили", padding=6)
        self.w = window
        self.tree = tree_table(self, [("name", "Профиль", 120), ("window", "Окно", 150), ("state", "Статус", 90)], 14)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.w.on_profile_selected(self.selected()))
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(6, 0))
        for text, command in (("Новый", self.new), ("Переименовать", self.rename), ("Удалить", self.delete)):
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 4))
        bind = ttk.Frame(self)
        bind.pack(fill="x", pady=(6, 0))
        self.bind_hint = RichLabel(bind, lines=3)
        self.bind_hint.configure(width=40)
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
        self.bind_hint.set(f"Привязать окно: выберите профиль, наведите мышь на окно игры и нажмите "
                           f"`{self.w.c.settings.hotkey_bind_window}`")
        for name in self.tree.get_children():
            window = self.w.c.bound_window(name)
            state = "—"
            if window is not None:
                summary = self.w.c.summary(name)
                state = f"▶ {summary.active}  ⏸ {summary.paused}" if summary.running else f"готов ({summary.actions})"
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
