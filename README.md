# SoundPod

[![Build Windows EXE](https://github.com/omarsaleh777/soundpod/actions/workflows/build.yml/badge.svg)](https://github.com/omarsaleh777/soundpod/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/omarsaleh777/soundpod)](https://github.com/omarsaleh777/soundpod/releases/latest)

A free Windows soundboard. Play sounds and local text-to-speech through your
microphone in Discord, TeamSpeak, games, or any app that records audio.

Clean-room clone inspired by Soundpad. No account, no cloud, no telemetry.
Not affiliated with Leppsoft.

## Download and run

You do **not** need Python to use the release.

1. Open the **[Releases page](https://github.com/omarsaleh777/soundpod/releases/latest)**.
2. Download `SoundPod-release.zip` from the latest release.
3. **Extract the zip** to a folder such as `C:\SoundPod`. Do not run it from
   inside the zip.
4. Install **VB-CABLE** once (see below).
5. Run `SoundPod.exe`.
6. Open **Preferences > Audio** and choose your speakers, microphone, and
   `CABLE Input`.
7. In your voice app, select `CABLE Output` as the microphone.

A small splash appears while the app unpacks. If Windows SmartScreen warns,
click **More info > Run anyway**.

## What you need

- Windows 10 or 11, 64-bit.
- [VB-CABLE](https://vb-audio.com/Cable/) (free) for microphone injection.
- A microphone and headphones or speakers.

SoundPod plays sounds on your speakers without VB-CABLE. The cable is only
needed to send sounds into voice chat.

## One-time VB-CABLE setup

1. Download the official package from <https://vb-audio.com/Cable/>.
2. Extract it and run `VBCABLE_Setup_x64.exe` as administrator.
3. Reboot Windows.
4. **Check Windows playback.** The installer sometimes makes `CABLE Input` the
   default playback device, which mutes the PC. If that happens, SoundPod shows
   a warning and a **Fix Windows default playback** button. You can also fix it
   in Windows Settings > System > Sound.
5. Open SoundPod > **Preferences > Audio**:
   - **Speakers**: your headphones or speakers.
   - **Microphone**: your real microphone.
   - **Cable input for mic injection**: `CABLE Input (VB-Audio Virtual Cable)`.
   - Click **Apply**, then **OK**.

## Make it work with other apps

Most games and chat apps use the Windows **default microphone**. SoundPod can
switch that default to `CABLE Output` while it runs:

- **Preferences > Audio** > **Windows microphone compatibility**.
- Keep **"Make CABLE Output the Windows default microphone while SoundPod runs"**
  enabled.
- SoundPod restores your previous microphone when it closes.

Apps where you explicitly picked a physical mic still need `CABLE Output`
selected once. Also turn off their noise suppression, automatic gain, and echo
cancellation; those features cut soundboard audio.

The green strip on the main window shows the live state:

- **MIC INJECTION: ON** — the cable stream is active.
- **WINDOWS MIC: CABLE OUTPUT** — apps using the default microphone can hear it.

If either is wrong, click **Open audio setup** on the orange banner.

## Using SoundPod

- **Add sounds**: drag files onto the window, or click **Add**. MP3, WAV, OGG,
  FLAC, AAC, M4A, MP4, Opus, WMA, and AIF are supported.
- **Play**: double-click a sound, press **Enter**, click a hotbar button, or use
  a global hotkey.
- **Set a hotkey**: right-click a sound > **Set hotkey**, or press `Ctrl+H`.
- **Block voice**: the **BLOCK VOICE** button on the green strip. Your voice is
  replaced by the sound while it plays.
- **Normalize**: the **NORMALIZE** button. Evens out loudness across sounds.
- **Volume**: the slider in the toolbar, or right-click a sound > **Set volume**
  (up to 300%).
- **Edit**: select a sound and press `Ctrl+E` to trim, normalize, or change gain.
- **Auto Keys**: right-click > **Set Auto Keys**. `~ctrl` holds Ctrl until the
  sound ends; `f` taps F. Example: `~ctrl, f`.
- **Text to speech**: type text, choose a voice, click **Speak to both**.
- **Record**: choose microphone or system audio, then **Start recording**.
- **Phone remote**: **Window > Phone remote**. Open the address shown on a phone
  in the same Wi-Fi. The link contains a private session key; keep it to
  yourself. Windows Firewall may ask once.
- **Import a Soundpad list**: **File > Import Soundpad list** (`.spl`).

### Shortcuts

| Shortcut | Action |
| --- | --- |
| Enter | Play selected sound |
| Esc | Stop |
| Delete | Remove selected sound |
| Ctrl+O | Add files |
| Ctrl+F | Search |
| Ctrl+H | Set hotkey |
| Ctrl+E | Edit sound |
| Ctrl+T | Text to speech |
| Ctrl+R | Record |
| Ctrl+, | Preferences |

## Tips for clear audio

- Use the **DirectSound** or **WASAPI** entry for your microphone, not MME.
- Keep the cable at 48 kHz. VB-CABLE defaults to 2-channel, 24-bit, 48 kHz.
- Disable noise suppression, auto gain, and echo cancellation in the voice app.
- Do not run two soundboards or two copies of SoundPod at once.

## Troubleshooting

- **The app does not open**: check `%APPDATA%\SoundPod\crash.log`. A second copy
  may already be running; SoundPod brings the existing window to the front.
  Look for its tray icon.
- **No sound in voice chat**: the voice app must use `CABLE Output`. The strip
  should show **MIC INJECTION: ON** and **WINDOWS MIC: CABLE OUTPUT**.
- **The PC is silent after installing VB-CABLE**: Windows switched playback to
  `CABLE Input`. Click **Fix Windows default playback** in the Devices tab or
  Preferences, or choose your headphones in Windows Settings.
- **My mic is silent when SoundPod is closed**: expected; `CABLE Output` only
  carries audio while SoundPod runs. SoundPod restores the default mic on exit.
- **A hotkey does nothing**: check the status bar. Another app may own the key;
  pick a different combination. See **Hotkeys > Status**.
- **Crackling**: close other audio apps, or change `BLOCK = 256` to `512` in
  `soundpod/audio.py` when running from source.
- **No Windows voices**: Settings > Time & Language > Speech > Add voices.
- **SoundVolumeView.exe is unsigned**: it is the bundled NirSoft helper used
  only when Windows blocks the default-device API. It is freeware, included
  unmodified with its readme, and is not downloaded at runtime.

## Data and privacy

- Library: `%APPDATA%\SoundPod\library.json`
- Settings: `%APPDATA%\SoundPod\settings.json`
- Recordings: `%APPDATA%\SoundPod\recordings`
- Decode cache: `%LOCALAPPDATA%\SoundPod\cache`
- Crash log: `%APPDATA%\SoundPod\crash.log`

Everything runs locally. There is no account, no telemetry, and no upload.
The phone remote listens only on your local network and requires a random
per-session key that is part of the link shown in the app.

## Build from source

Requirements: Windows 10/11, Python 3.11 or newer.

```powershell
python -m pip install -r requirements.txt
.\run.bat
```

`run.bat` launches without a console. Use `run-console.bat` to see errors.

Build the EXE and release zip:

```powershell
python -m pip install -r requirements-build.txt
.\build.ps1
```

This produces `release\SoundPod.exe`, `release\SoundPodRecorder.exe`, and
`SoundPod-release.zip`. The PyInstaller specs are in `packaging/`.

The GitHub workflow in `.github/workflows/build.yml` builds the same zip on a
Windows runner. Push a tag such as `v1.0.0` and it attaches the zip to the
GitHub release.

## How it works

SoundPod captures your real microphone, mixes in the active sounds at 48 kHz,
and writes the result to `CABLE Input`. Your voice app records `CABLE Output`.
A second output stream plays the same sounds on your speakers.

Soundpad uses its own signed driver inside the microphone stream. SoundPod is
user-mode and needs VB-CABLE instead. See
[docs/REVERSE-ENGINEERING.md](docs/REVERSE-ENGINEERING.md) for the technical
notes.

## Differences from Soundpad

- Microphone injection needs VB-CABLE; Soundpad uses a private APO driver.
- No kernel driver, Windows service, or per-device APO installation.
- No meowpad.me sound-list sharing; use `.spl` import/export instead.
- UI is inspired by Soundpad, not pixel-identical.

## Credits

- VB-CABLE by VB-Audio — external dependency, not bundled.
- SoundVolumeView by NirSoft — freeware, bundled unmodified with its readme.
- Built with Python, PySide6, NumPy, sounddevice, soundfile, and FFmpeg.

## License

MIT for the SoundPod code. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). SoundVolumeView remains
NirSoft freeware under its own terms. VB-CABLE is not included.
