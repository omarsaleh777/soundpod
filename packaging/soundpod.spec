# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the SoundPod windowed application.

Run from the project root:
    pyinstaller packaging/soundpod.spec --noconfirm --clean
"""
from __future__ import annotations

from pathlib import Path

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path.cwd()
TOOLS = ROOT / "tools"

a = Analysis(
    [str(ROOT / "soundpod" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[(imageio_ffmpeg.get_ffmpeg_exe(), ".")],
    datas=[
        (str(TOOLS / "SoundVolumeView" / "SoundVolumeView.exe"), "tools/SoundVolumeView"),
        (str(TOOLS / "SoundVolumeView" / "readme.txt"), "tools/SoundVolumeView"),
        (str(TOOLS / "SoundVolumeView" / "SoundVolumeView.chm"), "tools/SoundVolumeView"),
    ],
    hiddenimports=collect_submodules("soundcard")
    + [
        "soundpod.audio",
        "soundpod.autokeys",
        "soundpod.editor",
        "soundpod.hotkeys",
        "soundpod.library",
        "soundpod.recorder",
        "soundpod.record_worker",
        "soundpod.remote",
        "soundpod.tts",
        "soundpod.ui",
        "soundpod.winaudio",
        "soundpod.preferences",
        "imageio_ffmpeg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

splash = Splash(
    image_file=str(ROOT / "packaging" / "splash.png"),
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="SoundPod",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "packaging" / "soundpod.ico"),
)
