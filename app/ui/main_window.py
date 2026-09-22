from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core.book_loader import Book, load_book
from app.core.tone import PRESETS, ToneSettings, apply_preset
from app.core.tts_engine import VoiceInfo, fetch_voices, preferred_voice, run_async
from app.core.worker import PreviewWorker, SynthesisWorker
from app.ui.styles import STYLESHEET


class VoicesLoader(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.loaded.emit(run_async(fetch_voices()))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Audiobook Studio")
        self.resize(1180, 760)
        self.setStyleSheet(STYLESHEET)

        self.book: Book | None = None
        self.voices: list[VoiceInfo] = []
        self.tone = ToneSettings()
        self.worker: SynthesisWorker | None = None
        self.preview_worker: PreviewWorker | None = None
        self.workdir = Path(tempfile.gettempdir()) / "audiobook-studio"
        self.player = QMediaPlayer(self)
        self.audio_out = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(0.9)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        layout.addLayout(self._left_column(), 3)
        layout.addLayout(self._right_column(), 2)
        self.voices_loader = VoicesLoader()
        self.voices_loader.loaded.connect(self._on_voices)
        self.voices_loader.failed.connect(self._on_voices_fail)
        self.status.setText("Загружаю список голосов…")
        self.voices_loader.start()

    def _left_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        hero = QLabel("Озвучка книг")
        hero.setObjectName("hero")
        hint = QLabel("PDF, FB2, TXT → MP4. Голос и тональность настраиваются до экспорта.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        col.addWidget(hero)
        col.addWidget(hint)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Файл книги…")
        self.path_edit.setReadOnly(True)
        browse = QPushButton("Открыть")
        browse.clicked.connect(self.open_book)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse)
        col.addLayout(file_row)

        self.meta_label = QLabel("Книга не загружена")
        self.meta_label.setObjectName("muted")
        self.meta_label.setWordWrap(True)
        col.addWidget(self.meta_label)

        self.preview = QPlainTextEdit()
        self.preview.setPlaceholderText("Текст книги появится здесь после загрузки.")
        col.addWidget(self.preview, 1)
        return col

    def _right_column(self) -> QVBoxLayout:
        col = QVBoxLayout()

        voice_box = QGroupBox("Голос озвучки")
        voice_l = QVBoxLayout(voice_box)
        self.locale_combo = QComboBox()
        self.locale_combo.currentIndexChanged.connect(self._filter_voices)
        self.voice_combo = QComboBox()
        voice_l.addWidget(QLabel("Язык / регион"))
        voice_l.addWidget(self.locale_combo)
        voice_l.addWidget(QLabel("Голос"))
        voice_l.addWidget(self.voice_combo)
        preview_btn = QPushButton("Прослушать фрагмент")
        preview_btn.clicked.connect(self.preview_voice)
        voice_l.addWidget(preview_btn)
        col.addWidget(voice_box)

        tone_box = QGroupBox("Тональность")
        tone_l = QVBoxLayout(tone_box)
        self.preset_combo = QComboBox()
        for key, data in PRESETS.items():
            self.preset_combo.addItem(data["label"], key)
        self.preset_combo.currentIndexChanged.connect(self._on_preset)
        self.tone_hint = QLabel(PRESETS["neutral"]["hint"])
        self.tone_hint.setObjectName("muted")
        self.tone_hint.setWordWrap(True)
        tone_l.addWidget(self.preset_combo)
        tone_l.addWidget(self.tone_hint)

        grid = QGridLayout()
        self.pitch_slider = self._slider(-40, 40, 0)
        self.rate_slider = self._slider(-40, 40, 0)
        self.volume_slider = self._slider(-50, 50, 0)
        self.pitch_value = QLabel("+0 Hz")
        self.rate_value = QLabel("+0 %")
        self.volume_value = QLabel("+0 %")
        self.pitch_slider.valueChanged.connect(lambda v: self._sync_slider("pitch", v))
        self.rate_slider.valueChanged.connect(lambda v: self._sync_slider("rate", v))
        self.volume_slider.valueChanged.connect(lambda v: self._sync_slider("volume", v))
        grid.addWidget(QLabel("Высота тона"), 0, 0)
        grid.addWidget(self.pitch_slider, 0, 1)
        grid.addWidget(self.pitch_value, 0, 2)
        grid.addWidget(QLabel("Темп"), 1, 0)
        grid.addWidget(self.rate_slider, 1, 1)
        grid.addWidget(self.rate_value, 1, 2)
        grid.addWidget(QLabel("Громкость"), 2, 0)
        grid.addWidget(self.volume_slider, 2, 1)
        grid.addWidget(self.volume_value, 2, 2)
        tone_l.addLayout(grid)

        self.auto_tone = QCheckBox("Учитывать тональность текста (! ? … диалоги)")
        self.auto_tone.setChecked(True)
        tone_l.addWidget(self.auto_tone)
        col.addWidget(tone_box)

        out_box = QGroupBox("Экспорт MP4")
        out_l = QVBoxLayout(out_box)
        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Куда сохранить видео…")
        out_btn = QPushButton("Путь")
        out_btn.clicked.connect(self.choose_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_btn)
        out_l.addLayout(out_row)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel("Готово к работе")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        out_l.addWidget(self.progress)
        out_l.addWidget(self.status)
        btns = QHBoxLayout()
        self.start_btn = QPushButton("Озвучить в MP4")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_export)
        self.cancel_btn = QPushButton("Стоп")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_export)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.cancel_btn)
        out_l.addLayout(btns)
        col.addWidget(out_box)
        col.addStretch(1)
        return col

    def _slider(self, lo: int, hi: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        return slider

    def _on_voices_fail(self, message: str) -> None:
        self.status.setText("Не удалось загрузить голоса")
        QMessageBox.warning(
            self,
            "Голоса",
            "Не удалось загрузить список голосов Microsoft Edge TTS.\n"
            "Нужен интернет при первом запуске.\n\n"
            f"{message}",
        )

    def _on_voices(self, voices: list) -> None:
        self.voices = voices
        self.status.setText("Голоса загружены")
        locales = sorted({v.locale for v in self.voices})
        self.locale_combo.blockSignals(True)
        self.locale_combo.clear()
        self.locale_combo.addItem("Все языки", "")
        for loc in locales:
            self.locale_combo.addItem(loc, loc)
        ru = self.locale_combo.findData("ru-RU")
        if ru >= 0:
            self.locale_combo.setCurrentIndex(ru)
        self.locale_combo.blockSignals(False)
        self._filter_voices()
        preferred = preferred_voice(self.voices)
        idx = self.voice_combo.findData(preferred)
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)

    def _filter_voices(self) -> None:
        locale = self.locale_combo.currentData() or ""
        current = self.voice_combo.currentData()
        self.voice_combo.clear()
        for voice in self.voices:
            if locale and voice.locale != locale:
                continue
            self.voice_combo.addItem(voice.label, voice.short_name)
        if current:
            idx = self.voice_combo.findData(current)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

    def _on_preset(self) -> None:
        key = self.preset_combo.currentData()
        apply_preset(key, self.tone)
        data = PRESETS[key]
        self.tone_hint.setText(data["hint"])
        self.pitch_slider.blockSignals(True)
        self.rate_slider.blockSignals(True)
        self.pitch_slider.setValue(self.tone.pitch_hz)
        self.rate_slider.setValue(self.tone.rate_percent)
        self.pitch_slider.blockSignals(False)
        self.rate_slider.blockSignals(False)
        self._sync_slider("pitch", self.tone.pitch_hz)
        self._sync_slider("rate", self.tone.rate_percent)

    def _sync_slider(self, kind: str, value: int) -> None:
        if kind == "pitch":
            self.tone.pitch_hz = value
            self.pitch_value.setText(f"{value:+d} Hz")
        elif kind == "rate":
            self.tone.rate_percent = value
            self.rate_value.setText(f"{value:+d} %")
        else:
            self.tone.volume_percent = value
            self.volume_value.setText(f"{value:+d} %")

    def open_book(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите книгу",
            "",
            "Книги (*.pdf *.fb2 *.txt);;PDF (*.pdf);;FictionBook (*.fb2);;Текст (*.txt)",
        )
        if not path:
            return
        try:
            book = load_book(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ошибка чтения", str(exc))
            return
        self.book = book
        self.path_edit.setText(path)
        meta = book.title
        if book.author:
            meta = f"{book.title} — {book.author}"
        chars = len(book.text)
        self.meta_label.setText(f"{meta}  ·  {chars:,} символов  ·  {book.format.upper()}")
        self.preview.setPlainText(book.text)
        suggested = Path(path).with_suffix(".mp4")
        self.out_edit.setText(str(suggested))

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить MP4",
            self.out_edit.text() or "audiobook.mp4",
            "Видео MP4 (*.mp4)",
        )
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.out_edit.setText(path)

    def _current_voice(self) -> tuple[str, str]:
        name = self.voice_combo.currentData()
        label = self.voice_combo.currentText()
        if not name:
            raise ValueError("Выберите голос озвучки.")
        return name, label

    def _current_tone(self) -> ToneSettings:
        self.tone.auto_from_text = self.auto_tone.isChecked()
        self.tone.preset = self.preset_combo.currentData() or "neutral"
        return self.tone

    def preview_voice(self) -> None:
        if self.preview_worker and self.preview_worker.isRunning():
            return
        try:
            voice, _ = self._current_voice()
        except ValueError as exc:
            QMessageBox.warning(self, "Голос", str(exc))
            return
        text = self.preview.toPlainText()
        dest = self.workdir / "preview.mp3"
        self.status.setText("Готовлю пробный фрагмент…")
        self.preview_worker = PreviewWorker(text, voice, self._current_tone(), dest)
        self.preview_worker.finished_ok.connect(self._play_preview)
        self.preview_worker.failed.connect(lambda m: QMessageBox.critical(self, "Превью", m))
        self.preview_worker.start()

    def _play_preview(self, path: str) -> None:
        self.status.setText("Играет пробный фрагмент")
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def start_export(self) -> None:
        if not self.book:
            QMessageBox.information(self, "Книга", "Сначала откройте PDF, FB2 или TXT.")
            return
        dest = self.out_edit.text().strip()
        if not dest:
            self.choose_output()
            dest = self.out_edit.text().strip()
        if not dest:
            return
        try:
            voice, label = self._current_voice()
        except ValueError as exc:
            QMessageBox.warning(self, "Голос", str(exc))
            return

        text = self.preview.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Текст", "Нет текста для озвучки.")
            return
        self.book.text = text

        job_dir = self.workdir / "job"
        self.worker = SynthesisWorker(
            book=self.book,
            voice=voice,
            voice_label=label,
            tone=self._current_tone(),
            dest_mp4=dest,
            workdir=job_dir,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.worker.start()

    def cancel_export(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.status.setText("Останавливаю…")

    def _on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.status.setText(message)

    def _on_done(self, path: str) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        self.status.setText(f"Сохранено: {path}")
        QMessageBox.information(self, "Готово", f"Аудиокнига сохранена:\n{path}")

    def _on_fail(self, message: str) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status.setText("Ошибка")
        QMessageBox.critical(self, "Ошибка озвучки", message)
