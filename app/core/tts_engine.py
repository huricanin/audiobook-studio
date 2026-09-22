from __future__ import annotations

import asyncio
from dataclasses import dataclass

import edge_tts


@dataclass
class VoiceInfo:
    short_name: str
    locale: str
    gender: str
    friendly: str

    @property
    def label(self) -> str:
        gender_ru = "жен." if self.gender.lower().startswith("f") else "муж."
        return f"{self.friendly}  ·  {self.locale}  ·  {gender_ru}"


async def fetch_voices() -> list[VoiceInfo]:
    raw = await edge_tts.list_voices()
    voices: list[VoiceInfo] = []
    for item in raw:
        voices.append(
            VoiceInfo(
                short_name=item["ShortName"],
                locale=item.get("Locale", ""),
                gender=item.get("Gender", ""),
                friendly=item.get("FriendlyName", item["ShortName"]),
            )
        )
    voices.sort(key=lambda v: (v.locale != "ru-RU", v.locale, v.gender, v.friendly))
    return voices


def preferred_voice(voices: list[VoiceInfo]) -> str:
    for name in ("ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"):
        if any(v.short_name == name for v in voices):
            return name
    if voices:
        return voices[0].short_name
    return "ru-RU-SvetlanaNeural"


async def synthesize_to_file(
    text: str,
    voice: str,
    dest: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
) -> None:
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
    )
    await communicate.save(dest)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
