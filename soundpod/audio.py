"""Audio playback, decoding and virtual-microphone injection.

The clone does not install a kernel audio driver. It feeds a virtual cable
(VB-CABLE, VoiceMeeter or similar) with a mix of the real microphone and the
soundboard. Voice chat then selects the cable's capture side as its microphone.
"""

from __future__ import annotations

import hashlib
import os
import queue
import subprocess
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import imageio_ffmpeg
import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 48_000
CHANNELS = 2
BLOCK = 256


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run_hidden(args: list[str]) -> subprocess.CompletedProcess:
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=flags,
        check=False,
    )


@dataclass(frozen=True)
class Device:
    index: int
    name: str
    inputs: int
    outputs: int
    sample_rate: float
    hostapi: int

    @property
    def label(self) -> str:
        return f"{self.name}  (#{self.index})"


def list_devices() -> list[Device]:
    rows: list[Device] = []
    for index, item in enumerate(sd.query_devices()):
        rows.append(
            Device(
                index=index,
                name=str(item["name"]),
                inputs=int(item["max_input_channels"]),
                outputs=int(item["max_output_channels"]),
                sample_rate=float(item["default_samplerate"]),
                hostapi=int(item["hostapi"]),
            )
        )
    return rows


def _cable_score(name: str) -> int:
    needle = name.lower()
    if "cable in 16ch" in needle:
        # ASIO multichannel variant: usable but not the default stereo route.
        return 60
    if "cable input" in needle:
        return 100
    if "vb-audio" in needle or "voicemeeter input" in needle:
        return 80
    if "virtual" in needle and "audio" in needle:
        return 40
    return 0


def _hostapi_score(index: int, devices: list[Device]) -> int:
    try:
        name = str(sd.query_hostapis(index)["name"]).lower()
    except Exception:
        return 0
    if "wasapi" in name:
        return 3
    if "directsound" in name:
        return 2
    if "mme" in name:
        return 1
    return 0


def hostapi_name(index: int) -> str:
    try:
        return str(sd.query_hostapis(index)["name"])
    except Exception:
        return ""


def find_cable_output(devices: Iterable[Device] | None = None) -> Device | None:
    rows = list(devices or list_devices())
    candidates = [d for d in rows if d.outputs > 0]
    scored = sorted(
        candidates,
        key=lambda d: (_cable_score(d.name), _hostapi_score(d.hostapi, rows), -d.index),
        reverse=True,
    )
    if scored and _cable_score(scored[0].name) > 0:
        return scored[0]
    return None


def default_input(devices: Iterable[Device] | None = None) -> Device | None:
    """Pick the real microphone; never the cable's capture side."""
    rows = list(devices or list_devices())
    inputs = [row for row in rows if row.inputs > 0]
    if not inputs:
        return None
    try:
        index = int(sd.default.device[0])
    except Exception:
        index = -1

    def rank(row: Device) -> tuple[int, int, int]:
        name = row.name.lower()
        if "mapper" in name:
            score = 0
        elif is_virtual_output(row.name) or "stereo mix" in name:
            score = 10
        elif "microphone" in name or "mic" in name:
            score = 100
        else:
            score = 60
        return (
            score,
            1 if _accepts_rate(row, "input") else 0,
            _hostapi_score(row.hostapi, rows),
            1 if row.index == index else 0,
        )

    return max(inputs, key=rank)


def is_virtual_output(name: str) -> bool:
    needle = name.lower()
    return any(
        token in needle
        for token in ("cable", "voicemeeter", "virtual", "vb-audio", "stereo mix")
    )


def default_output(devices: Iterable[Device] | None = None) -> Device | None:
    """Pick the real playback device, never a virtual cable.

    Windows can silently switch its default playback to CABLE Input (the
    VB-CABLE installer does exactly that). Trusting ``sd.default.device`` then
    sends every sound into the cable, so the PC goes mute. Prefer the physical
    device and only fall back to a cable when nothing else exists.
    """
    rows = list(devices or list_devices())
    outputs = [row for row in rows if row.outputs > 0]
    if not outputs:
        return None
    try:
        index = int(sd.default.device[1])
    except Exception:
        index = -1

    def rank(row: Device) -> tuple[int, int, int]:
        name = row.name.lower()
        if "mapper" in name:
            score = 0
        elif is_virtual_output(row.name):
            score = 10
        elif "headphone" in name or "headset" in name:
            score = 100
        elif "speaker" in name:
            score = 80
        elif "hdmi" in name or "digital" in name or "nvidia" in name:
            score = 40
        else:
            score = 60
        # Prefer a device that opens at the engine rate, then WASAPI, then the
        # Windows default.
        return (
            score,
            1 if _accepts_rate(row, "output") else 0,
            _hostapi_score(row.hostapi, rows),
            1 if row.index == index else 0,
        )

    best = max(outputs, key=rank)
    if rank(best)[0] == 0:
        return next((row for row in outputs if "mapper" not in row.name.lower()), best)
    return best


def _accepts_rate(device: Device, kind: str, rate: int = SAMPLE_RATE) -> bool:
    """Ask PortAudio whether the endpoint opens at the engine rate."""
    try:
        if kind == "input":
            channels = min(2, device.inputs)
            sd.check_input_settings(
                device=device.index, samplerate=rate, channels=channels, dtype="float32"
            )
        else:
            channels = min(2, device.outputs)
            sd.check_output_settings(
                device=device.index, samplerate=rate, channels=channels, dtype="float32"
            )
        return channels > 0
    except Exception:
        return False


def windows_default_output(devices: Iterable[Device] | None = None) -> Device | None:
    """Return whatever Windows currently treats as the default playback device."""
    rows = list(devices or list_devices())
    try:
        index = int(sd.default.device[1])
    except Exception:
        return None
    return next((row for row in rows if row.index == index and row.outputs > 0), None)


class SoundData:
    """Decoded 48 kHz stereo float samples and their peak level."""

    def __init__(self, samples: np.ndarray, path: Path):
        if samples.ndim == 1:
            samples = samples[:, None]
        if samples.shape[1] == 1:
            samples = np.repeat(samples, 2, axis=1)
        elif samples.shape[1] > 2:
            samples = samples[:, :2]
        self.samples = np.ascontiguousarray(samples, dtype=np.float32)
        self.path = path
        self.duration = float(len(self.samples) / SAMPLE_RATE)
        peak = float(np.max(np.abs(self.samples))) if len(self.samples) else 0.0
        self.peak = peak

    def normalized(self, target_dbfs: float = -1.0) -> np.ndarray:
        if self.peak <= 1e-9:
            return self.samples
        target = 10.0 ** (target_dbfs / 20.0)
        return self.samples * (target / self.peak)


class SoundCache:
    """Transcodes every supported input to canonical 48 kHz stereo WAV once."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._data: OrderedDict[Path, SoundData] = OrderedDict()
        self._bytes = 0
        self._max_bytes = 512 * 1024 * 1024
        self._lock = threading.RLock()

    @staticmethod
    def _key(path: Path) -> str:
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|v2"
        return hashlib.sha1(raw.encode("utf-8", "surrogatepass")).hexdigest()

    def wav_path(self, source: Path) -> Path:
        source = Path(source)
        target = self.cache_dir / f"{self._key(source)}.wav"
        if target.exists() and target.stat().st_size > 44:
            return target
        tmp = target.with_suffix(".tmp.wav")
        result = _run_hidden(
            [
                _ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ac",
                str(CHANNELS),
                "-ar",
                str(SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(tmp),
            ]
        )
        if result.returncode != 0 or not tmp.exists():
            detail = result.stderr.decode("utf-8", "replace").strip()
            raise RuntimeError(f"Could not decode {source.name}: {detail}")
        os.replace(tmp, target)
        return target

    def get(self, source: Path) -> SoundData:
        source = Path(source)
        with self._lock:
            cached = self._data.get(source)
            if cached is not None:
                self._data.move_to_end(source)
                return cached
            wav = self.wav_path(source)
            samples, rate = sf.read(str(wav), dtype="float32", always_2d=True)
            if rate != SAMPLE_RATE:
                raise RuntimeError(f"Unexpected decode rate {rate} for {source.name}")
            data = SoundData(samples, source)
            self._data[source] = data
            self._bytes += data.samples.nbytes
            while self._bytes > self._max_bytes and len(self._data) > 1:
                _, old = self._data.popitem(last=False)
                self._bytes -= old.samples.nbytes
            return data

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._bytes = 0


class Voice:
    __slots__ = ("samples", "position", "gain")

    def __init__(self, samples: np.ndarray, gain: float):
        self.samples = samples
        self.position = 0
        self.gain = float(gain)

    @property
    def finished(self) -> bool:
        return self.position >= len(self.samples)


class Mixer:
    """Sample-accurate mix of overlapping sounds for one output device."""

    def __init__(self) -> None:
        self._voices: list[Voice] = []
        self._lock = threading.Lock()
        self._generation = 0

    def add(self, samples: np.ndarray, gain: float = 1.0) -> int:
        with self._lock:
            self._voices.append(Voice(samples, gain))
            self._generation += 1
            return self._generation

    def stop(self) -> None:
        with self._lock:
            self._voices.clear()

    @property
    def playing(self) -> bool:
        with self._lock:
            return bool(self._voices)

    def render(self, frames: int) -> np.ndarray:
        out = np.zeros((frames, CHANNELS), dtype=np.float32)
        with self._lock:
            if not self._voices:
                return out
            keep: list[Voice] = []
            for voice in self._voices:
                remaining = len(voice.samples) - voice.position
                take = min(frames, remaining)
                if take > 0:
                    out[:take] += voice.samples[voice.position : voice.position + take] * voice.gain
                    voice.position += take
                if not voice.finished:
                    keep.append(voice)
            self._voices = keep
        np.clip(out, -1.0, 1.0, out=out)
        return out


class DeviceOutput:
    """Stereo output stream backed by a mixer."""

    def __init__(self, device: int, on_error=None):
        self.device = int(device)
        self.mixer = Mixer()
        self._on_error = on_error
        self._stream: sd.OutputStream | None = None

    def start(self) -> None:
        if self._stream is not None:
            return
        try:
            self._stream = sd.OutputStream(
                device=self.device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=BLOCK,
                dtype="float32",
                latency="low",
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            raise

    def _callback(self, outdata, frames, _time, status) -> None:
        if status and self._on_error:
            self._on_error(str(status))
        outdata[:] = self.mixer.render(frames)

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def close(self) -> None:
        self.stop()


class MicInjector:
    """Captures the real microphone and writes mic + soundboard to a cable."""

    def __init__(self, input_device: int, output_device: int, on_error=None):
        self.input_device = int(input_device)
        self.output_device = int(output_device)
        self.mixer = Mixer()
        self._on_error = on_error
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=12)
        self._last = np.zeros((BLOCK, 1), dtype=np.float32)
        self._input: sd.InputStream | None = None
        self._output: sd.OutputStream | None = None
        self.block_voice = False
        self.passthrough = True

    def start(self) -> None:
        if self._input is not None:
            return
        info = sd.query_devices(self.input_device)
        channels = max(1, min(2, int(info["max_input_channels"])))
        try:
            self._input = sd.InputStream(
                device=self.input_device,
                samplerate=SAMPLE_RATE,
                channels=channels,
                blocksize=BLOCK,
                dtype="float32",
                latency="low",
                callback=self._input_callback,
            )
            self._output = sd.OutputStream(
                device=self.output_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=BLOCK,
                dtype="float32",
                latency="low",
                callback=self._output_callback,
            )
            self._input.start()
            self._output.start()
        except Exception:
            self.stop()
            raise

    def _input_callback(self, indata, _frames, _time, status) -> None:
        if status and self._on_error:
            self._on_error(str(status))
        frame = np.asarray(indata, dtype=np.float32).copy()
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass

    def _output_callback(self, outdata, frames, _time, status) -> None:
        if status and self._on_error:
            self._on_error(str(status))
        try:
            mic = self._queue.get_nowait()
            self._last = mic
        except queue.Empty:
            mic = self._last
        if len(mic) != frames:
            if len(mic) > frames:
                mic = mic[-frames:]
            else:
                pad = np.zeros((frames - len(mic), mic.shape[1]), dtype=np.float32)
                mic = np.vstack([mic, pad])
        if mic.shape[1] == 1:
            mic = np.repeat(mic, CHANNELS, axis=1)
        elif mic.shape[1] > CHANNELS:
            mic = mic[:, :CHANNELS]
        had_voice = self.mixer.playing
        voice = self.mixer.render(frames)
        level = 0.0 if (self.block_voice and had_voice) else (1.0 if self.passthrough else 0.0)
        outdata[:] = np.clip(mic * level + voice, -1.0, 1.0)

    def stop(self) -> None:
        for stream in (self._input, self._output):
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
        self._input = None
        self._output = None
        self._queue = queue.Queue(maxsize=12)

    def close(self) -> None:
        self.stop()


class AudioEngine:
    """Owns the speaker output and the microphone injector."""

    def __init__(self, cache_dir: Path):
        self.cache = SoundCache(cache_dir)
        self.volume = 0.75
        self.block_voice = False
        self.normalize = True
        self.speaker_device: int | None = None
        self.mic_device: int | None = None
        self.cable_device: int | None = None
        self._speaker: DeviceOutput | None = None
        self._injector: MicInjector | None = None
        self._lock = threading.Lock()
        self._errors: list[str] = []
        self._on_error = None
        self.current_title = ""

    def set_error_handler(self, handler) -> None:
        self._on_error = handler

    def _error(self, message: str) -> None:
        self._errors.append(message)
        if len(self._errors) > 50:
            self._errors = self._errors[-50:]
        if self._on_error:
            self._on_error(message)

    def start(self) -> None:
        with self._lock:
            self._stop_locked()
            if self.speaker_device is not None:
                try:
                    self._speaker = DeviceOutput(self.speaker_device, self._error)
                    self._speaker.start()
                except Exception as exc:
                    self._speaker = None
                    self._error(f"Speaker output failed: {exc}")
            if self.mic_device is not None and self.cable_device is not None:
                try:
                    self._injector = MicInjector(self.mic_device, self.cable_device, self._error)
                    self._injector.block_voice = self.block_voice
                    self._injector.start()
                except Exception as exc:
                    self._injector = None
                    self._error(f"Microphone injection failed: {exc}")

    def _stop_locked(self) -> None:
        if self._speaker:
            self._speaker.stop()
            self._speaker = None
        if self._injector:
            self._injector.stop()
            self._injector = None

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    @property
    def injection_ready(self) -> bool:
        return self._injector is not None

    def set_block_voice(self, enabled: bool) -> None:
        self.block_voice = bool(enabled)
        if self._injector:
            self._injector.block_voice = bool(enabled)

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))

    def set_normalize(self, enabled: bool) -> None:
        self.normalize = bool(enabled)

    def _samples_for(self, sound: SoundData) -> np.ndarray:
        return sound.normalized() if self.normalize else sound.samples

    def play(self, sound: SoundData, mode: str = "both", title: str = "", extra_gain: float = 1.0) -> None:
        samples = self._samples_for(sound)
        gain = self.volume * self.volume * max(0.0, float(extra_gain))
        used = False
        if mode in ("both", "speakers") and self._speaker:
            self._speaker.mixer.add(samples, gain)
            used = True
        if mode in ("both", "microphone") and self._injector:
            self._injector.mixer.add(samples, gain)
            used = True
        if used:
            self.current_title = title or sound.path.name
        elif mode in ("both", "microphone"):
            self._error("Microphone output is not available. Select a cable output device.")

    def play_file(
        self,
        path: Path,
        mode: str = "both",
        title: str = "",
        extra_gain: float = 1.0,
    ) -> None:
        self.play(self.cache.get(Path(path)), mode=mode, title=title, extra_gain=extra_gain)

    def stop_all(self) -> None:
        if self._speaker:
            self._speaker.mixer.stop()
        if self._injector:
            self._injector.mixer.stop()
        self.current_title = ""

    def levels(self) -> dict[str, bool]:
        return {
            "speaker": bool(self._speaker and self._speaker.mixer.playing),
            "injector": bool(self._injector and self._injector.mixer.playing),
        }

    def status(self) -> str:
        parts = []
        parts.append("speakers on" if self._speaker else "speakers off")
        parts.append("mic injection on" if self._injector else "mic injection off")
        return " | ".join(parts)
