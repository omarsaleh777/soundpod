"""Local Windows text-to-speech through System.Speech (SAPI).

Soundpad uses the WinRT SpeechSynthesizer. This clone uses the same Windows
voice packs through System.Speech, which supports SSML rate and pitch.
No cloud service is contacted.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

_VOICES_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $rows = @($s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object {
        [pscustomobject]@{
            Name = $_.VoiceInfo.Name
            Culture = $_.VoiceInfo.Culture.Name
            Gender = "$($_.VoiceInfo.Gender)"
            Age = "$($_.VoiceInfo.Age)"
        }
    })
    if ($rows.Count -eq 0) { '[]' } else { ConvertTo-Json -InputObject $rows -Compress }
} finally {
    $s.Dispose()
}
"""

_SYNTH_SCRIPT = r"""
param(
    [Parameter(Mandatory=$true)][string]$Out,
    [Parameter(Mandatory=$true)][string]$TextB64,
    [string]$Voice = '',
    [string]$Lang = 'en-US',
    [int]$Rate = 0,
    [int]$Pitch = 0
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($Voice -ne '') { $s.SelectVoice($Voice) }
    $text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TextB64))
    $escaped = [System.Security.SecurityElement]::Escape($text)
    $rateText = $(if ($Rate -ge 0) { "+$Rate%" } else { "$Rate%" })
    $pitchText = $(if ($Pitch -ge 0) { "+$Pitch%" } else { "$Pitch%" })
    $ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='$Lang'><prosody rate='$rateText' pitch='$pitchText'>$escaped</prosody></speak>"
    $s.SetOutputToWaveFile($Out)
    try {
        $s.SpeakSsml($ssml)
    } catch {
        $s.Speak($text)
    }
} finally {
    $s.Dispose()
}
"""


@dataclass(frozen=True)
class Voice:
    name: str
    culture: str = ""
    gender: str = ""
    age: str = ""

    @property
    def label(self) -> str:
        extra = ", ".join(part for part in (self.culture, self.gender) if part)
        return f"{self.name} ({extra})" if extra else self.name


class TTS:
    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._script = self.work_dir / "synthesize.ps1"
        self._script.write_text(_SYNTH_SCRIPT, encoding="utf-8")
        self._voices: list[Voice] | None = None
        self._lock = threading.Lock()

    @staticmethod
    def available() -> bool:
        return os.name == "nt"

    def _powershell(self, args: list[str]) -> subprocess.CompletedProcess:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=flags,
            check=False,
        )

    def voices(self, refresh: bool = False) -> list[Voice]:
        if not self.available():
            return []
        with self._lock:
            if self._voices is not None and not refresh:
                return list(self._voices)
            done = self._powershell(["-NoProfile", "-NonInteractive", "-Command", _VOICES_SCRIPT])
            rows: list[Voice] = []
            if done.returncode == 0:
                text = done.stdout.decode("utf-8", "replace").strip()
                try:
                    payload = json.loads(text) if text else []
                    if isinstance(payload, dict):
                        payload = [payload]
                    for item in payload:
                        rows.append(
                            Voice(
                                name=str(item.get("Name", "")),
                                culture=str(item.get("Culture", "")),
                                gender=str(item.get("Gender", "")),
                                age=str(item.get("Age", "")),
                            )
                        )
                except Exception:
                    rows = []
            self._voices = [row for row in rows if row.name]
            return list(self._voices)

    def synthesize(
        self,
        text: str,
        voice: str = "",
        rate: int = 0,
        pitch: int = 0,
        language: str = "en-US",
    ) -> Path:
        if not self.available():
            raise RuntimeError("Text-to-speech requires Windows")
        text = text.strip()
        if not text:
            raise ValueError("Nothing to speak")
        # -10..10 UI sliders become -30%..+30% rate and -50%..+50% pitch.
        rate_pct = int(max(-10, min(10, rate)) * 3)
        pitch_pct = int(max(-10, min(10, pitch)) * 5)
        out = self.work_dir / f"tts-{os.getpid()}-{uuid.uuid4().hex[:8]}.wav"
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        args = [
            "-File",
            str(self._script),
            "-Out",
            str(out),
            "-TextB64",
            encoded,
            "-Voice",
            voice,
            "-Lang",
            language or "en-US",
            "-Rate",
            str(rate_pct),
            "-Pitch",
            str(pitch_pct),
        ]
        done = self._powershell(args)
        if done.returncode != 0 or not out.exists() or out.stat().st_size < 64:
            detail = done.stderr.decode("utf-8", "replace").strip()
            raise RuntimeError(f"Speech synthesis failed: {detail}")
        return out
