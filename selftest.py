"""Run with: python selftest.py"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from soundpod.audio import SAMPLE_RATE, Mixer, SoundCache
from soundpod.autokeys import parse_keys
from soundpod.library import Library
from soundpod.recorder import worker_command
from soundpod.tts import TTS
from soundpod import winaudio


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok  {message}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="soundpod-test-") as tmp:
        root = Path(tmp)

        mixer = Mixer()
        samples = np.full((4800, 2), 0.25, dtype=np.float32)
        mixer.add(samples, 0.5)
        out = np.vstack([mixer.render(256) for _ in range(24)])
        check(out.shape == (6144, 2), "mixer renders stereo frames")
        check(abs(float(out.max()) - 0.125) < 1e-4, "mixer applies gain")
        check(not mixer.playing, "mixer retires finished voices")

        tone_path = root / "tone.wav"
        seconds = 0.6
        t = np.arange(int(44_100 * seconds)) / 44_100
        tone = 0.2 * np.sin(2 * math.pi * 440 * t)
        stereo = np.column_stack([tone, tone]).astype(np.float32)
        sf.write(str(tone_path), stereo, 44_100, subtype="PCM_16")

        cache = SoundCache(root / "cache")
        sound = cache.get(tone_path)
        check(sound.duration > 0.55 and sound.duration < 0.65, "ffmpeg decode and resample")
        check(sound.samples.shape[1] == 2, "decoded audio is stereo")
        check(abs(float(np.max(np.abs(sound.normalized()))) - 0.891) < 0.01, "peak normalize")

        library = Library(root / "library.json")
        library.add_path(tone_path, category="Tests")
        library.sounds[0].hotkey = "ctrl+alt+9"
        library.save()
        spl = root / "soundlist.spl"
        library.export_spl(spl)
        imported = Library(root / "imported.json")
        count = imported.import_spl(spl)
        check(count == 1, "Soundpad .spl round trip imports one sound")
        check(imported.sounds[0].hotkey == "ctrl+alt+9", "hotkey survives .spl round trip")

        holds, taps = parse_keys("~ctrl, f, ~shift")
        check(holds == [0x11, 0x10], "Auto Keys parses held modifiers")
        check(taps == [ord("F")], "Auto Keys parses tapped keys")

        render = winaudio.Endpoint("{0.0.0.00000000}.{abc}", "Speakers", "Render")
        capture = winaudio.Endpoint("{0.0.1.00000000}.{abc}", "Microphone", "Capture")
        check(
            winaudio.same_endpoint(render, capture),
            "endpoint IDs compare by GUID across render/capture prefixes",
        )
        command = worker_command("microphone", 48000, root / "x.pcm")
        check(
            "-m" in command and "soundpod.record_worker" in command,
            "recorder builds the source-run worker command",
        )

        tts = TTS(root / "tts")
        voices = tts.voices()
        check(bool(voices), "Windows TTS voices are available")
        wav = tts.synthesize("SoundPod self test.", voice=voices[0].name, rate=0, pitch=0)
        check(wav.exists() and wav.stat().st_size > 1000, "local TTS produced a WAV")
        spoken = SoundCache(root / "cache").get(wav)
        check(spoken.duration > 0.5, "TTS WAV decodes to 48 kHz audio")

    print("all checks passed")


if __name__ == "__main__":
    main()
