"""Soundpad-style Preferences window.

The dialog owns only its widgets. MainWindow applies the returned values, so
the Devices tab, tray menu and main control strip stay in sync with one source
of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .audio import (
    Device,
    default_input,
    default_output,
    find_cable_output,
    hostapi_name,
    list_devices,
)
from .hotkeys import hotkey_to_qt, qt_to_hotkey
from . import winaudio


class HotkeyDialog(QDialog):
    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set hotkey")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Press the key combination for this sound."))
        self.edit = QKeySequenceEdit()
        if current:
            self.edit.setKeySequence(QKeySequence(hotkey_to_qt(current)))
        layout.addWidget(self.edit)
        hint = QLabel("Examples: F8, Ctrl+Alt+1, Shift+Num+2")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self.edit.clear)
        layout.addWidget(buttons)

    def value(self) -> str:
        return qt_to_hotkey(self.edit.keySequence().toString())


class PreferencesDialog(QDialog):
    def __init__(
        self,
        settings: dict,
        parent=None,
        devices: list[Device] | None = None,
        library=None,
        audio=None,
        hotkey_summary: str = "",
        on_apply=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("SoundPod Preferences")
        self.setMinimumSize(780, 560)
        if parent is not None and parent.styleSheet():
            self.setStyleSheet(parent.styleSheet())

        self._settings = dict(settings)
        self._devices = list(devices if devices is not None else list_devices())
        self._library = library
        self._audio = audio
        self._on_apply = on_apply
        self._hotkey_changes: dict[str, str] = {}
        self._hotkey_summary = hotkey_summary
        self._default_mic_changed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        title = QLabel("Preferences")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel("Audio, hotkeys, window behaviour and advanced options.")
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._audio_tab(), "Audio")
        self.tabs.addTab(self._hotkeys_tab(), "Hotkeys")
        self.tabs.addTab(self._interface_tab(), "Interface")
        self.tabs.addTab(self._advanced_tab(), "Advanced")
        root.addWidget(self.tabs, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        root.addWidget(self.buttons)

    # ------------------------------------------------------------------ audio

    def _audio_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        devices_box = QGroupBox("Devices")
        form = QFormLayout(devices_box)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(7)

        self.speaker_combo = QComboBox()
        self.mic_combo = QComboBox()
        self.cable_combo = QComboBox()
        for combo in (self.speaker_combo, self.mic_combo, self.cable_combo):
            combo.setMinimumWidth(380)
        form.addRow("Speakers", self.speaker_combo)
        form.addRow("Microphone", self.mic_combo)
        form.addRow("Cable input for mic injection", self.cable_combo)
        self._fill_devices()

        refresh_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh device list")
        refresh_btn.clicked.connect(self._refresh_devices)
        refresh_row.addWidget(refresh_btn)
        refresh_row.addStretch(1)
        form.addRow("", refresh_row)

        hint = QLabel(
            "Microphone is your real mic. Cable input is the playback side of "
            "VB-CABLE; voice apps listen to its capture side, CABLE Output."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        layout.addWidget(devices_box)

        playback_box = QGroupBox("Playback")
        play_form = QFormLayout(playback_box)
        play_form.setSpacing(7)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Speakers + microphone", "both")
        self.mode_combo.addItem("Speakers only", "speakers")
        self.mode_combo.addItem("Microphone only", "microphone")
        index = self.mode_combo.findData(self._settings.get("mode", "both"))
        self.mode_combo.setCurrentIndex(max(0, index))
        play_form.addRow("Play sounds to", self.mode_combo)

        volume_row = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(float(self._settings.get("volume", 0.75)) * 100))
        self.volume_value = QLabel(f"{self.volume_slider.value()}%")
        self.volume_value.setObjectName("muted")
        self.volume_value.setFixedWidth(42)
        self.volume_slider.valueChanged.connect(
            lambda value: self.volume_value.setText(f"{value}%")
        )
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_value)
        play_form.addRow("Master volume", volume_row)

        self.normalize_check = QCheckBox("Normalize each sound to a consistent peak")
        self.normalize_check.setChecked(bool(self._settings.get("normalize", True)))
        play_form.addRow("", self.normalize_check)
        self.block_check = QCheckBox("Block voice while a sound plays (replace the microphone)")
        self.block_check.setChecked(bool(self._settings.get("block_voice", False)))
        play_form.addRow("", self.block_check)
        layout.addWidget(playback_box)

        windows_box = QGroupBox("Windows microphone compatibility")
        windows_layout = QVBoxLayout(windows_box)
        windows_layout.setSpacing(6)
        self.auto_mic_check = QCheckBox(
            "Make CABLE Output the Windows default microphone while SoundPod runs"
        )
        self.auto_mic_check.setChecked(bool(self._settings.get("auto_default_mic", True)))
        self.auto_mic_check.toggled.connect(self._auto_mic_toggled)
        windows_layout.addWidget(self.auto_mic_check)
        auto_hint = QLabel(
            "Most apps follow the Windows default microphone. With this on, "
            "games and chat apps that use the default hear SoundPod without "
            "manual setup. The previous microphone is restored when SoundPod "
            "closes. Apps where you explicitly picked your real mic still need "
            "CABLE Output selected once."
        )
        auto_hint.setObjectName("muted")
        auto_hint.setWordWrap(True)
        windows_layout.addWidget(auto_hint)

        self.default_mic_label = QLabel("")
        self.default_mic_label.setWordWrap(True)
        windows_layout.addWidget(self.default_mic_label)
        self.injection_label = QLabel("")
        self.injection_label.setWordWrap(True)
        windows_layout.addWidget(self.injection_label)

        fix_row = QHBoxLayout()
        self.fix_playback_btn = QPushButton("Fix Windows default playback")
        self.fix_playback_btn.clicked.connect(self._fix_playback)
        fix_row.addWidget(self.fix_playback_btn)
        fix_row.addStretch(1)
        windows_layout.addLayout(fix_row)
        layout.addWidget(windows_box)

        self._update_audio_labels()
        layout.addStretch(1)
        return tab

    def _fill_devices(self, preserve: bool = True) -> None:
        old = {
            "speaker": self.speaker_combo.currentData() if preserve and hasattr(self, "speaker_combo") else None,
            "mic": self.mic_combo.currentData() if preserve and hasattr(self, "mic_combo") else None,
            "cable": self.cable_combo.currentData() if preserve and hasattr(self, "cable_combo") else None,
        }
        outputs = [d for d in self._devices if d.outputs > 0]
        inputs = [d for d in self._devices if d.inputs > 0]
        speaker_default = default_output(self._devices)
        mic_default = default_input(self._devices)
        cable_default = find_cable_output(self._devices)

        self._fill_combo(
            self.speaker_combo,
            outputs,
            False,
            old["speaker"],
            self._settings.get("speaker"),
            speaker_default.index if speaker_default else None,
        )
        self._fill_combo(
            self.mic_combo,
            inputs,
            False,
            old["mic"],
            self._settings.get("mic"),
            mic_default.index if mic_default else None,
        )
        self._fill_combo(
            self.cable_combo,
            outputs,
            True,
            old["cable"],
            self._settings.get("cable"),
            cable_default.index if cable_default else None,
        )

    @staticmethod
    def _fill_combo(combo: QComboBox, rows: list[Device], none: bool, *preferred) -> None:
        combo.blockSignals(True)
        combo.clear()
        if none:
            combo.addItem("(none)", None)
        for device in rows:
            api = hostapi_name(device.hostapi)
            label = f"{device.name}  [{api}]  (#{device.index})" if api else device.label
            combo.addItem(label, device.index)
        chosen = -1
        for wanted in preferred:
            if wanted is None:
                continue
            chosen = combo.findData(wanted)
            if chosen >= 0:
                break
        combo.setCurrentIndex(chosen if chosen >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_devices(self) -> None:
        self._devices = list_devices()
        self._fill_devices(True)
        self._update_audio_labels()

    def _auto_mic_toggled(self, checked: bool) -> None:
        self._default_mic_changed = True
        if not checked:
            self.default_mic_label.setText(
                "Windows default microphone will be left untouched."
            )

    def _update_audio_labels(self) -> None:
        cable = winaudio.cable_output()
        current = winaudio.default_capture()
        if cable is None:
            self.default_mic_label.setText(
                "VB-CABLE was not found. Install it to enable microphone injection."
            )
            self.default_mic_label.setStyleSheet("color:#ffbf69;")
        elif current is not None and winaudio.same_endpoint(current, cable):
            self.default_mic_label.setText(
                "Windows default microphone: CABLE Output (apps can hear SoundPod)."
            )
            self.default_mic_label.setStyleSheet("color:#86f5b0;")
        else:
            name = current.name if current is not None else "unknown"
            self.default_mic_label.setText(f"Windows default microphone: {name}.")
            self.default_mic_label.setStyleSheet("color:#7f8c9c;")
        if self._audio is not None and self._audio.injection_ready:
            self.injection_label.setText("Microphone injection: active")
            self.injection_label.setStyleSheet("color:#86f5b0;")
        else:
            self.injection_label.setText(
                "Microphone injection: inactive. Select a real microphone and CABLE Input."
            )
            self.injection_label.setStyleSheet("color:#ffbf69;")

    def _fix_playback(self) -> None:
        target = winaudio.physical_output()
        if target is None:
            QMessageBox.warning(
                self,
                "No playback device",
                "Windows reports no physical playback device. Connect headphones or speakers first.",
            )
            return
        try:
            how = winaudio.set_default_compat(target.id)
        except OSError as exc:
            QMessageBox.warning(self, "Could not change the default device", str(exc))
            return
        QMessageBox.information(
            self,
            "Default playback restored",
            f"Windows now plays through {target.name}.\n\n{how}",
        )

    # ---------------------------------------------------------------- hotkeys

    def _hotkeys_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.hotkeys_check = QCheckBox("Enable global hotkeys while SoundPod runs")
        self.hotkeys_check.setChecked(bool(self._settings.get("hotkeys_enabled", True)))
        layout.addWidget(self.hotkeys_check)
        summary = QLabel(
            self._hotkey_summary
            or "Hotkeys are registered with Windows. Another app can own a key; "
            "the main status bar shows failures."
        )
        summary.setObjectName("muted")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.hotkey_table = QTableWidget(0, 2)
        self.hotkey_table.setHorizontalHeaderLabels(["Sound", "Hotkey"])
        self.hotkey_table.verticalHeader().setVisible(False)
        self.hotkey_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.hotkey_table.setSelectionMode(QTableWidget.SingleSelection)
        self.hotkey_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hotkey_table.setAlternatingRowColors(True)
        self.hotkey_table.setShowGrid(False)
        header = self.hotkey_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.hotkey_table.setColumnWidth(1, 190)
        self.hotkey_table.doubleClicked.connect(lambda _index: self._change_hotkey())
        layout.addWidget(self.hotkey_table, 1)

        buttons = QHBoxLayout()
        change_btn = QPushButton("Set hotkey…")
        change_btn.clicked.connect(self._change_hotkey)
        clear_btn = QPushButton("Clear hotkey")
        clear_btn.clicked.connect(self._clear_hotkey)
        buttons.addWidget(change_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch(1)
        note = QLabel("Hotkey changes are applied when you press OK or Apply.")
        note.setObjectName("muted")
        buttons.addWidget(note)
        layout.addLayout(buttons)

        self._reload_hotkey_table()
        return tab

    def _reload_hotkey_table(self) -> None:
        if self._library is None:
            self.hotkey_table.setRowCount(0)
            return
        sounds = sorted(self._library.sounds, key=lambda sound: sound.title.lower())
        self.hotkey_table.setRowCount(len(sounds))
        for row, sound in enumerate(sounds):
            title = QTableWidgetItem(sound.title)
            title.setData(Qt.UserRole, sound.id)
            self.hotkey_table.setItem(row, 0, title)
            value = self._hotkey_changes.get(sound.id, sound.hotkey)
            self.hotkey_table.setItem(row, 1, QTableWidgetItem(value or "—"))

    def _selected_hotkey_sound(self):
        if self._library is None:
            return None
        row = self.hotkey_table.currentRow()
        if row < 0:
            return None
        item = self.hotkey_table.item(row, 0)
        if item is None:
            return None
        return self._library.by_id(item.data(Qt.UserRole) or "")

    def _conflicting_hotkey(self, value: str, ignore_id: str):
        needle = value.strip().lower()
        if not needle or self._library is None:
            return None
        for sound in self._library.sounds:
            if sound.id == ignore_id:
                continue
            current = self._hotkey_changes.get(sound.id, sound.hotkey)
            if current.strip().lower() == needle:
                return sound
        return None

    def _change_hotkey(self) -> None:
        sound = self._selected_hotkey_sound()
        if sound is None:
            QMessageBox.information(self, "Set hotkey", "Select a sound first.")
            return
        current = self._hotkey_changes.get(sound.id, sound.hotkey)
        dialog = HotkeyDialog(current, self)
        if dialog.exec() != QDialog.Accepted:
            return
        value = dialog.value().strip()
        if value:
            other = self._conflicting_hotkey(value, sound.id)
            if other is not None:
                QMessageBox.warning(
                    self,
                    "Hotkey in use",
                    f"{value} is already used by “{other.title}”.",
                )
                return
        self._hotkey_changes[sound.id] = value
        self._reload_hotkey_table()

    def _clear_hotkey(self) -> None:
        sound = self._selected_hotkey_sound()
        if sound is None:
            return
        self._hotkey_changes[sound.id] = ""
        self._reload_hotkey_table()

    # -------------------------------------------------------------- interface

    def _interface_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        window_box = QGroupBox("Window")
        window_layout = QVBoxLayout(window_box)
        self.top_check = QCheckBox("Always on top")
        self.top_check.setChecked(bool(self._settings.get("always_on_top", False)))
        self.minimize_tray_check = QCheckBox("Minimize to the tray instead of closing")
        self.minimize_tray_check.setChecked(bool(self._settings.get("minimize_to_tray", False)))
        self.start_minimized_check = QCheckBox("Start minimized to the tray")
        self.start_minimized_check.setChecked(bool(self._settings.get("start_minimized", False)))
        for check in (
            self.top_check,
            self.minimize_tray_check,
            self.start_minimized_check,
        ):
            window_layout.addWidget(check)
        self.notify_check = QCheckBox("Show a tray notification when a sound starts")
        self.notify_check.setChecked(bool(self._settings.get("show_notifications", True)))
        window_layout.addWidget(self.notify_check)
        layout.addWidget(window_box)

        startup_box = QGroupBox("Windows startup")
        startup_layout = QVBoxLayout(startup_box)
        self.startup_check = QCheckBox("Start SoundPod when I sign in to Windows")
        self.startup_check.setChecked(bool(self._settings.get("start_with_windows", False)))
        startup_layout.addWidget(self.startup_check)
        startup_hint = QLabel(
            "The startup entry points at the current SoundPod location. Move the "
            "folder and toggle this again if you relocate the app."
        )
        startup_hint.setObjectName("muted")
        startup_hint.setWordWrap(True)
        startup_layout.addWidget(startup_hint)
        layout.addWidget(startup_box)

        layout.addStretch(1)
        return tab

    # --------------------------------------------------------------- advanced

    def _advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        record_box = QGroupBox("Recordings")
        record_layout = QVBoxLayout(record_box)
        row = QHBoxLayout()
        self.record_dir_edit = QLineEdit(
            str(
                self._settings.get("record_dir")
                or (Path(os.environ.get("APPDATA", Path.home())) / "SoundPod" / "recordings")
            )
        )
        self.record_dir_edit.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_record_dir)
        row.addWidget(self.record_dir_edit, 1)
        row.addWidget(browse)
        record_layout.addLayout(row)
        record_hint = QLabel(
            "New recordings are saved here and added to the current category."
        )
        record_hint.setObjectName("muted")
        record_layout.addWidget(record_hint)
        layout.addWidget(record_box)

        data_box = QGroupBox("Data and maintenance")
        data_layout = QVBoxLayout(data_box)
        data_path = Path(os.environ.get("APPDATA", Path.home())) / "SoundPod"
        path_label = QLabel(
            f"Library and settings: {data_path}\n"
            f"Decode cache: {Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'SoundPod' / 'cache'}"
        )
        path_label.setObjectName("muted")
        path_label.setWordWrap(True)
        data_layout.addWidget(path_label)
        open_btn = QPushButton("Open data folder")
        open_btn.clicked.connect(lambda: self._open_folder(data_path))
        data_layout.addWidget(open_btn)
        layout.addWidget(data_box)

        about_box = QGroupBox("About")
        about_layout = QVBoxLayout(about_box)
        about = QLabel(
            "SoundPod is a clean-room soundboard. Audio goes through VB-CABLE; "
            "no Soundpad code, driver, icon or cloud service is used. Local only: "
            "no account, telemetry or uploads."
        )
        about.setObjectName("muted")
        about.setWordWrap(True)
        about_layout.addWidget(about)
        layout.addWidget(about_box)

        layout.addStretch(1)
        return tab

    def _browse_record_dir(self) -> None:
        start = self.record_dir_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Recordings folder", start)
        if chosen:
            self.record_dir_edit.setText(chosen)

    def _open_folder(self, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]

    # ----------------------------------------------------------------- values

    def values(self) -> dict:
        return {
            "speaker": self.speaker_combo.currentData(),
            "mic": self.mic_combo.currentData(),
            "cable": self.cable_combo.currentData(),
            "mode": self.mode_combo.currentData() or "both",
            "volume": self.volume_slider.value() / 100.0,
            "normalize": self.normalize_check.isChecked(),
            "block_voice": self.block_check.isChecked(),
            "auto_default_mic": self.auto_mic_check.isChecked(),
            "hotkeys_enabled": self.hotkeys_check.isChecked(),
            "hotkey_changes": dict(self._hotkey_changes),
            "always_on_top": self.top_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
            "minimize_to_tray": self.minimize_tray_check.isChecked(),
            "show_notifications": self.notify_check.isChecked(),
            "start_with_windows": self.startup_check.isChecked(),
            "record_dir": self.record_dir_edit.text().strip(),
        }

    def _apply(self) -> None:
        values = self.values()
        if callable(self._on_apply):
            self._on_apply(values)
        self._settings.update(
            {key: value for key, value in values.items() if key != "hotkey_changes"}
        )
        self._default_mic_changed = False
        if self._library is not None:
            self._hotkey_changes.clear()
            self._reload_hotkey_table()
        self._update_audio_labels()
