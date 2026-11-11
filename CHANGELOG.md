# Changelog

## 1.0.2

- The Devices tab is taller and can be resized by dragging the divider above
  the tabs.
- The device options now scroll, so **Block voice**, **Normalize**, **Always on
  top**, **Global hotkeys**, and **Start SoundPod with Windows** stay reachable
  on small windows.

## 1.0.1

- Fixed recording failing when `SoundPodRecorder.exe` was missing. The app now
  shows a clear error and the Recorder tab explains how to fix it.
- The recorder now uses the microphone selected in **Preferences > Audio**
  instead of the Windows default, which SoundPod switches to `CABLE Output`.
- Added `--microphone` support to the recorder helper.
- Release instructions now say to extract all files, not just `SoundPod.exe`.

## 1.0.0

- First public release: sound library, categories, search, global hotkeys,
  speaker/microphone/both playback, block voice, normalize, TTS, recorder,
  editor, per-sound volume, Auto Keys, phone remote, `.spl` import/export,
  Preferences, and Windows default-microphone handoff.
