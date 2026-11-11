# Reverse-engineering notes

Technical notes behind the clean-room SoundPod clone. No Soundpad code, icons,
sounds, or drivers are included in this repository.

Target: `C:\Program Files\Soundpad\Soundpad.exe`, version 4.0.9, SHA-256
`9b17717dfc9852e2c7b730cce4b8058528667d0b484bb936d3ce07b66ab50d72`.

## Proven from shipped files

- **No transcription.** The app has no speech-recognition library, model, string
  or network endpoint. It has text-to-speech, not speech-to-text.
- **TTS is local.** `TTS.dll` exports `CleanUp`, `GetAvailableVoiceCount`,
  `GetAvailableVoices`, `GetPreparedSpeech`, `PrepareTextToSpeech`. Its strings
  include `Windows.Media.SpeechSynthesis.SpeechSynthesizer`. `Soundpad.exe`
  contains the SSML template:
  `<speak version="1.0" ...><prosody rate="%s" pitch="%s">%s</prosody></speak>`.
- **TTS output is a temporary WAV.** Strings `sp-tts-`, `.wav`, `Temp\`,
  `Failed to create sound from text` and `Another text to speech operation is
  still in progress` match the export names.
- **Microphone injection is an APO.** `UniteFx.dll` strings include
  `RegisterApoInstanceInMemMapping`, `UniteFxControl::PlaySoundData`,
  `UniteFxControl::PlaySoundFile`, `UniteFxControl::Stop`,
  `Global\UniteFxTransferMutex1.8.0`, `Global\UniteFxMappingObject1.8.0`.
  The live registry proves the binding: capture endpoint
  `{8bd4063a-af79-425f-b9ce-1315984dccdf}` has
  `{d04e05a6-594b-4fb6-a80d-01af5eed7d1d},7 =
  {27384E53-9860-0AC3-9519-C60EBCAA2C71}` and that CLSID points to
  `C:\WINDOWS\system32\UniteFx1.8.0.dll`.
- **Global keys are a separate helper.** `SoundpadService.exe` imports
  `SetWindowsHookExW`, `RegisterRawInputDevices`, `GetAsyncKeyState` and
  `SendInput`. That is hotkey/Auto Keys work, not transcription.
- **Online feature is sound-list sharing.** The only app URL is
  `https://api.meowpad.me/v2/soundpad/`, adjacent to `recentSoundlists`.
- **Audio decoding uses Media Foundation** (`MF*.dll`) and `AVRT.dll`; playback
  and recording are local.
- **Signed by Arthur Lepp / Leppsoft.** Authenticode signer subject:
  `CN=Arthur Lepp, O=Arthur Lepp, C=DE`; file version 4.0.9.

## Inferred

- The GUI calls `TTS.dll` on a worker thread, writes the returned WAV under
  `%TEMP%`, then plays it through the same `UniteFxControl` path as a sound file.
  The strings and exports match this order; the exact call sites were not
  decompiled.
- The APO receives audio and control data over named shared memory and a mutex.
  The names and log messages strongly imply this, but the binary struct layout
  was not recovered.
- `api.meowpad.me` handles recent/shared sound lists. The endpoint was not
  reachable during testing, so request and response fields remain unknown.

## Hidden

- Exact C++ implementation, shared-memory structures, APO interface vtable, and
  meowpad request formats.
- Whether any legacy or server-side feature once used speech recognition. The
  installed 4.0.9 build does not.
- Runtime network traffic was not captured. Static imports and strings show no
  STT service.

## Feature parity

| Soundpad feature | SoundPod status |
| --- | --- |
| Sound list, categories, search | Yes |
| Global hotkeys | Yes, Windows `RegisterHotKey` |
| Play to speakers / microphone | Yes |
| Play to both, block voice | Yes |
| Microphone + sound mix in voice chat | Yes, through VB-CABLE |
| Recorder (mic and system audio) | Yes |
| Editor: cut, normalize, gain | Yes |
| Per-sound volume | Yes |
| Text to speech (local Windows voices) | Yes |
| Auto Keys (send keys with a sound) | Yes |
| Remote control from phone | Yes, local web page with a session key |
| Import / export `.spl` lists | Yes |
| Sound-list sharing (`meowpad.me`) | Not cloned: private API. Use `.spl` export. |
| Kernel audio driver (APO) | Not cloned: uses VB-CABLE |
| Injection into the physical mic endpoint | Needs a native APO/VST bridge; not included |
| Start with Windows / hotkey toggle | Yes |
| Preferences window | Yes |
| Windows default-microphone handoff | Yes, restored on exit |
| Volume boost beyond 100% | Yes, per-sound up to 300% |
