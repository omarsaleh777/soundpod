"""Waveform sound editor: trim, normalize and save.

The original Soundpad editor lets you cut a sound and normalize it. This clone
shows the full waveform with start/end handles and writes the edited sound to a
new WAV file, then replaces the library entry.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .audio import SAMPLE_RATE, SoundData


class Waveform(QWidget):
    """Waveform with draggable selection handles."""

    selection_changed = Signal(float, float)

    def __init__(self, samples: np.ndarray, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self._samples = np.ascontiguousarray(samples, dtype=np.float32)
        self._envelope = self._build_envelope()
        self.start = 0.0
        self.end = 1.0
        self._dragging: str | None = None

    def _build_envelope(self, buckets: int = 2400) -> np.ndarray:
        mono = np.abs(self._samples).max(axis=1) if self._samples.ndim > 1 else np.abs(self._samples)
        if len(mono) <= buckets:
            return mono.astype(np.float32)
        step = len(mono) / buckets
        out = np.zeros(buckets, dtype=np.float32)
        for index in range(buckets):
            chunk = mono[int(index * step) : int((index + 1) * step) + 1]
            out[index] = float(chunk.max()) if len(chunk) else 0.0
        return out

    def set_samples(self, samples: np.ndarray) -> None:
        self._samples = np.ascontiguousarray(samples, dtype=np.float32)
        self._envelope = self._build_envelope()
        self.start, self.end = 0.0, 1.0
        self.update()

    def duration(self) -> float:
        return len(self._samples) / SAMPLE_RATE

    def _x_to_time(self, x: float) -> float:
        width = max(1, self.width() - 1)
        return min(1.0, max(0.0, x / width))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor("#0b0e13"))

        mid = rect.center().y()
        painter.setPen(QPen(QColor("#1d2733"), 1))
        painter.drawLine(rect.left(), mid, rect.right(), mid)

        env = self._envelope
        if len(env) == 0:
            return
        width = max(1, rect.width())
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0.0, QColor("#2ecc71"))
        grad.setColorAt(0.5, QColor("#1f9d55"))
        grad.setColorAt(1.0, QColor("#2ecc71"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        half = rect.height() / 2 - 4
        for x in range(width):
            idx = int(x / width * len(env))
            peak = float(env[min(idx, len(env) - 1)])
            if peak <= 0.0:
                continue
            h = max(1.0, peak * half)
            painter.drawRect(QRectF(rect.left() + x, mid - h, 1.0, h * 2))

        if self.start > 0.0:
            painter.setBrush(QColor(0, 0, 0, 120))
            painter.drawRect(QRectF(rect.left(), rect.top(), width * self.start, rect.height()))
        if self.end < 1.0:
            painter.setBrush(QColor(0, 0, 0, 120))
            painter.drawRect(
                QRectF(rect.left() + width * self.end, rect.top(), width * (1.0 - self.end), rect.height())
            )
        painter.setBrush(QColor("#86f5b0"))
        for value in (self.start, self.end):
            x = rect.left() + width * value
            painter.drawRect(QRectF(x - 1.5, rect.top(), 3.0, rect.height()))

        painter.setPen(QPen(QColor("#4b5b6e"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = self._x_to_time(event.position().x())
        if abs(pos - self.start) <= abs(pos - self.end):
            self._dragging = "start"
            self.start = min(pos, self.end - 0.001)
        else:
            self._dragging = "end"
            self.end = max(pos, self.start + 0.001)
        self.selection_changed.emit(self.start, self.end)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging is None:
            return
        pos = self._x_to_time(event.position().x())
        if self._dragging == "start":
            self.start = min(pos, self.end - 0.001)
        else:
            self.end = max(pos, self.start + 0.001)
        self.selection_changed.emit(self.start, self.end)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = None


class SoundEditor(QDialog):
    """Trim / normalize dialog. Returns the new WAV path on accept."""

    def __init__(self, data: SoundData, title: str, output_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit sound - {title}")
        self.resize(760, 420)
        self.data = data
        self.output_dir = Path(output_dir)
        self.result_path: Path | None = None

        layout = QVBoxLayout(self)
        self.waveform = Waveform(data.samples)
        layout.addWidget(self.waveform, 1)

        info = QHBoxLayout()
        self.range_label = QLabel()
        info.addWidget(self.range_label)
        info.addStretch(1)
        reset = QPushButton("Select all")
        reset.clicked.connect(self._select_all)
        info.addWidget(reset)
        layout.addLayout(info)

        self.waveform.selection_changed.connect(self._refresh_range)

        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel("Gain"))
        self.gain = QSlider(Qt.Horizontal)
        self.gain.setRange(-200, 200)
        self.gain.setValue(0)
        self.gain.setFixedWidth(220)
        self.gain_label = QLabel("0 dB")
        self.gain.valueChanged.connect(self._refresh_gain)
        gain_row.addWidget(self.gain)
        gain_row.addWidget(self.gain_label)
        self.normalize = QCheckBox("Normalize to -1 dBFS")
        gain_row.addWidget(self.normalize)
        gain_row.addStretch(1)
        layout.addLayout(gain_row)

        self.hint = QLabel("Drag the green handles to select the part to keep.")
        self.hint.setObjectName("muted")
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_range()

    def _select_all(self) -> None:
        self.waveform.start, self.waveform.end = 0.0, 1.0
        self.waveform.update()
        self._refresh_range()

    def _refresh_range(self, *_args) -> None:
        start = self.waveform.start
        end = self.waveform.end
        seconds = (end - start) * self.waveform.duration()
        self.range_label.setText(
            f"Selection: {start * self.waveform.duration():.2f}s - "
            f"{end * self.waveform.duration():.2f}s  ({seconds:.2f}s)"
        )

    def _refresh_gain(self, value: int) -> None:
        self.gain_label.setText(f"{value / 10:.1f} dB")

    def accept(self) -> None:
        samples = self.data.samples
        total = len(samples)
        first = int(self.waveform.start * total)
        last = int(self.waveform.end * total)
        if last - first < 32:
            self.hint.setText("Selection is too short.")
            return
        clip = samples[first:last].copy()
        if self.normalize.isChecked():
            peak = float(np.max(np.abs(clip))) if len(clip) else 0.0
            if peak > 1e-9:
                clip *= (10.0 ** (-1.0 / 20.0)) / peak
        gain_db = self.gain.value() / 10.0
        if abs(gain_db) > 0.01:
            clip *= 10.0 ** (gain_db / 20.0)
        clip = np.clip(clip, -1.0, 1.0).astype(np.float32)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"edit-{uuid.uuid4().hex[:10]}.wav"
        sf.write(str(target), clip, SAMPLE_RATE, subtype="PCM_16")
        self.result_path = target
        super().accept()
