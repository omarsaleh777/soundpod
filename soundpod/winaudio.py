"""Windows default audio endpoint control.

VB-CABLE silently becomes the default playback device after installation. That
mutes the PC: every sound goes into the cable instead of the speakers. This
module reads installed endpoints from the registry and switches the Windows
default endpoint through the undocumented IPolicyConfig COM interface.
"""

from __future__ import annotations

import ctypes
import csv
import subprocess
import sys
import tempfile
import time
import winreg
from ctypes import POINTER, Structure, byref, c_int, c_void_p, c_wchar_p
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CLSID_POLICY_CONFIG = "{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}"
IID_POLICY_CONFIG = "{F8679F50-850A-4961-AB95-3F3B0B1A2A9B}"

PKEY_FRIENDLY_NAME = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
PKEY_DEVICE_STATE = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"

DEVICE_STATE_ACTIVE = 0x1

RENDER = "Render"
CAPTURE = "Capture"

_ROLES = (0, 1, 2)  # console, multimedia, communications


class GUID(Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, value: str = ""):
        super().__init__()
        if not value:
            return
        text = value.strip("{}")
        parts = text.split("-")
        self.Data1 = int(parts[0], 16)
        self.Data2 = int(parts[1], 16)
        self.Data3 = int(parts[2], 16)
        tail = bytes.fromhex(parts[3] + parts[4])
        for index, byte in enumerate(tail):
            self.Data4[index] = byte


@dataclass(frozen=True)
class Endpoint:
    id: str
    name: str
    kind: str

    @property
    def active(self) -> bool:
        return True

    def __str__(self) -> str:
        return f"{self.name} [{self.kind}]"


@dataclass(frozen=True)
class HelperDevice:
    """One SoundVolumeView row, keyed by its normalised MMDevice ID."""

    id: str
    friendly: str
    name: str
    default: str


def _read_string(root, path: str) -> str:
    try:
        with winreg.OpenKey(root, path) as key:
            value, _type = winreg.QueryValueEx(key, PKEY_FRIENDLY_NAME)
            return str(value)
    except OSError:
        return ""


def _read_state(root, path: str) -> int:
    try:
        with winreg.OpenKey(root, path) as key:
            value, _type = winreg.QueryValueEx(key, "DeviceState")
            return int(value)
    except OSError:
        return 0


def endpoints(kind: str | None = None) -> list[Endpoint]:
    """List active render (playback) and capture (recording) endpoints."""
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio"
    found: list[Endpoint] = []
    for group in (RENDER, CAPTURE):
        if kind is not None and group.lower() != kind.lower():
            continue
        prefix = "{0.0.0.00000000}"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{group}") as node:
                count = winreg.QueryInfoKey(node)[0]
                names = [winreg.EnumKey(node, index) for index in range(count)]
        except OSError:
            continue
        for name in names:
            path = f"{base}\\{group}\\{name}"
            if _read_state(winreg.HKEY_LOCAL_MACHINE, path) != DEVICE_STATE_ACTIVE:
                continue
            label = _read_string(winreg.HKEY_LOCAL_MACHINE, f"{path}\\Properties")
            if not label:
                continue
            found.append(Endpoint(id=f"{prefix}\\{name}", name=label, kind=group))
    return found


def _create_policy_config():
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx(None, 0)
    clsid = GUID(CLSID_POLICY_CONFIG)
    iid = GUID(IID_POLICY_CONFIG)
    pointer = c_void_p()
    result = ole32.CoCreateInstance(
        byref(clsid), None, 1, byref(iid), byref(pointer)
    )
    if result != 0 or not pointer.value:
        raise OSError(f"IPolicyConfig unavailable (HRESULT 0x{result & 0xFFFFFFFF:08x})")
    return pointer


def _method(pointer: c_void_p, index: int, restype, *argtypes):
    vtable = ctypes.cast(pointer, POINTER(POINTER(c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    return prototype(vtable[index])


def set_default(endpoint_id: str) -> None:
    """Make an endpoint the default device for all three Windows roles."""
    pointer = _create_policy_config()
    try:
        set_default_endpoint = _method(pointer, 13, ctypes.c_long, c_wchar_p, c_int)
        for role in _ROLES:
            result = set_default_endpoint(pointer, endpoint_id, role)
            if result != 0:
                raise OSError(f"SetDefaultEndpoint failed (0x{result & 0xFFFFFFFF:08x})")
    finally:
        release = _method(pointer, 2, ctypes.c_ulong)
        release(pointer)


def _helper_candidates() -> list[Path]:
    bases: list[Path] = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).resolve().parent)
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            bases.append(Path(bundle))
    else:
        bases.append(Path(__file__).resolve().parent.parent)
    rows: list[Path] = []
    for base in bases:
        rows.append(base / "tools" / "SoundVolumeView" / "SoundVolumeView.exe")
    seen: set[str] = set()
    unique: list[Path] = []
    for row in rows:
        key = str(row).lower()
        if key in seen or not row.exists():
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _normalize_id(value: str) -> str:
    """Return the device GUID from either MMDevice item-ID spelling.

    The registry uses ``{0.0.0.00000000}\\{guid}``. SoundVolumeView prints
    ``{0.0.0.00000000}.{guid}`` for render endpoints and
    ``{0.0.1.00000000}.{guid}`` for capture endpoints, so comparing the whole
    string misses microphones. The final ``{…}`` segment is the stable GUID.
    """
    text = value.strip().lower()
    start = text.rfind("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text.replace("}.{", "}\\{")


def same_endpoint(first: Endpoint | None, second: Endpoint | None) -> bool:
    if first is None or second is None:
        return False
    return _normalize_id(first.id) == _normalize_id(second.id)


_HELPER_CACHE: dict[str, tuple[float, dict[str, HelperDevice]]] = {}
_HELPER_CACHE_SECONDS = 10.0


def _helper_devices(exe: Path) -> dict[str, HelperDevice]:
    """Map MMDevice item IDs to SoundVolumeView rows."""
    key = str(exe).lower()
    cached = _HELPER_CACHE.get(key)
    if cached is not None and (time.monotonic() - cached[0]) < _HELPER_CACHE_SECONDS:
        return cached[1]
    handle = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    handle.close()
    path = Path(handle.name)
    found: dict[str, HelperDevice] = {}
    try:
        flags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.run(
            [str(exe), "/scomma", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            timeout=20,
            check=False,
        )
        if not path.exists() or path.stat().st_size == 0:
            return {}
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("Type") != "Device":
                    continue
                item = (row.get("Item ID") or "").strip()
                friendly = (row.get("Command-Line Friendly ID") or "").strip()
                if item and friendly:
                    found[_normalize_id(item)] = HelperDevice(
                        id=item,
                        friendly=friendly,
                        name=(row.get("Name") or "").strip(),
                        default=(row.get("Default") or "").strip().lower(),
                    )
        _HELPER_CACHE[key] = (time.monotonic(), found)
        return found
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def _invalidate_helper_cache() -> None:
    _HELPER_CACHE.clear()


def default_capture() -> Endpoint | None:
    """Return the Windows default recording endpoint."""
    known = {_normalize_id(row.id): row for row in endpoints(CAPTURE)}
    for exe in _helper_candidates():
        for key, device in _helper_devices(exe).items():
            if "capture" in device.default:
                row = known.get(key)
                if row is not None:
                    return row
    return None


def set_default_compat(endpoint_id: str) -> str:
    """Set the Windows default endpoint, returning a short description.

    Windows 11 25H2 no longer exposes IPolicyConfig through AudioSes.dll, so the
    in-process COM call fails with E_NOINTERFACE. Fall back to the bundled
    SoundVolumeView helper, which speaks the current audio-policy APIs.
    """
    try:
        set_default(endpoint_id)
        _invalidate_helper_cache()
        return "set through IPolicyConfig"
    except OSError as error:
        first = error
    for exe in _helper_candidates():
        devices = _helper_devices(exe)
        match = devices.get(_normalize_id(endpoint_id))
        if not match:
            continue
        result = subprocess.run(
            [str(exe), "/SetDefault", match.friendly, "all"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            timeout=20,
            check=False,
        )
        if result.returncode == 0:
            _invalidate_helper_cache()
            return f"set through SoundVolumeView ({match.name})"
    raise OSError(
        f"{first}. Open Settings > System > Sound and choose a real output device. "
        "SoundVolumeView.exe was not found next to the app."
    )


def find(name_part: str, kind: str) -> Endpoint | None:
    needle = name_part.lower()
    rows = endpoints(kind)
    for row in rows:
        if needle in row.name.lower():
            return row
    return None


def cable_input() -> Endpoint | None:
    for row in endpoints(RENDER):
        name = row.name.lower()
        if "cable input" in name and "16ch" not in name:
            return row
    return None


def cable_output() -> Endpoint | None:
    for row in endpoints(CAPTURE):
        name = row.name.lower()
        if "cable output" in name and "point" not in name:
            return row
    return None


def physical_output(exclude: Iterable[Endpoint] = ()) -> Endpoint | None:
    skip = {row.id for row in exclude}
    scored = []
    for row in endpoints(RENDER):
        name = row.name.lower()
        if row.id in skip:
            continue
        if "cable" in name or "voicemeeter" in name or "virtual" in name:
            continue
        score = 50
        if "headphone" in name or "headset" in name:
            score = 100
        elif "speaker" in name:
            score = 80
        elif "hdmi" in name or "digital" in name or "nvidia" in name:
            score = 10
        scored.append((score, row))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def physical_input(exclude: Iterable[Endpoint] = ()) -> Endpoint | None:
    skip = {row.id for row in exclude}
    for row in endpoints(CAPTURE):
        name = row.name.lower()
        if row.id in skip:
            continue
        if "cable" in name or "voicemeeter" in name or "virtual" in name or "stereo mix" in name:
            continue
        if "mapper" in name:
            continue
        return row
    return None
