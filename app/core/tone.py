from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ToneSettings:
    preset: str = "neutral"
    pitch_hz: int = 0
    rate_percent: int = 0
    volume_percent: int = 0
    auto_from_text: bool = True


PRESETS: dict[str, dict] = {
    "neutral": {
        "label": "Нейтральный",
        "pitch": 0,
        "rate": 0,
        "hint": "Ровное чтение без окраски",
    },
    "calm": {
        "label": "Спокойный",
        "pitch": -12,
        "rate": -12,
        "hint": "Ниже и медленнее — для лирики и эссе",
    },
    "warm": {
        "label": "Тёплый",
        "pitch": 4,
        "rate": -6,
        "hint": "Мягкая интонация, чуть медленнее",
    },
    "bright": {
        "label": "Светлый",
        "pitch": 16,
        "rate": 8,
        "hint": "Выше и живее — для лёгкой прозы",
    },
    "dramatic": {
        "label": "Драматичный",
        "pitch": -6,
        "rate": -8,
        "hint": "Сдержанный темп, чуть ниже тон",
    },
    "dark": {
        "label": "Мрачный",
        "pitch": -22,
        "rate": -14,
        "hint": "Низкий тон и медленный темп",
    },
    "epic": {
        "label": "Эпический",
        "pitch": -10,
        "rate": -4,
        "hint": "Весомое повествование",
    },
}


def apply_preset(name: str, settings: ToneSettings) -> ToneSettings:
    data = PRESETS.get(name, PRESETS["neutral"])
    settings.preset = name
    settings.pitch_hz = int(data["pitch"])
    settings.rate_percent = int(data["rate"])
    return settings


def format_ssml_params(pitch_hz: int, rate_percent: int, volume_percent: int) -> dict[str, str]:
    pitch = f"{pitch_hz:+d}Hz"
    rate = f"{rate_percent:+d}%"
    volume = f"{volume_percent:+d}%"
    return {"pitch": pitch, "rate": rate, "volume": volume}


def split_chunks(text: str, max_chars: int = 1800) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", text)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        candidate = f"{buf} {part}".strip() if buf else part
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(part) <= max_chars:
            buf = part
        else:
            chunks.extend(_hard_split(part, max_chars))
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def _hard_split(text: str, max_chars: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for word in words:
        extra = len(word) + (1 if buf else 0)
        if size + extra > max_chars and buf:
            out.append(" ".join(buf))
            buf = [word]
            size = len(word)
        else:
            buf.append(word)
            size += extra
    if buf:
        out.append(" ".join(buf))
    return out


def auto_adjust(chunk: str, base: ToneSettings) -> tuple[int, int]:
    """Смещает высоту и темп фрагмента по знакам и ритму текста."""
    if not base.auto_from_text:
        return base.pitch_hz, base.rate_percent

    pitch = base.pitch_hz
    rate = base.rate_percent
    stripped = chunk.strip()
    exclam = stripped.count("!")
    questions = stripped.count("?")
    ellipsis = stripped.count("…") + stripped.count("...")
    quotes = stripped.count("«") + stripped.count("»") + stripped.count('"')

    if exclam:
        pitch += min(10, 3 * exclam)
        rate += min(8, 2 * exclam)
    if questions:
        pitch += min(12, 4 * questions)
        rate -= min(4, questions)
    if ellipsis:
        pitch -= min(8, 2 * ellipsis)
        rate -= min(10, 3 * ellipsis)
    if quotes >= 2:
        pitch += 4

    pitch = max(-50, min(50, pitch))
    rate = max(-50, min(50, rate))
    return pitch, rate
