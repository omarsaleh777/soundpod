"""Auto Keys: send keystrokes together with a sound.

Soundpad's Auto Keys sends key presses around playback, for example holding the
push-to-talk key so a game transmits the sound. Syntax:

    "~ctrl"      hold ctrl until the sound ends
    "f"          tap f once when the sound starts
    "~shift, c"  hold shift, tap c

Keys use Windows virtual-key names: a-z, 0-9, f1-f24, space, enter, tab, esc,
shift, ctrl, alt, up, down, left, right, home, end, insert, delete, page up,
page down.
"""

from __future__ import annotations

import ctypes
import threading
import time

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
INPUT_KEYBOARD = 1

_VK = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "caps lock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "page up": 0x21,
    "pgup": 0x21,
    "page down": 0x22,
    "pgdown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "print screen": 0x2C,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
}

_EXTENDED = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x2C,
}


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_short),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUTUNION)]


def parse_keys(spec: str) -> tuple[list[int], list[int]]:
    """Return (held, tapped) virtual-key codes."""
    holds: list[int] = []
    taps: list[int] = []
    for raw in spec.replace(";", ",").replace("\n", ",").split(","):
        token = raw.strip().lower()
        if not token:
            continue
        hold = token.startswith("~")
        if hold:
            token = token[1:].strip()
        combo = [part.strip() for part in token.split("+") if part.strip()]
        codes: list[int] = []
        for part in combo:
            vk = _vk_for(part)
            if vk is None:
                continue
            codes.append(vk)
        if not codes:
            continue
        if hold:
            holds.extend(codes)
        else:
            taps.extend(codes)
    return holds, taps


def _vk_for(name: str) -> int | None:
    if name in _VK:
        return _VK[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x70 + int(name[1:]) - 1
    if name.startswith("num ") and name[4:].isdigit():
        return 0x60 + int(name[4:])
    return None


def _send(vk: int, keyup: bool) -> None:
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_SCANCODE
    if keyup:
        flags |= KEYEVENTF_KEYUP
    if vk in _EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    item = _INPUT(
        type=INPUT_KEYBOARD,
        union=_INPUTUNION(
            ki=_KEYBDINPUT(
                wVk=0,
                wScan=scan,
                dwFlags=flags,
                time=0,
                dwExtraInfo=ctypes.POINTER(ctypes.c_ulong)(),
            )
        ),
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(_INPUT))


class AutoKeys:
    """Sends the configured keys for one playback."""

    def __init__(self):
        self._held: list[int] = []
        self._lock = threading.Lock()

    def engage(self, spec: str, duration: float) -> bool:
        """Press holds and taps. Holds are released after `duration` seconds."""
        holds, taps = parse_keys(spec)
        if not holds and not taps:
            return False
        for vk in holds:
            _send(vk, False)
        for vk in taps:
            _send(vk, False)
            time.sleep(0.03)
            _send(vk, True)
        if holds:
            with self._lock:
                self._held.extend(holds)
            timer = threading.Timer(max(0.2, duration), self._release, args=(holds,))
            timer.daemon = True
            timer.start()
        return True

    def _release(self, keys: list[int]) -> None:
        for vk in reversed(keys):
            try:
                _send(vk, True)
            except Exception:
                pass
        with self._lock:
            self._held = [vk for vk in self._held if vk not in keys]

    def release_all(self) -> None:
        with self._lock:
            held, self._held = self._held, []
        for vk in reversed(held):
            try:
                _send(vk, True)
            except Exception:
                pass
