"""ProfileStore: one JSON file per Profile plus a folder with its Slot Fingerprints (PNG).

    profiles/<file-stem>.json
    profiles/<file-stem>/<action-id>.png

The file stem is derived from the user-given name, which is stored inside the JSON, so any
name (spaces, slashes, Cyrillic) is allowed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from myclicker.domain.model import (Action, Fingerprint, Key, KeyTarget, MouseButton, MouseTarget, Point, Profile,
                                    Schedule)
from myclicker.persistence import png

FORMAT_VERSION = 1


def _stem(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")[:40] or "profile"
    return f"{slug}-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]}"


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class ProfileStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    # ----- queries -----
    def list_names(self) -> list[str]:
        if not self.root.exists():
            return []
        names = []
        for path in self.root.glob("*.json"):
            try:
                names.append(json.loads(path.read_text(encoding="utf-8"))["name"])
            except (OSError, ValueError, KeyError):
                continue
        return names

    def exists(self, name: str) -> bool:
        return self._json_path(name).exists()

    def load(self, name: str) -> Profile:
        data = json.loads(self._json_path(name).read_text(encoding="utf-8"))
        folder = self._fingerprint_dir(name)
        return Profile(
            name=data["name"],
            window_title=data.get("window_title", ""),
            actions=[self._action_from_json(a, folder) for a in data.get("actions", [])],
        )

    # ----- commands -----
    def save(self, profile: Profile) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        folder = self._fingerprint_dir(profile.name)
        keep = set()
        for action in profile.actions:
            target = action.target
            if isinstance(target, MouseTarget) and target.fingerprint is not None:
                folder.mkdir(exist_ok=True)
                image_path = folder / f"{action.id}.png"
                _write_atomic(image_path, png.encode(target.fingerprint.image))
                keep.add(image_path.name)
        if folder.exists():
            for stale in folder.glob("*.png"):
                if stale.name not in keep:
                    stale.unlink()
            if not any(folder.iterdir()):
                folder.rmdir()
        data = {
            "format": FORMAT_VERSION,
            "name": profile.name,
            "window_title": profile.window_title,
            "actions": [self._action_to_json(a) for a in profile.actions],
        }
        _write_atomic(self._json_path(profile.name),
                      json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def delete(self, name: str) -> None:
        self._json_path(name).unlink(missing_ok=True)
        shutil.rmtree(self._fingerprint_dir(name), ignore_errors=True)

    def rename(self, old: str, new: str) -> None:
        if self.exists(new):
            raise FileExistsError(f"профиль «{new}» уже существует")
        profile = self.load(old)
        profile.name = new
        self.save(profile)
        self.delete(old)

    # ----- mapping -----
    def _json_path(self, name: str) -> Path:
        return self.root / f"{_stem(name)}.json"

    def _fingerprint_dir(self, name: str) -> Path:
        return self.root / _stem(name)

    @staticmethod
    def _action_to_json(action: Action) -> dict:
        data = {
            "id": action.id,
            "name": action.name,
            "enabled": action.enabled,
            "interval": action.schedule.interval,
            "jitter": action.schedule.jitter,
        }
        target = action.target
        if isinstance(target, MouseTarget):
            data["mouse"] = {
                "x": target.point.x, "y": target.point.y,
                "method": target.method_id,
                "button": target.button.value,
                "double": target.double,
                "fingerprint_check": target.fingerprint.check if target.fingerprint else False,
                "has_fingerprint": target.fingerprint is not None,
            }
        else:
            data["key"] = {"vk": target.key.vk, "name": target.key.name, "method": target.method_id}
        return data

    @staticmethod
    def _action_from_json(data: dict, folder: Path) -> Action:
        schedule = Schedule(float(data["interval"]), float(data.get("jitter", 0.0)))
        if "mouse" in data:
            m = data["mouse"]
            fingerprint = None
            image_path = folder / f"{data['id']}.png"
            if m.get("has_fingerprint") and image_path.exists():
                fingerprint = Fingerprint(png.decode(image_path.read_bytes()), check=m.get("fingerprint_check", True))
            target = MouseTarget(point=Point(int(m["x"]), int(m["y"])), method_id=m["method"],
                                 button=MouseButton(m.get("button", "left")), double=bool(m.get("double", False)),
                                 fingerprint=fingerprint)
        else:
            k = data["key"]
            target = KeyTarget(key=Key(int(k["vk"]), k["name"]), method_id=k["method"])
        return Action(id=data["id"], name=data["name"], schedule=schedule, target=target,
                      enabled=bool(data.get("enabled", True)))
