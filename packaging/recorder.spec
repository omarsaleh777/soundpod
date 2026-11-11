# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the SoundPodRecorder console helper.

Run from the project root:
    pyinstaller packaging/recorder.spec --noconfirm --clean --distpath dist/recorder
"""
from __future__ import annotations

from pathlib import Path

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path.cwd()

a = Analysis(
    [str(ROOT / "soundpod" / "record_worker.py")],
    pathex=[str(ROOT)],
    binaries=[(imageio_ffmpeg.get_ffmpeg_exe(), ".")],
    datas=[],
    hiddenimports=collect_submodules("soundcard")
    + [
        "soundpod.record_worker",
        "numpy",
        "soundcard",
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="SoundPodRecorder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
