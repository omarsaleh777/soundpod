"""Microphone and system-audio recorder.

Recording runs in a child process (soundcard/Media Foundation needs its main
thread). The child streams raw PCM; the parent wraps it into WAV when stopping,
so a slow driver cannot freeze the UI.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 48_000


def _record_helper() -> Path | None:
    """Locate the console recorder helper next to the frozen app."""
    names = ("SoundPodRecorder.exe",) if os.name == "nt" else ("SoundPodRecorder",)
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            roots.append(Path(bundle))
    else:
        roots.append(Path(__file__).resolve().parent.parent)
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.exists():
                return candidate
    return None


def worker_command(source: str, rate: int, output: Path) -> list[str]:
    """Build the child-process command for source runs and frozen builds."""
    helper = _record_helper()
    if getattr(sys, "frozen", False):
        if helper is None:
            raise RuntimeError(
                "SoundPodRecorder.exe is missing from the application folder. "
                "Reinstall or rebuild SoundPod."
            )
        return [
            str(helper),
            "--source",
            source,
            "--rate",
            str(rate),
            "--output",
            str(output),
        ]
    return [
        sys.executable,
        "-m",
        "soundpod.record_worker",
        "--source",
        source,
        "--rate",
        str(rate),
        "--output",
        str(output),
    ]


class Recorder:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._process: subprocess.Popen | None = None
        self._part: Path | None = None
        self._last_path: Path | None = None
        self._error: str | None = None
        self.started_at: float = 0.0
        self._source = "microphone"

    def set_output_dir(self, path: Path | str) -> None:
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        self.output_dir = target

    @property
    def recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, source: str = "microphone") -> None:
        if self.recording:
            return
        if source not in ("microphone", "system"):
            source = "microphone"
        stamp = datetime.now().strftime("recording-%Y%m%d-%H%M%S")
        self._part = (self.output_dir / f".{stamp}.pcm").resolve()
        self._last_path = None
        self._error = None
        self._source = source
        self.started_at = time.time()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        command = worker_command(source, RATE, self._part)
        if getattr(sys, "frozen", False):
            cwd = str(Path(sys.executable).resolve().parent)
        else:
            cwd = str(Path(__file__).resolve().parent.parent)
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
            cwd=cwd,
        )
        ready = self._process.stdout.readline().strip() if self._process.stdout else ""
        if ready != "ready":
            detail = ""
            if self._process.stderr:
                detail = self._process.stderr.read().strip()
            self._process = None
            raise RuntimeError(detail or "Recording process did not start")

    def stop(self, wait: float = 3.0) -> Path | None:
        process = self._process
        if process is None:
            return self._last_path
        try:
            if process.stdin is not None:
                process.stdin.write("stop\n")
                process.stdin.flush()
                process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        stderr = ""
        if process.stderr is not None:
            try:
                stderr = process.stderr.read().strip()
            except Exception:
                pass
        self._process = None
        part = self._part
        self._part = None
        if part is None or not part.exists() or part.stat().st_size < 4:
            raise RuntimeError(stderr or "Nothing was recorded")
        raw = np.fromfile(part, dtype="<i2")
        part.unlink(missing_ok=True)
        if raw.size < 2:
            raise RuntimeError("Nothing was recorded")
        if raw.size % 2:
            raw = raw[:-1]
        audio = raw.reshape(-1, 2).astype(np.float32) / 32768.0
        target = self.output_dir / (datetime.now().strftime("recording-%Y%m%d-%H%M%S") + ".wav")
        sf.write(str(target), np.clip(audio, -1.0, 1.0), RATE, subtype="PCM_16")
        self._last_path = target
        return target
