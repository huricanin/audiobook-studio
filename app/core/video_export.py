from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def wrap_text(text: str, width: int = 28) -> list[str]:
    words = text.split()
    lines: list[str] = []
    buf: list[str] = []
    for word in words:
        trial = " ".join(buf + [word])
        if len(trial) <= width:
            buf.append(word)
        else:
            if buf:
                lines.append(" ".join(buf))
            buf = [word]
    if buf:
        lines.append(" ".join(buf))
    return lines[:8]


def make_cover(path: Path, title: str, author: str, voice_label: str, tone_label: str) -> Path:
    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), "#0f1419")
    draw = ImageDraw.Draw(img)

    for i in range(height):
        mix = i / height
        r = int(15 + 28 * mix)
        g = int(20 + 18 * mix)
        b = int(25 + 40 * mix)
        draw.line([(0, i), (width, i)], fill=(r, g, b))

    draw.rectangle([120, 140, 180, 940], fill="#d4a373")
    draw.rectangle([0, 0, width, 8], fill="#d4a373")

    try:
        title_font = ImageFont.truetype("arial.ttf", 72)
        sub_font = ImageFont.truetype("arial.ttf", 36)
        small_font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        title_font = ImageFont.load_default()
        sub_font = title_font
        small_font = title_font

    y = 280
    draw.text((260, 180), "AUDIOBOOK STUDIO", font=small_font, fill="#d4a373")
    for line in wrap_text(title or "Аудиокнига", 26):
        draw.text((260, y), line, font=title_font, fill="#f4f1ea")
        y += 88
    if author:
        draw.text((260, y + 12), author, font=sub_font, fill="#c9c4b8")
        y += 70
    draw.text((260, 860), f"Голос: {voice_label}", font=small_font, fill="#9aa3ad")
    draw.text((260, 910), f"Тональность: {tone_label}", font=small_font, fill="#9aa3ad")

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


def concat_audio(parts: list[Path], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        shutil.copy2(parts[0], dest)
        return dest
    list_file = dest.with_suffix(".concat.txt")
    lines = []
    for part in parts:
        escaped = part.resolve().as_posix().replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")
    cmd = [
        _ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(dest),
    ]
    _run(cmd)
    return dest


def export_mp4(audio: Path, cover: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "1",
        "-i",
        str(cover),
        "-i",
        str(audio),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    _run(cmd)
    return dest


def _run(cmd: list[str]) -> None:
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err or "ffmpeg завершился с ошибкой")
