from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.book_loader import Book
from app.core.tone import PRESETS, ToneSettings, auto_adjust, format_ssml_params, split_chunks
from app.core.tts_engine import run_async, synthesize_to_file
from app.core.video_export import concat_audio, export_mp4, make_cover


class SynthesisWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        book: Book,
        voice: str,
        voice_label: str,
        tone: ToneSettings,
        dest_mp4: str,
        workdir: Path,
    ) -> None:
        super().__init__()
        self.book = book
        self.voice = voice
        self.voice_label = voice_label
        self.tone = tone
        self.dest_mp4 = dest_mp4
        self.workdir = workdir
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            self._process()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def _process(self) -> None:
        chunks = split_chunks(self.book.text)
        if not chunks:
            raise ValueError("Текст книги пуст.")
        self.workdir.mkdir(parents=True, exist_ok=True)
        audio_parts: list[Path] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            if self._cancel:
                raise RuntimeError("Остановлено пользователем.")
            pitch, rate = auto_adjust(chunk, self.tone)
            params = format_ssml_params(pitch, rate, self.tone.volume_percent)
            part = self.workdir / f"part_{index:04d}.mp3"
            self.progress.emit(
                int((index - 1) / total * 80),
                f"Озвучка фрагмента {index} из {total}…",
            )
            run_async(
                synthesize_to_file(
                    text=chunk,
                    voice=self.voice,
                    dest=str(part),
                    rate=params["rate"],
                    pitch=params["pitch"],
                    volume=params["volume"],
                )
            )
            audio_parts.append(part)

        if self._cancel:
            raise RuntimeError("Остановлено пользователем.")

        self.progress.emit(82, "Склеиваю аудиодорожку…")
        merged = self.workdir / "full.mp3"
        concat_audio(audio_parts, merged)

        self.progress.emit(90, "Собираю обложку и MP4…")
        cover = self.workdir / "cover.png"
        tone_label = PRESETS.get(self.tone.preset, {}).get("label", self.tone.preset)
        make_cover(
            cover,
            self.book.title,
            self.book.author,
            self.voice_label,
            tone_label,
        )
        export_mp4(merged, cover, Path(self.dest_mp4))
        self.progress.emit(100, "Готово")
        self.finished_ok.emit(self.dest_mp4)


class PreviewWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, text: str, voice: str, tone: ToneSettings, dest: Path) -> None:
        super().__init__()
        self.text = text
        self.voice = voice
        self.tone = tone
        self.dest = dest

    def run(self) -> None:
        try:
            sample = self.text.strip()[:280] or "Это пробный фрагмент озвучки."
            pitch, rate = auto_adjust(sample, self.tone)
            params = format_ssml_params(pitch, rate, self.tone.volume_percent)
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            run_async(
                synthesize_to_file(
                    text=sample,
                    voice=self.voice,
                    dest=str(self.dest),
                    rate=params["rate"],
                    pitch=params["pitch"],
                    volume=params["volume"],
                )
            )
            self.finished_ok.emit(str(self.dest))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
