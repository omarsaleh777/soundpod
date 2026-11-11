"""SoundPod desktop UI: Soundpad-style soundboard clone."""

from __future__ import annotations

import json
import os
import shutil
import sys
import winreg
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .audio import (
    AudioEngine,
    Device,
    default_input,
    default_output,
    find_cable_output,
    hostapi_name,
    is_virtual_output,
    list_devices,
    windows_default_output,
)
from .autokeys import AutoKeys
from .editor import SoundEditor
from .hotkeys import HotkeyManager
from .library import AUDIO_FILTER, Library, Sound, fmt_duration
from .preferences import HotkeyDialog, PreferencesDialog
from .recorder import Recorder, record_helper_available
from . import winaudio
from .remote import RemoteServer
from .tts import TTS

APP_NAME = "SoundPod"
VERSION = "1.0.2"

STYLE = """
QWidget {
    background: #0f1319;
    color: #d7dde5;
    font-family: "Segoe UI";
    font-size: 9.5pt;
}
QMainWindow, QDialog { background: #0f1319; }
QMenuBar { background: #0b0e13; border-bottom: 1px solid #1b222c; padding: 2px; }
QMenuBar::item { background: transparent; padding: 5px 9px; border-radius: 3px; }
QMenuBar::item:selected { background: #1b2531; }
QMenu { background: #141b24; border: 1px solid #263140; padding: 4px; }
QMenu::item { padding: 6px 26px 6px 22px; border-radius: 3px; }
QMenu::item:selected { background: #1d3b2b; color: #86f5b0; }
QMenu::separator { height: 1px; background: #263140; margin: 5px 8px; }
QToolButton, QPushButton {
    background: #1a222d;
    border: 1px solid #2a3645;
    border-radius: 5px;
    padding: 6px 11px;
}
QToolButton:hover, QPushButton:hover { background: #222e3c; border-color: #3c4c60; }
QToolButton:pressed, QPushButton:pressed { background: #131a23; }
QToolButton:checked, QPushButton:checked {
    background: #173a2a; border-color: #2ecc71; color: #a9ffc6;
}
QPushButton#accent { background: #1f9d55; border-color: #2ecc71; color: white; font-weight: 600; }
QPushButton#accent:hover { background: #24b863; }
QPushButton#danger { color: #ff9b9b; }
QWidget#controlStrip { background:#0d1218; border-bottom: 2px solid #1f9d55; }
QLabel#badgeOn {
    color: #86f5b0; font-weight: 700; font-size: 10pt;
    background: #173a2a; border: 1px solid #2ecc71; border-radius: 6px;
    padding: 4px 12px;
}
QLabel#badgeOff {
    color: #ffbf69; font-weight: 700; font-size: 10pt;
    background: #2a1a12; border: 1px solid #ff9b44; border-radius: 6px;
    padding: 4px 12px;
}

QGroupBox {
    border: 1px solid #263140; border-radius: 6px; margin-top: 11px; padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 10px; padding: 0 4px; color: #8d9bad; font-weight: 600;
}

QPushButton { font-size: 9.5pt; }
QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {
    background: #121821;
    border: 1px solid #2a3543;
    border-radius: 4px;
    padding: 5px;
    selection-background-color: #1f9d55;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #2ecc71; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: #141b24; border: 1px solid #2a3543; selection-background-color: #1d3b2b; }
QTableWidget {
    background: #0f1319;
    alternate-background-color: #121821;
    gridline-color: #1a222d;
    border: 1px solid #1a222d;
    selection-background-color: #173a2a;
    selection-color: #a9ffc6;
}
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background: #151c25;
    color: #8d9bad;
    border: none;
    border-right: 1px solid #1e2732;
    border-bottom: 1px solid #263140;
    padding: 6px;
    font-weight: 600;
}
QListWidget { background: #0c1015; border: none; outline: none; }
QListWidget::item { padding: 8px 10px; border-left: 3px solid transparent; }
QListWidget::item:hover { background: #131a23; }
QListWidget::item:selected { background: #14291e; color: #86f5b0; border-left: 3px solid #2ecc71; }
QTabWidget::pane { border: none; border-top: 1px solid #1c2430; }
QTabBar::tab { background: #0c1015; color: #8d9bad; padding: 7px 15px; border: none; }
QTabBar::tab:selected { color: #86f5b0; background: #121821; border-bottom: 2px solid #2ecc71; }
QTabBar::tab:hover { color: #d7dde5; }
QSlider::groove:horizontal { height: 4px; background: #26313f; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #2ecc71; border-radius: 2px; }
QSlider::handle:horizontal { background: #2ecc71; width: 12px; margin: -4px 0; border-radius: 6px; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #3a4759; border-radius: 3px; background: #121821; }
QCheckBox::indicator:checked { background: #2ecc71; border-color: #2ecc71; }
QScrollBar:vertical { background: #0c1015; width: 10px; }
QScrollBar::handle:vertical { background: #2a3645; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #0b0e13; color: #7f8c9c; border-top: 1px solid #1b222c; }
QSplitter::handle { background: #1b222c; width: 1px; }
QSplitter::handle:vertical { height: 6px; }
QSplitter::handle:hover { background: #2ecc71; }
QFrame#panel { background: #0f1319; }
QLabel#muted { color: #7f8c9c; }
QLabel#accent { color: #86f5b0; font-weight: 600; }
QLabel#warn { color: #ffbf69; }
QLabel#title { font-size: 15pt; font-weight: 700; color: #f1f5f9; }
"""


def make_icon(size: int = 64) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#1f9d55"))
    painter.setPen(QColor("#7ef0a8"))
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 14, 14)
    painter.setBrush(QColor("#eafff1"))
    painter.setPen(Qt.NoPen)
    triangle = [
        (size * 0.38, size * 0.27),
        (size * 0.38, size * 0.73),
        (size * 0.74, size * 0.50),
    ]
    from PySide6.QtGui import QPolygonF
    from PySide6.QtCore import QPointF

    painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in triangle]))
    painter.end()
    return QIcon(pix)


class TaskThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self.fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    log_message = Signal(str)
    play_requested = Signal(str)
    stop_requested = Signal()
    recording_done = Signal(object)
    tts_done = Signal(object)
    tts_save_done = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setWindowIcon(make_icon())
        self.resize(1180, 760)
        self.setMinimumSize(980, 600)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)

        appdata = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
        local = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
        appdata.mkdir(parents=True, exist_ok=True)
        local.mkdir(parents=True, exist_ok=True)
        self.settings_path = appdata / "settings.json"
        self.library = Library(appdata / "library.json")
        self.library.load()
        self.audio = AudioEngine(local / "cache")
        self.tts = TTS(local / "tts")
        self.recorder = Recorder(appdata / "recordings")
        self.autokeys = AutoKeys()
        self.remote = RemoteServer(
            sounds=self._remote_sounds,
            play=lambda sound_id: self.play_requested.emit(sound_id),
            stop=lambda: self.stop_requested.emit(),
            port=8765,
            bind="0.0.0.0",
        )
        self._remote_action: QAction | None = None
        self._remote_url = ""
        self.hotkeys = HotkeyManager(self.play_requested.emit, QApplication.instance())
        self.hotkey_errors: list[str] = []
        self._tasks: list[TaskThread] = []
        self._callbacks: dict[TaskThread, tuple] = {}
        self._audio_started = False
        self._current_category = "All Sounds"
        self._tray: QSystemTrayIcon | None = None
        self._settings = self._load_settings()
        self._loading = True
        self._quitting = False
        self._auto_mic_applied = False
        self._restore_capture_id: str | None = None
        self._last_default_mic_note = ""

        self.audio.set_error_handler(self.log_message.emit)
        self.log_message.connect(self._append_log)
        self.play_requested.connect(self._on_hotkey, Qt.QueuedConnection)
        self.stop_requested.connect(self._stop_all, Qt.QueuedConnection)
        self.recording_done.connect(self._on_recording_done)
        self.tts_done.connect(self._on_tts_done)
        self.tts_save_done.connect(self._on_tts_save_done)

        self._build_ui()
        self._build_menus()
        self._build_tray()
        self._apply_settings_to_widgets()
        self._loading = False
        self._refresh_categories()
        self._refresh_table()
        self._register_hotkeys()
        self._load_voices()
        self._append_log(f"{APP_NAME} {VERSION} ready.")
        if not self.hotkeys.available:
            self._append_log(
                "Global hotkeys unavailable: native event filter could not be installed."
            )
        QTimer.singleShot(80, self._start_audio)

    # ---------------------------------------------------------------- settings

    def _load_settings(self) -> dict:
        defaults = {
            "speaker": None,
            "mic": None,
            "cable": None,
            "mode": "both",
            "volume": 0.75,
            "normalize": True,
            "block_voice": False,
            "category": "All Sounds",
            "tts_voice": "",
            "hotkeys_enabled": True,
            "start_with_windows": False,
            "auto_default_mic": True,
            "always_on_top": False,
            "start_minimized": False,
            "minimize_to_tray": False,
            "show_notifications": True,
            "record_dir": "",
        }
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            defaults.update({k: v for k, v in data.items() if k in defaults})
        except Exception:
            pass
        return defaults

    def _save_settings(self) -> None:
        if getattr(self, "_loading", False):
            return
        self._settings.update(
            {
                "speaker": self.speaker_combo.currentData() if hasattr(self, "speaker_combo") else None,
                "mic": self.mic_combo.currentData() if hasattr(self, "mic_combo") else None,
                "cable": self.cable_combo.currentData() if hasattr(self, "cable_combo") else None,
                "mode": self.mode_combo.currentData() if hasattr(self, "mode_combo") else "both",
                "volume": self.volume_slider.value() / 100.0,
                "normalize": self.normalize_check.isChecked() if hasattr(self, "normalize_check") else True,
                "block_voice": self.block_check.isChecked() if hasattr(self, "block_check") else False,
                "category": self._current_category,
                "tts_voice": self.voice_combo.currentData() if hasattr(self, "voice_combo") else "",
                "hotkeys_enabled": self.hotkeys_check.isChecked() if hasattr(self, "hotkeys_check") else True,
                "start_with_windows": self.startup_check.isChecked() if hasattr(self, "startup_check") else False,
                "always_on_top": self.top_check.isChecked() if hasattr(self, "top_check") else False,
                "start_minimized": bool(self._settings.get("start_minimized", False)),
                "minimize_to_tray": bool(self._settings.get("minimize_to_tray", False)),
                "show_notifications": bool(self._settings.get("show_notifications", True)),
                "auto_default_mic": bool(self._settings.get("auto_default_mic", True)),
                "record_dir": str(self.recorder.output_dir),
            }
        )
        try:
            self.settings_path.write_text(
                json.dumps(self._settings, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            self._append_log(f"Could not save settings: {exc}")

    # -------------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet("background:#0b0e13;border-bottom:1px solid #1b222c;")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(10, 7, 10, 7)
        bar.setSpacing(6)

        self.play_btn = QPushButton("▶  Play")
        self.play_btn.setObjectName("accent")
        self.play_btn.clicked.connect(self._play_selected)
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.clicked.connect(self._stop_all)
        self.add_btn = QPushButton("+  Add")
        self.add_btn.clicked.connect(self._add_files)
        self.remove_btn = QPushButton("−  Remove")
        self.remove_btn.setObjectName("danger")
        self.remove_btn.clicked.connect(self._remove_selected)

        for button in (self.play_btn, self.stop_btn, self.add_btn, self.remove_btn):
            bar.addWidget(button)

        bar.addSpacing(12)
        mode_label = QLabel("Play to")
        mode_label.setObjectName("muted")
        bar.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Speakers + mic", "both")
        self.mode_combo.addItem("Speakers only", "speakers")
        self.mode_combo.addItem("Microphone only", "microphone")
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        bar.addWidget(self.mode_combo)

        bar.addSpacing(8)
        vol_icon = QLabel("Volume")
        vol_icon.setObjectName("muted")
        bar.addWidget(vol_icon)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(130)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        bar.addWidget(self.volume_slider)
        self.volume_value = QLabel("75%")
        self.volume_value.setObjectName("muted")
        self.volume_value.setFixedWidth(38)
        bar.addWidget(self.volume_value)

        bar.addStretch(1)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search sounds…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(250)
        self.search_edit.textChanged.connect(self._refresh_table)
        bar.addWidget(self.search_edit)
        root.addWidget(toolbar)

        # ------------------------------------------------------------------ control strip
        strip = QWidget()
        strip.setObjectName("controlStrip")
        strip.setFixedHeight(72)
        strip.setStyleSheet(
            "QWidget#controlStrip { background:#0d1218; border-bottom: 2px solid #1f9d55; }"
        )
        strip_row = QHBoxLayout(strip)
        strip_row.setContentsMargins(14, 8, 14, 8)
        strip_row.setSpacing(10)

        strip_title = QLabel("SoundPod")
        strip_title.setObjectName("title")
        strip_row.addWidget(strip_title)

        strip_row.addSpacing(18)

        self.block_strip_btn = QPushButton("BLOCK VOICE: OFF")
        self.block_strip_btn.setCheckable(True)
        self.block_strip_btn.setMinimumWidth(150)
        self.block_strip_btn.setMinimumHeight(36)
        self.block_strip_btn.setToolTip(
            "Replace your microphone with the sound while it plays. "
            "Same switch as Devices > Block voice."
        )
        self.block_strip_btn.toggled.connect(self._strip_block)
        strip_row.addWidget(self.block_strip_btn)

        self.normalize_strip_btn = QPushButton("NORMALIZE: OFF")
        self.normalize_strip_btn.setCheckable(True)
        self.normalize_strip_btn.setMinimumWidth(150)
        self.normalize_strip_btn.setMinimumHeight(36)
        self.normalize_strip_btn.setToolTip(
            "Even out the loudness of every sound before it is played."
        )
        self.normalize_strip_btn.toggled.connect(self._strip_normalize)
        strip_row.addWidget(self.normalize_strip_btn)

        strip_row.addSpacing(14)

        self.injection_badge = QLabel("MIC INJECTION: STARTING…")
        self.injection_badge.setMinimumHeight(36)
        self.injection_badge.setObjectName("badgeOff")
        self.injection_badge.setAlignment(Qt.AlignCenter)
        self.injection_badge.setToolTip(
            "ON means SoundPod is mixing your microphone and sounds into VB-CABLE."
        )
        strip_row.addWidget(self.injection_badge)

        strip_row.addSpacing(14)

        self.default_mic_badge = QLabel("WINDOWS MIC: CHECKING…")
        self.default_mic_badge.setMinimumHeight(36)
        self.default_mic_badge.setObjectName("badgeOff")
        self.default_mic_badge.setAlignment(Qt.AlignCenter)
        self.default_mic_badge.setToolTip(
            "Shows which microphone Windows apps use by default while SoundPod runs."
        )
        strip_row.addWidget(self.default_mic_badge)

        strip_row.addStretch(1)

        self.prefs_btn = QPushButton("⚙  PREFERENCES")
        self.prefs_btn.setMinimumHeight(36)
        self.prefs_btn.setMinimumWidth(150)
        self.prefs_btn.setToolTip("Open the full SoundPod preferences (Ctrl+,)")
        self.prefs_btn.clicked.connect(self._open_preferences)
        strip_row.addWidget(self.prefs_btn)

        root.addWidget(strip)

        self.setup_banner = QWidget()
        self.setup_banner.setObjectName("setupBanner")
        self.setup_banner.setStyleSheet(
            "QWidget#setupBanner { background:#2a1a12; border-bottom:1px solid #ff9b44; }"
            "QLabel#setupText { color:#ffcf9e; font-weight:600; }"
        )
        banner_row = QHBoxLayout(self.setup_banner)
        banner_row.setContentsMargins(14, 7, 14, 7)
        banner_row.setSpacing(10)
        self.setup_text = QLabel(
            "Mic injection is OFF — voice chat will not hear your sounds. "
            "Choose your real microphone and CABLE Input."
        )
        self.setup_text.setObjectName("setupText")
        self.setup_text.setWordWrap(True)
        banner_row.addWidget(self.setup_text, 1)
        setup_btn = QPushButton("Open audio setup")
        setup_btn.setObjectName("accent")
        setup_btn.clicked.connect(self._open_preferences)
        banner_row.addWidget(setup_btn)
        self.setup_banner.hide()
        root.addWidget(self.setup_banner)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_head = QWidget()
        left_head.setStyleSheet("background:#0c1015;border-bottom:1px solid #1b222c;")
        lh = QHBoxLayout(left_head)
        lh.setContentsMargins(10, 8, 6, 8)
        cat_title = QLabel("Categories")
        cat_title.setObjectName("muted")
        lh.addWidget(cat_title)
        lh.addStretch(1)
        add_cat = QToolButton()
        add_cat.setText("+")
        add_cat.setToolTip("Add category")
        add_cat.clicked.connect(self._add_category)
        del_cat = QToolButton()
        del_cat.setText("−")
        del_cat.setToolTip("Remove category")
        del_cat.clicked.connect(self._remove_category)
        lh.addWidget(add_cat)
        lh.addWidget(del_cat)
        left_layout.addWidget(left_head)

        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self._category_changed)
        left_layout.addWidget(self.category_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Title", "Hotkey", "Duration", "Volume", "Category"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.doubleClicked.connect(lambda _i: self._play_selected())
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        upper = QWidget()
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(0)
        upper_layout.addWidget(self.table, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(58)
        scroll.setStyleSheet("QScrollArea{border:none;background:#0b0e13;border-top:1px solid #1b222c;}")
        self.hotbar_widget = QWidget()
        self.hotbar_widget.setStyleSheet("background:#0b0e13;")
        self.hotbar_layout = QHBoxLayout(self.hotbar_widget)
        self.hotbar_layout.setContentsMargins(8, 6, 8, 6)
        self.hotbar_layout.setSpacing(5)
        self.hotbar_layout.addStretch(1)
        scroll.setWidget(self.hotbar_widget)
        upper_layout.addWidget(scroll)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tts_tab(), "Text to speech")
        self.tabs.addTab(self._build_recorder_tab(), "Recorder")
        self.tabs.addTab(self._build_settings_tab(), "Devices")
        self.tabs.addTab(self._build_log_tab(), "Log")
        self.tabs.setMinimumHeight(300)
        self.tabs.setToolTip("Drag the divider above to make this panel taller or shorter.")

        self.bottom_splitter = QSplitter(Qt.Vertical)
        self.bottom_splitter.addWidget(upper)
        self.bottom_splitter.addWidget(self.tabs)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.setStretchFactor(0, 1)
        self.bottom_splitter.setStretchFactor(1, 0)
        self.bottom_splitter.setSizes([420, 320])
        right_layout.addWidget(self.bottom_splitter, 1)
        splitter.addWidget(right)
        splitter.setSizes([215, 865])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self.device_status = QLabel("Starting audio…")
        self.device_status.setObjectName("muted")
        self.statusBar().addPermanentWidget(self.device_status)
        self.hotkey_status = QLabel("Hotkeys: starting")
        self.hotkey_status.setObjectName("muted")
        self.statusBar().addPermanentWidget(self.hotkey_status)

        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._add_files)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.search_edit.setFocus)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._stop_all)
        QShortcut(QKeySequence("Delete"), self.table).activated.connect(self._remove_selected)
        QShortcut(QKeySequence("Return"), self.table).activated.connect(self._play_selected)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._toggle_recording)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._edit_sound)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self._open_preferences)

    def _build_tts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(12)

        left = QVBoxLayout()
        self.tts_text = QPlainTextEdit()
        self.tts_text.setPlaceholderText("Type text to speak through your microphone…")
        self.tts_text.setFixedHeight(105)
        left.addWidget(self.tts_text)
        row = QHBoxLayout()
        self.tts_both_btn = QPushButton("Speak to both")
        self.tts_both_btn.setObjectName("accent")
        self.tts_both_btn.clicked.connect(lambda: self._speak("both"))
        self.tts_spk_btn = QPushButton("Speakers")
        self.tts_spk_btn.clicked.connect(lambda: self._speak("speakers"))
        self.tts_mic_btn = QPushButton("Microphone")
        self.tts_mic_btn.clicked.connect(lambda: self._speak("microphone"))
        self.tts_save_btn = QPushButton("Save as sound")
        self.tts_save_btn.clicked.connect(lambda: self._speak(self.mode_combo.currentData(), save=True))
        for button in (self.tts_both_btn, self.tts_spk_btn, self.tts_mic_btn, self.tts_save_btn):
            row.addWidget(button)
        row.addStretch(1)
        left.addLayout(row)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(5)
        voice_row = QHBoxLayout()
        voice_label = QLabel("Voice")
        voice_label.setObjectName("muted")
        voice_row.addWidget(voice_label)
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(220)
        voice_row.addWidget(self.voice_combo, 1)
        right.addLayout(voice_row)

        self.rate_slider, rate_value = self._slider_row(right, "Speed", -10, 10, 0)
        self.pitch_slider, pitch_value = self._slider_row(right, "Pitch", -10, 10, 0)
        self._rate_value = rate_value
        self._pitch_value = pitch_value
        for slider in (self.rate_slider, self.pitch_slider):
            slider.valueChanged.connect(self._tts_slider_changed)
        right.addStretch(1)
        layout.addLayout(right, 0)

        self.tts_status = QLabel("Local Windows voices. No cloud.")
        self.tts_status.setObjectName("muted")
        right.addWidget(self.tts_status)
        return tab

    def _slider_row(self, parent_layout, label: str, low: int, high: int, value: int):
        row = QHBoxLayout()
        text = QLabel(label)
        text.setObjectName("muted")
        text.setFixedWidth(48)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        slider.setFixedWidth(120)
        value_label = QLabel(str(value))
        value_label.setObjectName("muted")
        value_label.setFixedWidth(28)
        row.addWidget(text)
        row.addWidget(slider)
        row.addWidget(value_label)
        row.addStretch(1)
        parent_layout.addLayout(row)
        return slider, value_label

    def _build_recorder_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.record_source = QComboBox()
        self.record_source.addItem("Microphone", "microphone")
        self.record_source.addItem("System audio (what you hear)", "system")
        layout.addWidget(QLabel("Source"))
        layout.addWidget(self.record_source)

        self.record_btn = QPushButton("●  Start recording")
        self.record_btn.setObjectName("accent")
        self.record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_btn)
        self.record_time = QLabel("0:00")
        self.record_time.setObjectName("title")
        layout.addWidget(self.record_time)
        self.record_hint = QLabel("Recordings are saved to the library.")
        self.record_hint.setObjectName("muted")
        layout.addWidget(self.record_hint)
        if getattr(sys, "frozen", False) and not record_helper_available():
            self.record_hint.setText(
                "Recording is unavailable: SoundPodRecorder.exe is missing. "
                "Extract the whole zip so it stays next to SoundPod.exe."
            )
            self.record_hint.setStyleSheet("color:#ffbf69;")
        layout.addStretch(1)
        self._record_timer = QTimer(self)
        self._record_timer.setInterval(250)
        self._record_timer.timeout.connect(self._tick_recording)
        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        outer = QHBoxLayout(tab)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(16)

        grid = QVBoxLayout()
        grid.setSpacing(5)
        self.speaker_combo = self._device_combo()
        self.mic_combo = self._device_combo()
        self.cable_combo = self._device_combo()
        for label, combo in (
            ("Speakers", self.speaker_combo),
            ("Microphone", self.mic_combo),
            ("Cable input for mic injection", self.cable_combo),
        ):
            row = QHBoxLayout()
            text = QLabel(label)
            text.setObjectName("muted")
            text.setFixedWidth(190)
            row.addWidget(text)
            row.addWidget(combo, 1)
            grid.addLayout(row)

        buttons = QHBoxLayout()
        apply_btn = QPushButton("Apply devices")
        apply_btn.setObjectName("accent")
        apply_btn.clicked.connect(self._apply_devices)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._populate_devices)
        cable_btn = QPushButton("Get VB-CABLE")
        cable_btn.clicked.connect(
            lambda: self._open_url("https://vb-audio.com/Cable/")
        )
        buttons.addWidget(apply_btn)
        buttons.addWidget(refresh_btn)
        buttons.addWidget(cable_btn)
        buttons.addStretch(1)
        grid.addLayout(buttons)
        outer.addLayout(grid, 1)

        options_widget = QWidget()
        options = QVBoxLayout(options_widget)
        options.setContentsMargins(0, 0, 6, 0)
        options.setSpacing(4)
        self.block_check = QCheckBox("Block voice while playing (replace mic)")
        self.block_check.toggled.connect(self._block_changed)
        self.normalize_check = QCheckBox("Normalize volume on playback")
        self.normalize_check.toggled.connect(self._normalize_changed)
        self.top_check = QCheckBox("Always on top")
        self.top_check.toggled.connect(self._always_on_top)
        options.addWidget(self.block_check)
        options.addWidget(self.normalize_check)
        options.addWidget(self.top_check)
        self.hotkeys_check = QCheckBox("Global hotkeys enabled")
        self.hotkeys_check.toggled.connect(self._toggle_hotkeys)
        options.addWidget(self.hotkeys_check)
        self.startup_check = QCheckBox("Start SoundPod with Windows")
        self.startup_check.toggled.connect(self._toggle_startup)
        options.addWidget(self.startup_check)
        self.quality_hint = QLabel("")
        self.quality_hint.setWordWrap(True)
        self.quality_hint.setObjectName("muted")
        options.addWidget(self.quality_hint)
        self.cable_warning = QLabel("")
        self.cable_warning.setWordWrap(True)
        self.cable_warning.setObjectName("warn")
        options.addWidget(self.cable_warning)
        self.windows_warning = QLabel("")
        self.windows_warning.setWordWrap(True)
        self.windows_warning.setObjectName("warn")
        self.windows_warning.hide()
        options.addWidget(self.windows_warning)
        self.fix_default_btn = QPushButton("Fix Windows default playback")
        self.fix_default_btn.clicked.connect(self._fix_windows_default)
        self.fix_default_btn.hide()
        options.addWidget(self.fix_default_btn)
        options.addStretch(1)

        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_scroll.setFrameShape(QFrame.NoFrame)
        options_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        options_scroll.setMinimumWidth(390)
        options_scroll.setWidget(options_widget)
        outer.addWidget(options_scroll, 0)
        return tab

    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        layout.addWidget(self.log)
        return tab

    def _device_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(330)
        return combo

    def _build_menus(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        self._action(file_menu, "&Add sound files…", "Ctrl+O", self._add_files)
        self._action(file_menu, "&Import Soundpad list…", "", self._import_spl)
        self._action(file_menu, "Save sound &list", "Ctrl+S", self._save_library)
        self._action(file_menu, "E&xport Soundpad list…", "", self._export_spl)
        file_menu.addSeparator()
        self._action(file_menu, "&Preferences…", "Ctrl+,", self._open_preferences)
        file_menu.addSeparator()
        self._action(file_menu, "E&xit", "Alt+F4", self._request_quit)

        edit_menu = menu.addMenu("&Edit")
        self._action(edit_menu, "&Remove sound", "Del", self._remove_selected)
        self._action(edit_menu, "Set &hotkey…", "Ctrl+H", self._set_hotkey)
        self._action(edit_menu, "Edit sound (&cut, normalize)…", "Ctrl+E", self._edit_sound)
        self._action(edit_menu, "Set sound &volume…", "", self._set_sound_volume)
        self._action(edit_menu, "Set &Auto Keys…", "", self._set_auto_keys)
        self._action(edit_menu, "&Reveal in Explorer", "", self._reveal_selected)
        edit_menu.addSeparator()
        self._action(edit_menu, "Add &category…", "", self._add_category)
        self._action(edit_menu, "Remove category", "", self._remove_category)

        play_menu = menu.addMenu("&Playback")
        self._action(play_menu, "&Play selected", "Return", self._play_selected)
        self._action(play_menu, "&Stop", "Esc", self._stop_all)
        play_menu.addSeparator()
        self._action(play_menu, "Play to &speakers", "", lambda: self._set_mode("speakers"))
        self._action(play_menu, "Play to &microphone", "", lambda: self._set_mode("microphone"))
        self._action(play_menu, "Play to &both", "", lambda: self._set_mode("both"))
        play_menu.addSeparator()
        self._action(play_menu, "&Block voice", "", self._toggle_block, checkable=True)

        sound_menu = menu.addMenu("&Sound")
        self._action(sound_menu, "&Record", "Ctrl+R", self._toggle_recording)
        self._action(sound_menu, "&Text to speech", "Ctrl+T", lambda: self.tabs.setCurrentIndex(0))
        self._action(sound_menu, "Edit sound…", "", self._edit_sound)

        hotkey_menu = menu.addMenu("&Hotkeys")
        self._action(hotkey_menu, "&Status…", "", self._show_hotkey_status)
        self._action(hotkey_menu, "&Re-register all", "", self._register_hotkeys)
        self._action(hotkey_menu, "Set &hotkey…", "", self._set_hotkey)

        window_menu = menu.addMenu("&Window")
        self._action(window_menu, "Always on &top", "", self._toggle_top, checkable=True)
        self._action(window_menu, "Minimize to &tray", "", self._minimize_to_tray)
        window_menu.addSeparator()
        self._remote_action = self._action(
            window_menu, "Phone &remote (web)", "", self._toggle_remote, checkable=True
        )

        help_menu = menu.addMenu("&Help")
        self._action(help_menu, "&About", "", self._about)

    def _action(self, menu: QMenu, text: str, shortcut: str, callback, checkable: bool = False) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(make_icon(), self)
        menu = QMenu()
        menu.addAction("Show SoundPod", self.showNormal)
        menu.addAction("Play selected", self._play_selected)
        menu.addAction("Stop", self._stop_all)
        menu.addSeparator()
        menu.addAction("Preferences…", self._open_preferences)
        menu.addSeparator()
        menu.addAction("Quit SoundPod", self._request_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    # ------------------------------------------------------------ library view

    def _refresh_categories(self) -> None:
        current = self._current_category
        self.category_list.blockSignals(True)
        self.category_list.clear()
        for name in self.library.categories:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            self.category_list.addItem(item)
        self.category_list.blockSignals(False)
        for row in range(self.category_list.count()):
            item = self.category_list.item(row)
            if item.data(Qt.UserRole) == current:
                self.category_list.setCurrentItem(item)
                break

    def _category_changed(self, item: QListWidgetItem | None, _previous=None) -> None:
        if item is None:
            return
        self._current_category = item.data(Qt.UserRole) or "All Sounds"
        self._settings["category"] = self._current_category
        self._refresh_table()

    def _visible_sounds(self) -> list[Sound]:
        sounds = self.library.category_sounds(self._current_category)
        needle = self.search_edit.text().strip().lower()
        if needle:
            sounds = [
                s for s in sounds
                if needle in s.title.lower() or needle in s.artist.lower() or needle in s.path.lower()
            ]
        return sounds

    def _refresh_table(self) -> None:
        sounds = self._visible_sounds()
        self.table.setRowCount(0)
        for row, sound in enumerate(sounds):
            self.table.insertRow(row)
            title = QTableWidgetItem(sound.title)
            title.setData(Qt.UserRole, sound.id)
            title.setToolTip(sound.path)
            self.table.setItem(row, 0, title)
            self.table.setItem(row, 1, QTableWidgetItem(sound.hotkey))
            self.table.setItem(row, 2, QTableWidgetItem(fmt_duration(sound.duration)))
            self.table.setItem(row, 3, QTableWidgetItem(f"{int(round(float(sound.gain or 1.0) * 100))}%"))
            self.table.setItem(row, 4, QTableWidgetItem(sound.category))
            for column in range(5):
                self.table.item(row, column).setData(Qt.UserRole + 1, sound.id)
        self._refresh_hotbar(sounds)
        self.statusBar().showMessage(f"{len(sounds)} sounds", 2500)

    def _refresh_hotbar(self, sounds: list[Sound]) -> None:
        while self.hotbar_layout.count():
            item = self.hotbar_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for sound in sounds[:12]:
            button = QPushButton(sound.title[:18])
            button.setToolTip(f"{sound.title}\n{sound.hotkey or 'No hotkey'}")
            button.setFixedHeight(34)
            button.clicked.connect(lambda _checked=False, sid=sound.id: self._play_id(sid))
            self.hotbar_layout.addWidget(button)
        self.hotbar_layout.addStretch(1)

    def _selected_sound(self) -> Sound | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return self.library.by_id(item.data(Qt.UserRole) or "")

    # ----------------------------------------------------------------- playback

    def _play_selected(self) -> None:
        sound = self._selected_sound()
        if sound is not None:
            self._play_sound(sound)

    def _play_id(self, sound_id: str) -> None:
        sound = self.library.by_id(sound_id)
        if sound is not None:
            self._play_sound(sound)

    def _on_hotkey(self, sound_id: str) -> None:
        self._play_id(sound_id)

    def _play_sound(self, sound: Sound) -> None:
        if not sound.exists:
            self._append_log(f"Missing file: {sound.path}")
            return
        mode = self.mode_combo.currentData()
        path = Path(sound.path)
        title = sound.title
        gain = float(getattr(sound, "gain", 1.0) or 1.0)
        auto_keys = (getattr(sound, "auto_keys", "") or "").strip()
        duration = float(sound.duration or 0.0)

        def work():
            data = self.audio.cache.get(path)
            if duration <= 0.0:
                duration_local = data.duration
            else:
                duration_local = duration
            self.audio.play(data, mode=mode, title=title, extra_gain=gain)
            if auto_keys:
                self.autokeys.engage(auto_keys, duration_local)
            return None

        self._run_task(work, on_done=lambda _r: self._show_playing(title))

    def _stop_all(self) -> None:
        self.audio.stop_all()
        self.autokeys.release_all()

    def _show_playing(self, title: str) -> None:
        self.statusBar().showMessage(f"Playing: {title}", 4000)
        self.setWindowTitle(f"{title} — {APP_NAME} {VERSION}")
        QTimer.singleShot(4500, lambda: self.setWindowTitle(f"{APP_NAME} {VERSION}"))
        if (
            self._tray is not None
            and bool(self._settings.get("show_notifications", True))
            and not self.isVisible()
        ):
            self._tray.showMessage(APP_NAME, f"Playing: {title}", QSystemTrayIcon.Information, 1500)

    def _mode_changed(self) -> None:
        self._settings["mode"] = self.mode_combo.currentData()
        self._save_settings()

    def _set_mode(self, mode: str) -> None:
        index = self.mode_combo.findData(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

    def _volume_changed(self, value: int) -> None:
        self.volume_value.setText(f"{value}%")
        self.audio.set_volume(value / 100.0)
        self._settings["volume"] = value / 100.0

    def _block_changed(self, checked: bool) -> None:
        self.audio.set_block_voice(checked)
        self._settings["block_voice"] = checked
        self._sync_control_strip()

    def _normalize_changed(self, checked: bool) -> None:
        self.audio.set_normalize(checked)
        self._settings["normalize"] = checked
        self._sync_control_strip()

    def _strip_block(self, checked: bool) -> None:
        if self.block_check.isChecked() != checked:
            self.block_check.setChecked(checked)
        else:
            self._sync_control_strip()

    def _strip_normalize(self, checked: bool) -> None:
        if self.normalize_check.isChecked() != checked:
            self.normalize_check.setChecked(checked)
        else:
            self._sync_control_strip()

    def _sync_control_strip(self) -> None:
        if not hasattr(self, "block_strip_btn"):
            return
        block = self.block_check.isChecked()
        normalize = self.normalize_check.isChecked()
        self.block_strip_btn.blockSignals(True)
        self.block_strip_btn.setChecked(block)
        self.block_strip_btn.setText("BLOCK VOICE: ON" if block else "BLOCK VOICE: OFF")
        self.block_strip_btn.blockSignals(False)
        self.normalize_strip_btn.blockSignals(True)
        self.normalize_strip_btn.setChecked(normalize)
        self.normalize_strip_btn.setText("NORMALIZE: ON" if normalize else "NORMALIZE: OFF")
        self.normalize_strip_btn.blockSignals(False)
        self._update_injection_badge()

    def _update_injection_badge(self) -> None:
        if not hasattr(self, "injection_badge"):
            return
        if self.audio.injection_ready:
            self.injection_badge.setText("MIC INJECTION: ON")
            self.injection_badge.setObjectName("badgeOn")
            self.injection_badge.setToolTip(
                "SoundPod is mixing your microphone and sounds into the VB-CABLE."
            )
        else:
            self.injection_badge.setText("MIC INJECTION: OFF")
            self.injection_badge.setObjectName("badgeOff")
            self.injection_badge.setToolTip(
                "No cable stream. Choose your real microphone and CABLE Input in Preferences > Audio."
            )
        self.injection_badge.style().unpolish(self.injection_badge)
        self.injection_badge.style().polish(self.injection_badge)
        self.injection_badge.update()
        if hasattr(self, "setup_banner"):
            show = (
                self._audio_started
                and os.environ.get("SOUNDPOD_NO_AUDIO") != "1"
                and not self.audio.injection_ready
            )
            self.setup_banner.setVisible(show)

    def _always_on_top(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self.isVisible():
            self.show()

    def _toggle_top(self, checked: bool) -> None:
        self.top_check.setChecked(checked)

    def _toggle_block(self, checked: bool) -> None:
        self.block_check.setChecked(checked)

    def _toggle_hotkeys(self, checked: bool) -> None:
        self._settings["hotkeys_enabled"] = checked
        if checked:
            self._register_hotkeys()
        else:
            self.hotkeys.clear()
            self.hotkey_status.setText("Hotkeys: off")
            self.hotkey_status.setStyleSheet("color:#7f8c9c;")
            self._append_log("Global hotkeys disabled.")
        self._save_settings()

    def _startup_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}"'
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        exe = pythonw if pythonw.exists() else Path(sys.executable)
        main_py = Path(__file__).resolve().parent.parent / "main.py"
        return f'"{exe}" "{main_py}"'

    def _toggle_startup(self, checked: bool) -> None:
        self._settings["start_with_windows"] = checked
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if checked:
                    winreg.SetValueEx(key, "SoundPod", 0, winreg.REG_SZ, self._startup_command())
                else:
                    try:
                        winreg.DeleteValue(key, "SoundPod")
                    except FileNotFoundError:
                        pass
            self._append_log(
                "SoundPod will start with Windows." if checked else "Windows startup entry removed."
            )
        except OSError as exc:
            self._append_log(f"Could not update the Windows startup entry: {exc}")
        self._save_settings()

    # -------------------------------------------------------------- preferences

    def _open_preferences(self) -> None:
        active = len(self.hotkeys._bindings)
        summary = f"{active} global hotkey(s) registered."
        if self.hotkey_errors:
            summary += f" {len(self.hotkey_errors)} failed; see Hotkeys > Status."
        if not self.hotkeys.available:
            summary += " Native hotkeys are unavailable in this session."
        dialog = PreferencesDialog(
            self._settings,
            parent=self,
            devices=list_devices(),
            library=self.library,
            audio=self.audio,
            hotkey_summary=summary,
            on_apply=self._apply_preferences,
        )
        dialog.exec()

    def _apply_preferences(self, values: dict) -> None:
        # Hotkey edits are collected by the dialog and saved as one batch.
        hotkey_changes = values.get("hotkey_changes") or {}
        hotkeys_changed = False
        for sound_id, hotkey in hotkey_changes.items():
            sound = self.library.by_id(sound_id)
            if sound is not None and sound.hotkey != hotkey:
                sound.hotkey = hotkey
                hotkeys_changed = True
        if hotkeys_changed:
            self.library.save()
            self._refresh_table()

        self._settings["auto_default_mic"] = bool(values.get("auto_default_mic", True))
        self._settings["always_on_top"] = bool(values.get("always_on_top", False))
        self._settings["start_minimized"] = bool(values.get("start_minimized", False))
        self._settings["minimize_to_tray"] = bool(values.get("minimize_to_tray", False))
        self._settings["show_notifications"] = bool(values.get("show_notifications", True))

        for combo, key in (
            (self.speaker_combo, "speaker"),
            (self.mic_combo, "mic"),
            (self.cable_combo, "cable"),
        ):
            index = combo.findData(values.get(key))
            if index >= 0:
                combo.setCurrentIndex(index)

        mode_index = self.mode_combo.findData(values.get("mode", "both"))
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        self.volume_slider.setValue(int(round(float(values.get("volume", 0.75)) * 100)))
        self.normalize_check.setChecked(bool(values.get("normalize", True)))
        self.block_check.setChecked(bool(values.get("block_voice", False)))
        self.top_check.setChecked(bool(values.get("always_on_top", False)))
        self.hotkeys_check.setChecked(bool(values.get("hotkeys_enabled", True)))
        self.startup_check.setChecked(bool(values.get("start_with_windows", False)))

        chosen_dir = Path(
            values.get("record_dir")
            or (Path(os.environ.get("APPDATA", Path.home())) / APP_NAME / "recordings")
        )
        if str(chosen_dir) != str(self.recorder.output_dir):
            try:
                self.recorder.set_output_dir(chosen_dir)
                self._append_log(f"Recordings folder: {chosen_dir}")
            except OSError as exc:
                self._append_log(f"Could not use recordings folder {chosen_dir}: {exc}")

        self._apply_devices()
        self._sync_control_strip()
        self._save_settings()
        if hotkeys_changed:
            self._register_hotkeys()
        self._append_log("Preferences applied.")

    # -------------------------------------------------------- default mic handoff

    def _configure_default_mic(self) -> None:
        """Optionally make CABLE Output the Windows default recording endpoint.

        Apps that follow the Windows default microphone then hear SoundPod with
        no per-app setup. The previous endpoint is restored on quit.
        """
        if not hasattr(self, "default_mic_badge"):
            return
        enabled = bool(self._settings.get("auto_default_mic", True))
        cable = winaudio.cable_output()
        if not enabled:
            if self._auto_mic_applied:
                self._restore_default_mic()
            self._update_default_mic_badge()
            return
        if cable is None:
            self._update_default_mic_badge()
            return
        current = winaudio.default_capture()
        if current is not None and winaudio.same_endpoint(current, cable):
            if self._restore_capture_id is None:
                previous = winaudio.physical_input()
                self._restore_capture_id = previous.id if previous is not None else None
            self._auto_mic_applied = True
            note = (
                "Windows default microphone is CABLE Output; apps that use the "
                "default can hear SoundPod."
            )
            if note != self._last_default_mic_note:
                self._append_log(note)
                self._last_default_mic_note = note
            self._update_default_mic_badge()
            return
        if current is not None:
            self._restore_capture_id = current.id
        try:
            how = winaudio.set_default_compat(cable.id)
        except OSError as exc:
            self._auto_mic_applied = False
            self._append_log(
                "Could not make CABLE Output the Windows default microphone: "
                f"{exc}"
            )
            self._update_default_mic_badge()
            return
        self._auto_mic_applied = True
        note = (
            f"Windows default microphone switched to {cable.name} ({how}). "
            "It will be restored when SoundPod closes."
        )
        if note != self._last_default_mic_note:
            self._append_log(note)
            self._last_default_mic_note = note
        self._update_default_mic_badge()

    def _restore_default_mic(self) -> None:
        if not self._auto_mic_applied:
            return
        target = None
        if self._restore_capture_id:
            wanted = winaudio._normalize_id(self._restore_capture_id)
            for row in winaudio.endpoints(winaudio.CAPTURE):
                if winaudio._normalize_id(row.id) == wanted:
                    target = row
                    break
        cable = winaudio.cable_output()
        if target is not None and cable is not None and winaudio.same_endpoint(target, cable):
            target = None
        if target is None:
            target = winaudio.physical_input()
        current = winaudio.default_capture()
        if target is not None and not winaudio.same_endpoint(current, target):
            try:
                how = winaudio.set_default_compat(target.id)
                self._append_log(
                    f"Windows default microphone restored to {target.name} ({how})."
                )
            except OSError as exc:
                self._append_log(f"Could not restore the Windows default microphone: {exc}")
        self._auto_mic_applied = False
        self._restore_capture_id = None
        self._last_default_mic_note = ""

    def _update_default_mic_badge(self) -> None:
        if not hasattr(self, "default_mic_badge"):
            return
        cable = winaudio.cable_output()
        current = winaudio.default_capture()
        if current is None:
            text = "WINDOWS MIC: UNKNOWN"
            obj = "badgeOff"
            tip = "Windows did not report a default recording device."
        elif cable is not None and winaudio.same_endpoint(current, cable):
            text = "WINDOWS MIC: CABLE OUTPUT"
            obj = "badgeOn"
            tip = (
                "Apps that follow the Windows default microphone hear your voice "
                "plus SoundPod. Restored when SoundPod closes."
            )
        else:
            text = f"WINDOWS MIC: {current.name}"
            if len(text) > 34:
                text = text[:31] + "…"
            auto = bool(self._settings.get("auto_default_mic", True))
            obj = "badgeOff"
            tip = (
                f"Windows default microphone is {current.name}. "
                + (
                    "SoundPod will switch it to CABLE Output when audio starts."
                    if auto
                    else "Auto switch is off; apps using the default will not hear sounds."
                )
            )
        self.default_mic_badge.setText(text)
        self.default_mic_badge.setObjectName(obj)
        self.default_mic_badge.setToolTip(tip)
        self.default_mic_badge.style().unpolish(self.default_mic_badge)
        self.default_mic_badge.style().polish(self.default_mic_badge)
        self.default_mic_badge.update()

    def _request_quit(self) -> None:
        self._quitting = True
        self.close()

    def _start_in_tray(self) -> None:
        if not self._settings.get("start_minimized"):
            return
        if self._tray is None:
            self.showMinimized()
            return
        self.hide()
        self._tray.showMessage(
            APP_NAME,
            "SoundPod is running in the tray. Double-click the tray icon to open it.",
            QSystemTrayIcon.Information,
            2500,
        )

    # -------------------------------------------------------------------- files

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add sound files", "", AUDIO_FILTER)
        if not paths:
            return
        category = self._current_category
        added = 0
        for raw in paths:
            if self.library.add_path(Path(raw), category=category) is not None:
                added += 1
        if added:
            self.library.save()
            self._refresh_categories()
            self._refresh_table()
            self._register_hotkeys()
            self._append_log(f"Added {added} sound file(s).")

    def _remove_selected(self) -> None:
        sound = self._selected_sound()
        if sound is None:
            return
        if QMessageBox.question(self, "Remove sound", f"Remove “{sound.title}” from the list?") != QMessageBox.Yes:
            return
        self.library.remove(sound)
        self.library.save()
        self._refresh_table()
        self._register_hotkeys()

    def _set_hotkey(self) -> None:
        sound = self._selected_sound()
        if sound is None:
            return
        dialog = HotkeyDialog(sound.hotkey, self)
        if dialog.exec() != QDialog.Accepted:
            return
        value = dialog.value().strip()
        if value:
            other = self.library.find_hotkey(value)
            if other is not None and other.id != sound.id:
                QMessageBox.warning(self, "Hotkey in use", f"{value} is already used by “{other.title}”.")
                return
            sound.hotkey = value
            self.library.save()
            self._refresh_table()
            self._register_hotkeys()
            return
        sound.hotkey = ""
        self.library.save()
        self._refresh_table()
        self._register_hotkeys()

    def _set_sound_volume(self) -> None:
        sound = self._selected_sound()
        if sound is None:
            return
        value, ok = QInputDialog.getInt(
            self,
            "Sound volume",
            f"Volume for “{sound.title}” in percent:",
            int(round(float(sound.gain or 1.0) * 100)),
            0,
            300,
            5,
        )
        if not ok:
            return
        sound.gain = value / 100.0
        self.library.save()
        self._append_log(f"{sound.title}: volume {value}%.")

    def _set_auto_keys(self) -> None:
        sound = self._selected_sound()
        if sound is None:
            return
        value, ok = QInputDialog.getText(
            self,
            "Auto Keys",
            "Keys sent with this sound.\n"
            "Use ~key to hold until the sound ends, plain key to tap.\n"
            "Example:  ~ctrl, f",
            text=getattr(sound, "auto_keys", "") or "",
        )
        if not ok:
            return
        sound.auto_keys = value.strip()
        self.library.save()
        self._append_log(
            f"{sound.title}: Auto Keys “{sound.auto_keys}”."
            if sound.auto_keys
            else f"{sound.title}: Auto Keys cleared."
        )

    def _edit_sound(self) -> None:
        sound = self._selected_sound()
        if sound is None:
            return
        if not sound.exists:
            self._append_log(f"Missing file: {sound.path}")
            return
        path = Path(sound.path)
        title = sound.title

        def work():
            return self.audio.cache.get(path)

        def done(data):
            output_dir = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME / "sounds"
            dialog = SoundEditor(data, title, output_dir, self)
            if dialog.exec() != QDialog.Accepted or dialog.result_path is None:
                return
            sound.path = str(dialog.result_path)
            sound.title = f"{title} (edited)"
            sound.duration = dialog.waveform.duration() * (dialog.waveform.end - dialog.waveform.start)
            self.audio.cache.get(Path(sound.path))
            self.library.save()
            self._refresh_table()
            self._register_hotkeys()
            self._append_log(f"Edited “{title}” -> {Path(sound.path).name}")

        self._run_task(work, on_done=done)

    def _toggle_remote(self, checked: bool) -> None:
        if checked:
            try:
                self._remote_url = self.remote.start()
            except Exception as exc:
                self._remote_url = ""
                if self._remote_action is not None:
                    self._remote_action.setChecked(False)
                self._append_log(f"Remote control failed to start: {exc}")
                QMessageBox.critical(self, "Remote control", f"Could not start the web server:\n{exc}")
                return
            self._append_log(f"Phone remote: {self._remote_url}")
            QMessageBox.information(
                self,
                "Phone remote",
                f"Open this address on a phone in the same Wi-Fi:\n\n{self._remote_url}\n\n"
                "The link contains a private session key. Keep it to yourself; it "
                "changes each time SoundPod starts. Windows Firewall may ask for "
                "permission the first time.",
            )
        else:
            self.remote.stop()
            self._remote_url = ""
            self._append_log("Phone remote stopped.")

    def _remote_sounds(self) -> list[dict]:
        rows = []
        for sound in self.library.sounds:
            rows.append(
                {
                    "id": sound.id,
                    "title": sound.title,
                    "category": sound.category,
                    "hotkey": sound.hotkey,
                }
            )
        return rows

    def _reveal_selected(self) -> None:
        sound = self._selected_sound()
        if sound is None or not sound.exists:
            return
        if os.name == "nt":
            subprocess_flags = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
            import subprocess
            subprocess.Popen(["explorer", "/select,", sound.path], creationflags=subprocess_flags)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(Path(sound.path).parent)])

    def _import_spl(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Soundpad list", "", "Soundpad sound list (*.spl);;All files (*.*)"
        )
        if not path:
            return
        try:
            count = self.library.import_spl(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self.library.save()
        self._refresh_categories()
        self._refresh_table()
        self._register_hotkeys()
        self._append_log(f"Imported {count} sound(s) from {path}.")

    def _export_spl(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Soundpad list", "soundlist.spl", "Soundpad sound list (*.spl)"
        )
        if not path:
            return
        try:
            self.library.export_spl(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._append_log(f"Exported sound list to {path}.")

    def _save_library(self) -> None:
        self.library.save()
        self._append_log("Sound list saved.")

    def _add_category(self) -> None:
        name, ok = QInputDialog.getText(self, "Add category", "Category name:")
        if ok and self.library.add_category(name):
            self.library.save()
            self._refresh_categories()

    def _remove_category(self) -> None:
        name = self._current_category
        if name == "All Sounds":
            return
        if QMessageBox.question(self, "Remove category", f"Remove “{name}”? Sounds move to All Sounds.") != QMessageBox.Yes:
            return
        self.library.remove_category(name)
        self._current_category = "All Sounds"
        self.library.save()
        self._refresh_categories()
        self._refresh_table()

    def _table_menu(self, position) -> None:
        sound = self._selected_sound()
        if sound is None:
            return
        menu = QMenu(self)
        menu.addAction("Play", lambda: self._play_sound(sound))
        menu.addAction("Set hotkey…", lambda: self._set_hotkey())
        menu.addAction("Edit sound…", self._edit_sound)
        menu.addAction("Set volume…", self._set_sound_volume)
        menu.addAction("Set Auto Keys…", self._set_auto_keys)
        menu.addSeparator()
        menu.addAction("Reveal in Explorer", self._reveal_selected)
        menu.addAction("Remove", self._remove_selected)
        menu.exec(self.table.viewport().mapToGlobal(position))

    # --------------------------------------------------------------------- TTS

    def _load_voices(self) -> None:
        def work():
            return self.tts.voices()

        def done(voices):
            self.voice_combo.blockSignals(True)
            self.voice_combo.clear()
            self.voice_combo.addItem("Windows default", "")
            for voice in voices or []:
                self.voice_combo.addItem(voice.label, voice.name)
            preferred = self._settings.get("tts_voice") or ""
            index = self.voice_combo.findData(preferred)
            self.voice_combo.setCurrentIndex(max(0, index))
            self.voice_combo.blockSignals(False)
            if not voices:
                self.tts_status.setText("No Windows voices found.")

        self._run_task(work, on_done=done)

    def _tts_slider_changed(self) -> None:
        self._rate_value.setText(str(self.rate_slider.value()))
        self._pitch_value.setText(str(self.pitch_slider.value()))

    def _speak(self, mode: str, save: bool = False) -> None:
        text = self.tts_text.toPlainText().strip()
        if not text:
            self.tts_status.setText("Type some text first.")
            return
        voice = self.voice_combo.currentData() or ""
        rate = self.rate_slider.value()
        pitch = self.pitch_slider.value()
        language = "en-US"
        self.tts_status.setText("Synthesizing…")
        self.tts_both_btn.setEnabled(False)
        self.tts_spk_btn.setEnabled(False)
        self.tts_mic_btn.setEnabled(False)
        self.tts_save_btn.setEnabled(False)

        def work():
            wav = self.tts.synthesize(text, voice=voice, rate=rate, pitch=pitch, language=language)
            self.audio.cache.get(wav)
            if not save:
                self.audio.play(self.audio.cache.get(wav), mode=mode, title="Text to speech")
            return wav

        def done(wav):
            self._tts_buttons(True)
            self.tts_status.setText("Spoken." if not save else "Saved.")
            if save:
                self.tts_save_done.emit(wav)
            else:
                self.tts_done.emit(wav)

        def failed(message):
            self._tts_buttons(True)
            self.tts_status.setText("TTS failed.")
            self._append_log(f"TTS failed: {message}")

        self._run_task(work, on_done=done, on_fail=failed)

    def _tts_buttons(self, enabled: bool) -> None:
        for button in (self.tts_both_btn, self.tts_spk_btn, self.tts_mic_btn, self.tts_save_btn):
            button.setEnabled(enabled)

    def _on_tts_done(self, _wav) -> None:
        self.statusBar().showMessage("Playing text to speech", 3000)

    def _on_tts_save_done(self, wav) -> None:
        target_dir = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME / "tts"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"tts-{os.urandom(3).hex()}.wav"
        try:
            shutil.copy2(wav, target)
            self.library.add_path(target, category=self._current_category)
            self.library.save()
            self._refresh_categories()
            self._refresh_table()
            self._register_hotkeys()
            self._append_log(f"Saved TTS as {target.name}.")
        except Exception as exc:
            self._append_log(f"Could not save TTS: {exc}")

    # ---------------------------------------------------------------- recorder

    def _toggle_recording(self) -> None:
        if self.recorder.recording:
            self.record_btn.setText("Stopping…")
            self.record_btn.setEnabled(False)

            def work():
                return self.recorder.stop()

            def done(path):
                self.record_btn.setText("●  Start recording")
                self.record_btn.setEnabled(True)
                self._record_timer.stop()
                self.record_time.setText("0:00")
                if path is not None:
                    self.recording_done.emit(path)

            def failed(message):
                self.record_btn.setText("●  Start recording")
                self.record_btn.setEnabled(True)
                self._record_timer.stop()
                self._append_log(f"Recording failed: {message}")
                QMessageBox.warning(
                    self,
                    "Could not save recording",
                    f"SoundPod could not save the recording.\n\n{message}",
                )

            self._run_task(work, on_done=done, on_fail=failed)
            return
        try:
            self.recorder.start(self.record_source.currentData())
        except Exception as exc:
            self._append_log(f"Recording failed: {exc}")
            QMessageBox.warning(
                self,
                "Could not start recording",
                f"{exc}\n\nIf this is a downloaded build, extract the whole "
                "SoundPod zip. SoundPodRecorder.exe must stay next to SoundPod.exe.",
            )
            return
        self.record_btn.setText("■  Stop recording")
        self.record_time.setText("0:00")
        self._record_timer.start()

    def _tick_recording(self) -> None:
        if not self.recorder.recording:
            self._record_timer.stop()
            return
        import time
        elapsed = int(time.time() - self.recorder.started_at)
        self.record_time.setText(f"{elapsed // 60}:{elapsed % 60:02d}")

    def _on_recording_done(self, path) -> None:
        sound = self.library.add_path(Path(path), category=self._current_category)
        if sound is not None:
            self.library.save()
            self._refresh_categories()
            self._refresh_table()
            self._register_hotkeys()
            self._append_log(f"Recording saved: {Path(path).name}")

    # ------------------------------------------------------------------ devices

    def _populate_devices(self) -> None:
        devices = list_devices()
        outputs = [d for d in devices if d.outputs > 0]
        inputs = [d for d in devices if d.inputs > 0]

        def fill(combo: QComboBox, rows: list[Device], none: bool, *preferred: int | None):
            combo.blockSignals(True)
            combo.clear()
            if none:
                combo.addItem("(none)", None)
            for device in rows:
                combo.addItem(device.label, device.index)
            index = -1
            for wanted in preferred:
                if wanted is None:
                    continue
                index = combo.findData(wanted)
                if index >= 0:
                    break
            if index < 0:
                index = 0
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

        speaker = default_output(devices)
        mic = default_input(devices)
        cable = find_cable_output(devices)
        by_index = {device.index: device for device in devices}

        saved_mic = self._settings.get("mic")
        saved_row = by_index.get(saved_mic) if isinstance(saved_mic, int) else None
        if saved_row is not None and mic is not None and saved_row.name == mic.name:
            saved_api = hostapi_name(saved_row.hostapi).lower()
            best_api = hostapi_name(mic.hostapi).lower()
            if saved_row.index != mic.index and (
                ("mme" in saved_api and "mme" not in best_api)
                or ("wasapi" in saved_api and saved_row.sample_rate != 48000.0)
            ):
                self._append_log(
                    f"Microphone: switched from {hostapi_name(saved_row.hostapi)} "
                    f"#{saved_row.index} to {hostapi_name(mic.hostapi)} #{mic.index} for cleaner audio."
                )
                saved_mic = mic.index
                self._settings["mic"] = mic.index

        def valid(index, want_output: bool) -> int | None:
            row = by_index.get(index) if isinstance(index, int) else None
            if row is None:
                return None
            if (row.outputs > 0) != want_output:
                return None
            name = row.name.lower()
            if "mapper" in name or is_virtual_output(row.name):
                return None
            return index

        def valid_cable(index) -> int | None:
            row = by_index.get(index) if isinstance(index, int) else None
            if row is None or row.outputs <= 0:
                return None
            if not is_virtual_output(row.name) or "output" in row.name.lower():
                return None
            return index

        fill(
            self.speaker_combo,
            outputs,
            False,
            valid(self._settings.get("speaker"), True),
            speaker.index if speaker else None,
        )
        fill(
            self.mic_combo,
            inputs,
            False,
            valid(saved_mic, False),
            mic.index if mic else None,
        )
        fill(
            self.cable_combo,
            outputs,
            True,
            valid_cable(self._settings.get("cable")),
            cable.index if cable else None,
        )
        if cable and self._settings.get("cable") is None:
            self._settings["cable"] = cable.index

    def _apply_devices(self) -> None:
        speaker = self.speaker_combo.currentData()
        mic = self.mic_combo.currentData()
        cable = self.cable_combo.currentData()
        self.audio.speaker_device = speaker
        self.audio.mic_device = mic
        self.audio.cable_device = cable
        self.audio.set_volume(self.volume_slider.value() / 100.0)
        self.audio.set_normalize(self.normalize_check.isChecked())
        self.audio.set_block_voice(self.block_check.isChecked())
        self._settings.update({"speaker": speaker, "mic": mic, "cable": cable})
        self.audio.start()
        self._save_settings()
        self._update_audio_status()
        if cable is None:
            self.cable_warning.setText(
                "No virtual cable found. Install VB-CABLE, restart Windows audio, then select CABLE Input. "
                "Without it, sounds play on speakers only."
            )
        else:
            self.cable_warning.setText(
                "SoundPod can make CABLE Output the Windows default microphone while it "
                "runs, so apps that follow the Windows default hear your voice plus "
                "sounds. Apps with an explicitly selected mic still need CABLE Output "
                "chosen once. Disable their noise suppression, auto gain and echo "
                "cancellation, or they will cut the sounds."
            )
        chosen = next(
            (device for device in list_devices() if device.index == mic),
            None,
        )
        self.recorder.set_microphone(chosen.name if chosen is not None else "")
        hint = ""
        if chosen is not None:
            api = hostapi_name(chosen.hostapi)
            if "mme" in api.lower():
                hint = (
                    "Microphone is on MME. If your voice sounds rough or delayed, "
                    "pick the DirectSound or WASAPI entry for the same microphone."
                )
            elif "wasapi" in api.lower() and chosen.sample_rate != 48000.0:
                hint = (
                    f"This microphone runs at {int(chosen.sample_rate)} Hz; Windows "
                    "resamples it to 48 kHz. The DirectSound/MME entry can be smoother."
                )
        self.quality_hint.setText(hint)
        self._append_log(f"Audio devices applied: {self.audio.status()}")
        self._check_windows_default()
        self._configure_default_mic()
        self._sync_control_strip()

    def _check_windows_default(self) -> None:
        raw = windows_default_output()
        if raw is not None and is_virtual_output(raw.name):
            self.windows_warning.setText(
                f"Windows currently sends all sound to “{raw.name}”, so the PC is silent. "
                "Click below to switch playback back to your real device."
            )
            self.windows_warning.show()
            self.fix_default_btn.show()
            self._append_log(
                f"Windows default playback is virtual ({raw.name}); local sounds will be inaudible."
            )
        else:
            self.windows_warning.hide()
            self.fix_default_btn.hide()

    def _fix_windows_default(self) -> None:
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
        except OSError as error:
            QMessageBox.warning(self, "Could not change the default device", str(error))
            self._append_log(f"Default playback fix failed: {error}")
            return
        self._append_log(f"Windows default playback set to {target.name} ({how}).")
        self._populate_devices()
        self._apply_devices()
        QMessageBox.information(
            self,
            "Default playback restored",
            f"Windows now plays through {target.name}.",
        )

    def _show_hotkey_status(self) -> None:
        active = len(self.hotkeys._bindings)
        lines = [f"Global hotkeys registered: {active}"]
        if self.hotkey_errors:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"  • {error}" for error in self.hotkey_errors)
            lines.append("")
            lines.append("Another program may own the key. Pick a different combination.")
        if not self.hotkeys.available:
            lines.append("")
            lines.append("Native event filter is not installed, so hotkeys cannot fire.")
        QMessageBox.information(self, "Hotkey status", "\n".join(lines))

    def _update_audio_status(self) -> None:
        parts = ["Speakers" if self.audio._speaker else "Speakers off"]
        parts.append("mic injection ON" if self.audio.injection_ready else "mic injection OFF")
        if self.audio.current_title:
            parts.append(self.audio.current_title)
        self.device_status.setText(" | ".join(parts))
        self._update_injection_badge()

    def _start_audio(self) -> None:
        if self._audio_started:
            return
        self._audio_started = True
        if os.environ.get("SOUNDPOD_NO_AUDIO") == "1":
            self.device_status.setText("Audio disabled by SOUNDPOD_NO_AUDIO")
            self._append_log("Audio startup skipped (SOUNDPOD_NO_AUDIO=1).")
            self._update_injection_badge()
            return
        self._populate_devices()
        self._apply_devices()

    def _open_url(self, url: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(url))

    # ---------------------------------------------------------------- hotkeys

    def _register_hotkeys(self) -> None:
        if hasattr(self, "hotkeys_check") and not self.hotkeys_check.isChecked():
            self.hotkeys.clear()
            self.hotkey_errors = []
            self.hotkey_status.setText("Hotkeys: off")
            self.hotkey_status.setStyleSheet("color:#7f8c9c;")
            return
        entries = [(s.id, s.hotkey) for s in self.library.sounds if s.hotkey.strip()]
        self.hotkey_errors = self.hotkeys.rebind(entries)
        active = len(self.hotkeys._bindings)
        if self.hotkey_errors:
            self.hotkey_status.setText(f"Hotkeys: {active} active, {len(self.hotkey_errors)} failed")
            self.hotkey_status.setStyleSheet("color:#ffbf69;")
        else:
            self.hotkey_status.setText(f"Hotkeys: {active} active")
            self.hotkey_status.setStyleSheet("color:#7f8c9c;")
        for error in self.hotkey_errors:
            self._append_log(f"Hotkey error: {error}")
        self._append_log(f"Hotkeys: {active} registered, {len(self.hotkey_errors)} failed.")

    # ----------------------------------------------------------------- helpers

    def _run_task(self, fn, on_done=None, on_fail=None) -> None:
        task = TaskThread(fn, self)
        self._tasks.append(task)
        self._callbacks[task] = (on_done, on_fail)

        def cleanup():
            self._callbacks.pop(task, None)
            if task in self._tasks:
                self._tasks.remove(task)
            task.deleteLater()

        task.done.connect(self._task_done)
        task.failed.connect(self._task_failed)
        task.finished.connect(cleanup)
        task.start()

    def _task_done(self, result) -> None:
        task = self.sender()
        callbacks = self._callbacks.get(task)
        if callbacks and callbacks[0] is not None:
            try:
                callbacks[0](result)
            except Exception as exc:
                self._append_log(f"Task failed: {exc}")

    def _task_failed(self, message: str) -> None:
        task = self.sender()
        callbacks = self._callbacks.get(task)
        if callbacks and callbacks[1] is not None:
            try:
                callbacks[1](message)
                return
            except Exception as exc:
                message = f"{message} ({exc})"
        self._append_log(message)

    def _append_log(self, message: str) -> None:
        if hasattr(self, "log"):
            self.log.appendPlainText(str(message))
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(str(message), 3500)

    def _apply_settings_to_widgets(self) -> None:
        mode = self._settings.get("mode", "both")
        index = self.mode_combo.findData(mode)
        self.mode_combo.setCurrentIndex(max(0, index))
        volume = int(float(self._settings.get("volume", 0.75)) * 100)
        self.volume_slider.setValue(volume)
        self.volume_value.setText(f"{volume}%")
        self.audio.set_volume(volume / 100.0)
        self.normalize_check.setChecked(bool(self._settings.get("normalize", True)))
        self.block_check.setChecked(bool(self._settings.get("block_voice", False)))
        self.audio.set_normalize(self.normalize_check.isChecked())
        self.audio.set_block_voice(self.block_check.isChecked())
        self.hotkeys_check.setChecked(bool(self._settings.get("hotkeys_enabled", True)))
        self.startup_check.setChecked(bool(self._settings.get("start_with_windows", False)))

    def _minimize_to_tray(self) -> None:
        if self._tray is not None:
            self.hide()
            self._tray.showMessage(APP_NAME, "Still running in the tray.", QSystemTrayIcon.Information, 2000)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME} {VERSION}</h3>"
            "<p>Soundboard for voice chat. Plays sounds and local text-to-speech "
            "through a virtual microphone.</p>"
            "<p>Clean-room functional clone inspired by Soundpad. Not affiliated with Leppsoft.</p>"
            "<p>Mic injection needs VB-CABLE or a similar virtual audio cable.</p>",
        )

    # ------------------------------------------------------------------ events

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        if not self._audio_started:
            QTimer.singleShot(50, self._start_audio)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        added = 0
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file():
                    if self.library.add_path(path, category=self._current_category) is not None:
                        added += 1
        if added:
            self.library.save()
            self._refresh_categories()
            self._refresh_table()
            self._register_hotkeys()
            self._append_log(f"Added {added} file(s) by drag and drop.")

    def closeEvent(self, event) -> None:
        self._save_settings()
        if not self._quitting and bool(self._settings.get("minimize_to_tray")) and self._tray is not None:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                APP_NAME, "Still running in the tray.", QSystemTrayIcon.Information, 2000
            )
            return
        self._quitting = True
        self._restore_default_mic()
        self.hotkeys.clear()
        self.autokeys.release_all()
        self.remote.stop()
        self.audio.stop()
        if self.recorder.recording:
            try:
                self.recorder.stop(wait=1.0)
            except Exception:
                pass
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)


def _single_instance_guard():
    """Return a kernel mutex handle, or None when another instance exists."""
    if os.name != "nt":
        return True
    import ctypes

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\SoundPod-SingleInstance")
    if not handle:
        return True
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


def _install_crash_log() -> None:
    """Write uncaught startup/UI exceptions to a file instead of failing silently."""
    log_path = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME / "crash.log"

    def hook(exc_type, exc, tb) -> None:
        import traceback

        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(text, encoding="utf-8")
        except Exception:
            pass
        try:
            QMessageBox.critical(
                None,
                APP_NAME,
                f"SoundPod hit an unexpected error.\n\n{exc}\n\nDetails were saved to:\n{log_path}",
            )
        except Exception:
            pass

    sys.excepthook = hook


def _focus_existing_instance() -> bool:
    """Bring a hidden/minimized SoundPod window to the front, if one exists."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.lower()
        if "soundpod" in title and "preferences" not in title:
            found.append(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return False
    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def main() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(APP_NAME)
    _install_crash_log()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(make_icon())
    guard = _single_instance_guard()
    if guard is None:
        if not _focus_existing_instance():
            QMessageBox.information(None, APP_NAME, "SoundPod is already running.")
        return 0
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    try:
        import pyi_splash

        pyi_splash.close()
    except Exception:
        pass
    QTimer.singleShot(400, window._start_in_tray)
    return app.exec()
