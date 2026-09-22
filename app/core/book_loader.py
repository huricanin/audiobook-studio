from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import chardet
from pypdf import PdfReader

FB2_NS = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}


@dataclass
class Book:
    path: Path
    title: str
    author: str
    text: str
    format: str


def load_book(path: str | Path) -> Book:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _load_txt(path)
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".fb2":
        return _load_fb2(path)
    raise ValueError(f"Неподдерживаемый формат: {suffix}. Доступны PDF, FB2, TXT.")


def _load_txt(path: Path) -> Book:
    raw = path.read_bytes()
    detected = chardet.detect(raw) if raw else {"encoding": "utf-8"}
    encoding = detected.get("encoding") or "utf-8"
    text = raw.decode(encoding, errors="replace")
    title = path.stem
    return Book(path=path, title=title, author="", text=_normalize(text), format="txt")


def _load_pdf(path: Path) -> Book:
    reader = PdfReader(str(path))
    meta = reader.metadata
    title = ""
    author = ""
    if meta:
        title = (meta.title or "").strip()
        author = (meta.author or "").strip()
    pages: list[str] = []
    for page in reader.pages:
        chunk = page.extract_text() or ""
        pages.append(chunk)
    text = _normalize("\n\n".join(pages))
    if not text.strip():
        raise ValueError(
            "В PDF не найден извлекаемый текст. Скан без текстового слоя не поддерживается."
        )
    return Book(
        path=path,
        title=title or path.stem,
        author=author,
        text=text,
        format="pdf",
    )


def _load_fb2(path: Path) -> Book:
    raw = path.read_bytes()
    detected = chardet.detect(raw) if raw else {"encoding": "utf-8"}
    encoding = detected.get("encoding") or "utf-8"
    xml_text = raw.decode(encoding, errors="replace")
    root = ET.fromstring(xml_text)

    def findall(tag: str):
        return root.findall(f".//fb:{tag}", FB2_NS) or root.findall(f".//{tag}")

    titles = findall("book-title")
    title = titles[0].text.strip() if titles and titles[0].text else path.stem

    first_names = findall("first-name")
    last_names = findall("last-name")
    author_parts = []
    if first_names and first_names[0].text:
        author_parts.append(first_names[0].text.strip())
    if last_names and last_names[0].text:
        author_parts.append(last_names[0].text.strip())
    author = " ".join(author_parts)

    paragraphs = []
    body = root.find("fb:body", FB2_NS)
    if body is None:
        body = root.find("body")
    nodes = body.iter() if body is not None else root.iter()
    skip_tags = {"binary", "stylesheet", "annotation"}
    for node in nodes:
        tag = node.tag.split("}")[-1].lower()
        if tag in skip_tags:
            continue
        if tag in {"p", "v", "title", "subtitle", "text-author", "epigraph"}:
            piece = "".join(node.itertext()).strip()
            if piece:
                paragraphs.append(piece)

    text = _normalize("\n\n".join(paragraphs))
    if not text.strip():
        raise ValueError("Не удалось извлечь текст из FB2.")
    return Book(path=path, title=title, author=author, text=text, format="fb2")


def _normalize(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
