"""Sound library, Soundpad .spl import/export and metadata helpers."""

from __future__ import annotations

import json
import mimetypes
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover - metadata is best effort
    MutagenFile = None

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".mp4", ".opus", ".wma", ".aiff", ".aif",
}

AUDIO_FILTER = (
    "Audio files (*.mp3 *.wav *.ogg *.flac *.aac *.m4a *.mp4 *.opus *.wma *.aiff *.aif);;"
    "All files (*.*)"
)


def audio_duration(path: Path) -> float:
    if MutagenFile is None:
        return 0.0
    try:
        media = MutagenFile(str(path))
        if media is not None and getattr(media, "info", None) is not None:
            return float(media.info.length)
    except Exception:
        pass
    return 0.0


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _key_to_hotkey(key: int, modifiers: int) -> str:
    mods: list[str] = []
    if modifiers & 2:
        mods.append("ctrl")
    if modifiers & 1:
        mods.append("alt")
    if modifiers & 4:
        mods.append("shift")
    if modifiers & 8:
        mods.append("windows")
    if 48 <= key <= 57:
        base = chr(key)
    elif 65 <= key <= 90:
        base = chr(key).lower()
    elif 112 <= key <= 123:
        base = f"f{key - 111}"
    elif 96 <= key <= 105:
        base = f"num {key - 96}"
    elif key == 32:
        base = "space"
    elif key == 13:
        base = "enter"
    elif key == 27:
        base = "esc"
    elif key == 9:
        base = "tab"
    else:
        base = ""
    if not base:
        return ""
    return "+".join(mods + [base])


@dataclass
class Sound:
    path: str
    title: str
    duration: float = 0.0
    hotkey: str = ""
    category: str = "All Sounds"
    artist: str = ""
    added: str = field(default_factory=lambda: date.today().isoformat())
    gain: float = 1.0
    auto_keys: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def exists(self) -> bool:
        return Path(self.path).exists()

    def as_dict(self) -> dict:
        data = asdict(self)
        data["duration"] = round(float(self.duration), 3)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Sound":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_path(cls, path: Path, category: str = "All Sounds") -> "Sound":
        path = Path(path)
        return cls(
            path=str(path),
            title=path.stem,
            duration=audio_duration(path),
            category=category,
        )


class Library:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.sounds: list[Sound] = []
        self.categories: list[str] = ["All Sounds"]
        self.dirty = False

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.sounds = []
        for row in raw.get("sounds", []):
            try:
                self.sounds.append(Sound.from_dict(row))
            except Exception:
                continue
        cats = [str(c) for c in raw.get("categories", []) if str(c).strip()]
        self.categories = ["All Sounds"] + [c for c in cats if c != "All Sounds"]
        for sound in self.sounds:
            if sound.category not in self.categories:
                self.categories.append(sound.category)
        self.dirty = False

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "sounds": [s.as_dict() for s in self.sounds],
            "categories": [c for c in self.categories if c != "All Sounds"],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self.dirty = False

    def add(self, sound: Sound) -> Sound:
        self.sounds.append(sound)
        if sound.category not in self.categories:
            self.categories.append(sound.category)
        self.dirty = True
        return sound

    def add_path(self, path: Path, category: str = "All Sounds") -> Sound | None:
        resolved = str(Path(path).resolve())
        for existing in self.sounds:
            try:
                if str(Path(existing.path).resolve()).lower() == resolved.lower():
                    return None
            except Exception:
                continue
        sound = Sound.from_path(Path(path), category=category)
        return self.add(sound)

    def remove(self, sound: Sound) -> None:
        self.sounds = [s for s in self.sounds if s.id != sound.id]
        self.dirty = True

    def by_id(self, sound_id: str) -> Sound | None:
        return next((s for s in self.sounds if s.id == sound_id), None)

    def find_hotkey(self, hotkey: str) -> Sound | None:
        needle = hotkey.strip().lower()
        if not needle:
            return None
        return next((s for s in self.sounds if s.hotkey.strip().lower() == needle), None)

    def category_sounds(self, category: str) -> list[Sound]:
        if category == "All Sounds":
            return list(self.sounds)
        return [s for s in self.sounds if s.category == category]

    def add_category(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.categories:
            return False
        self.categories.append(name)
        self.dirty = True
        return True

    def remove_category(self, name: str) -> None:
        if name in ("All Sounds", ""):
            return
        self.categories = [c for c in self.categories if c != name]
        for sound in self.sounds:
            if sound.category == name:
                sound.category = "All Sounds"
        self.dirty = True

    def import_spl(self, path: Path) -> int:
        """Import a Soundpad sound list. Returns number of added sounds."""
        root = ET.parse(path).getroot()
        if root.tag.lower() != "soundlist":
            raise ValueError("Not a Soundpad sound list")
        category_for_index: dict[int, str] = {}
        categories_node = root.find("Categories")
        if categories_node is not None:
            for category in categories_node.findall("Category"):
                name = (category.get("name") or "").strip()
                if not name:
                    continue
                self.add_category(name)
                for ref in category.findall("Sound"):
                    try:
                        category_for_index[int(ref.get("id", "-1"))] = name
                    except ValueError:
                        continue
        added = 0
        for index, node in enumerate(root.findall("Sound")):
            raw_path = node.get("url") or ""
            if not raw_path:
                continue
            source = Path(raw_path)
            if not source.exists():
                continue
            key = node.get("key")
            hotkey = ""
            if key is not None:
                try:
                    hotkey = _key_to_hotkey(int(key), int(node.get("keyModifiers", "0") or 0))
                except ValueError:
                    hotkey = ""
            category = category_for_index.get(index, "All Sounds")
            sound = self.add_path(source, category=category)
            if sound is None:
                continue
            sound.title = node.get("title") or source.stem
            sound.artist = node.get("artist") or ""
            duration = node.get("duration") or ""
            if ":" in duration:
                try:
                    minutes, seconds = duration.split(":", 1)
                    sound.duration = int(minutes) * 60 + float(seconds)
                except ValueError:
                    pass
            if not sound.duration:
                sound.duration = audio_duration(source)
            sound.hotkey = hotkey
            if node.get("addedOn"):
                sound.added = node.get("addedOn") or sound.added
            added += 1
        self.dirty = True
        return added

    def export_spl(self, path: Path) -> None:
        root = ET.Element("Soundlist")
        for index, sound in enumerate(self.sounds):
            node = ET.SubElement(root, "Sound")
            node.set("hash", sound.id)
            node.set("url", sound.path)
            node.set("artist", sound.artist)
            node.set("title", sound.title)
            node.set("duration", fmt_duration(sound.duration))
            key, modifiers = _hotkey_parts(sound.hotkey)
            node.set("keyModifiers", str(modifiers))
            node.set("key", str(key))
            node.set("addedOn", sound.added)
        categories = ET.SubElement(root, "Categories")
        ET.SubElement(categories, "Category", type="1", icon="stock_icon_cat_list", hidden="true")
        groups: dict[str, list[int]] = {}
        for index, sound in enumerate(self.sounds):
            groups.setdefault(sound.category or "All Sounds", []).append(index)
        for name, indices in groups.items():
            if name == "All Sounds":
                continue
            cat = ET.SubElement(categories, "Category", name=name, icon="stock_icon_cat_home")
            for index in indices:
                ET.SubElement(cat, "Sound", id=str(index))
        ET.SubElement(root, "Hotbar")
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="UTF-8", xml_declaration=True)


def _hotkey_parts(hotkey: str) -> tuple[int, int]:
    if not hotkey:
        return 0, 0
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return 0, 0
    modifiers = 0
    for part in parts[:-1]:
        if part == "alt":
            modifiers |= 1
        elif part == "ctrl":
            modifiers |= 2
        elif part == "shift":
            modifiers |= 4
        elif part in ("windows", "win", "meta"):
            modifiers |= 8
    base = parts[-1]
    if len(base) == 1 and base.isalnum():
        key = ord(base.upper())
    elif base.startswith("f") and base[1:].isdigit():
        key = 111 + int(base[1:])
    elif base.startswith("num ") and base[4:].isdigit():
        key = 96 + int(base[4:])
    elif base == "space":
        key = 32
    elif base == "enter":
        key = 13
    elif base == "esc":
        key = 27
    elif base == "tab":
        key = 9
    else:
        key = 0
    return key, modifiers
