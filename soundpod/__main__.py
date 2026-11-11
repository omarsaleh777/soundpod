"""Frozen-safe entry point for SoundPod.

PyInstaller executes this file as the top-level ``__main__`` module, so it must
use an absolute import (a relative import fails with "attempted relative import
with no known parent package").
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    roots = [Path(sys.executable).resolve().parent]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    for root in roots:
        match = next(iter(sorted(root.glob("ffmpeg*.exe"))), None)
        if match is not None:
            os.environ["IMAGEIO_FFMPEG_EXE"] = str(match)
            break

from soundpod.ui import main

if __name__ == "__main__":
    raise SystemExit(main())
