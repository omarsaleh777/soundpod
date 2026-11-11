"""Child process that records raw PCM with soundcard and exits.

The soundcard/Media Foundation recorder works on the process main thread, so a
child process is used. It streams raw PCM16 and flushes every block. The parent
wraps the raw file into WAV after stopping; the child exits without waiting for
the audio driver to close.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading

import numpy as np
import soundcard as sc


def pick_device(source: str):
    if source == "system":
        speaker = sc.default_speaker()
        if speaker is None:
            raise RuntimeError("No default speaker")
        return sc.get_microphone(speaker.name, include_loopback=True)
    mic = sc.default_microphone()
    if mic is None:
        raise RuntimeError("No default microphone")
    return mic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("microphone", "system"), default="microphone")
    parser.add_argument("--rate", type=int, default=48_000)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    stop = threading.Event()

    def watch_stdin() -> None:
        try:
            for line in sys.stdin:
                if line.strip().lower() == "stop":
                    break
        except Exception:
            pass
        stop.set()

    threading.Thread(target=watch_stdin, daemon=True).start()

    device = pick_device(args.source)
    channels = max(1, min(2, int(getattr(device, "channels", 2) or 2)))
    sys.stdout.write("ready\n")
    sys.stdout.flush()

    with device.recorder(samplerate=args.rate, channels=channels, blocksize=9600) as recorder:
        with open(args.output, "wb") as target:
            while not stop.is_set():
                data = recorder.record(numframes=4800)
                if data is None or not len(data):
                    continue
                if data.shape[1] == 1:
                    data = np.repeat(data, 2, axis=1)
                pcm = (np.clip(data[:, :2], -1.0, 1.0) * 32767.0).astype("<i2")
                target.write(pcm.tobytes())
                target.flush()

    sys.stdout.write("stopped\n")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
