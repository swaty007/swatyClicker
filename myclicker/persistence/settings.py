"""Application settings, stored in data/settings.json. Unknown or broken values fall back to defaults."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Settings:
    hotkey_toggle: str = "Ctrl+Alt+S"        # start/stop everything
    hotkey_capture: str = "Ctrl+Alt+C"       # add a mouse Action at the point under the cursor
    hotkey_bind_window: str = "Ctrl+Alt+A"   # bind the selected Profile to the window under the cursor
    default_mouse_method: str = "mouse.postmessage"
    default_key_method: str = "key.sendinput_scan"
    default_interval: float = 5.0
    default_jitter: float = 0.5
    default_hover_delay: float = 0.1         # pause after moving onto the point, before pressing
    default_hold: float = 0.06               # how long the mouse button stays down
    fingerprint_size: int = 20
    fingerprint_tolerance: int = 24
    fingerprint_min_similarity: float = 0.85
    fingerprint_search_radius: int = 150     # how far to look for a slot that moved, in pixels
    mini_panel_x: int = 8
    mini_panel_y: int = 8
    compatibility_app: str = "LU4"
    last_profiles: list = None               # profiles open in the previous session

    def __post_init__(self):
        if self.last_profiles is None:
            self.last_profiles = []


class SettingsStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Settings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Settings()
        defaults = Settings()
        values = {}
        for f in fields(Settings):
            value = data.get(f.name, getattr(defaults, f.name))
            default = getattr(defaults, f.name)
            if default is not None and not isinstance(value, type(default)):
                try:
                    value = type(default)(value)
                except (TypeError, ValueError):
                    value = default
            values[f.name] = value
        return Settings(**values)

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
