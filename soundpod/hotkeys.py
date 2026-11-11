"""Global hotkeys through the Windows RegisterHotKey API.

RegisterHotKey is more reliable than a low-level keyboard hook and does not
swallow the key, so games and voice chat still receive it.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "windows": MOD_WIN,
    "win": MOD_WIN,
    "meta": MOD_WIN,
}

_VK = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "page up": 0x21,
    "pgup": 0x21,
    "page down": 0x22,
    "pgdown": 0x22,
    "pgdn": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "pause": 0x13,
    "print screen": 0x2C,
    "caps lock": 0x14,
    "num 0": 0x60,
    "num 1": 0x61,
    "num 2": 0x62,
    "num 3": 0x63,
    "num 4": 0x64,
    "num 5": 0x65,
    "num 6": 0x66,
    "num 7": 0x67,
    "num 8": 0x68,
    "num 9": 0x69,
    "num *": 0x6A,
    "num +": 0x6B,
    "num -": 0x6D,
    "num .": 0x6E,
    "num /": 0x6F,
}

_QT_REPLACEMENTS = {
    "meta": "windows",
    "win": "windows",
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "ins": "insert",
    "pgup": "page up",
    "pgdown": "page down",
    "pgdn": "page down",
    "space": "space",
    "backspace": "backspace",
    "tab": "tab",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "pause": "pause",
    "print": "print screen",
}


def qt_to_hotkey(sequence: str) -> str:
    parts = [p.strip() for p in sequence.split("+") if p.strip()]
    out: list[str] = []
    for part in parts:
        low = part.lower()
        if low.startswith("num+") and low[4:].isdigit():
            out.append("num " + low[4:])
        else:
            out.append(_QT_REPLACEMENTS.get(low, low))
    return "+".join(out)


def hotkey_to_qt(hotkey: str) -> str:
    parts = [p.strip() for p in hotkey.split("+") if p.strip()]
    out = []
    for part in parts:
        low = part.lower()
        if low == "windows":
            out.append("Meta")
        elif low == "ctrl":
            out.append("Ctrl")
        elif low == "alt":
            out.append("Alt")
        elif low == "shift":
            out.append("Shift")
        elif low.startswith("num "):
            out.append("Num+" + low[4:])
        elif low == "space":
            out.append("Space")
        elif low in ("enter", "esc", "tab", "backspace", "home", "end"):
            out.append(low.capitalize())
        elif low == "delete":
            out.append("Del")
        elif low == "insert":
            out.append("Ins")
        elif low == "page up":
            out.append("PgUp")
        elif low == "page down":
            out.append("PgDown")
        elif len(low) == 1:
            out.append(low.upper())
        else:
            out.append(low.capitalize())
    return "+".join(out)


def parse_hotkey(hotkey: str) -> tuple[int, int] | None:
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for part in parts[:-1]:
        if part not in _MODS:
            return None
        mods |= _MODS[part]
    key = parts[-1]
    if key in _VK:
        vk = _VK[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        return None
    return mods | MOD_NOREPEAT, vk


class _NativeFilter(QAbstractNativeEventFilter):
    def __init__(self, manager: "HotkeyManager"):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        try:
            et = bytes(event_type)
        except Exception:
            et = b""
        if et in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
            except Exception:
                return False, 0
            if msg.message == WM_HOTKEY:
                callback = self.manager.callbacks.get(int(msg.wParam))
                if callback is not None:
                    callback()
        return False, 0


class HotkeyManager:
    def __init__(self, callback: Callable[[str], None], app=None):
        self.callback = callback
        self.callbacks: dict[int, Callable[[], None]] = {}
        self._bindings: dict[str, int] = {}
        self._next_id = 1
        self.errors: list[str] = []
        self.app = app
        self._filter = _NativeFilter(self)
        self._installed = False
        if app is not None:
            app.installNativeEventFilter(self._filter)
            self._installed = True

    @property
    def available(self) -> bool:
        return self._installed

    def _register(self, hotkey: str, callback: Callable[[], None]) -> int | None:
        parsed = parse_hotkey(hotkey)
        if parsed is None:
            self.errors.append(f"{hotkey}: unsupported key combination")
            return None
        mods, vk = parsed
        hotkey_id = self._next_id
        self._next_id += 1
        if self._next_id > 0xBFFF:
            self._next_id = 1
        if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, mods, vk):
            error = ctypes.get_last_error()
            self.errors.append(f"{hotkey}: RegisterHotKey failed (error {error})")
            return None
        self.callbacks[hotkey_id] = callback
        return hotkey_id

    def _unregister_all(self) -> None:
        for hotkey_id in list(self.callbacks):
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
            except Exception:
                pass
        self.callbacks.clear()
        self._bindings.clear()

    def clear(self) -> None:
        self._unregister_all()

    def rebind(self, entries: list[tuple[str, str]]) -> list[str]:
        self._unregister_all()
        self.errors = []
        seen: set[str] = set()
        for sound_id, hotkey in entries:
            combo = hotkey.strip().lower()
            if not combo or combo in seen:
                continue
            seen.add(combo)
            hotkey_id = self._register(combo, lambda sid=sound_id: self.callback(sid))
            if hotkey_id is not None:
                self._bindings[sound_id] = hotkey_id
        return list(self.errors)
