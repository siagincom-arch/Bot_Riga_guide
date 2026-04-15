"""
Pydantic-модели для Knowledge Base — Place и Passage.

Поля из TECH_SPEC §3.1–3.2.

Place — каноническая запись о достопримечательности.
Passage — чанк текста, привязанный к месту, хранится в Chroma.
"""

from __future__ import annotations

import hashlib
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class City(str, Enum):
    """Города, охватываемые MVP."""
    RIGA = "riga"
    SIGULDA = "sigulda"
    RUNDALE = "rundale"


class PassageTopic(str, Enum):
    """Тематическая классификация чанка (TECH_SPEC §3.2)."""
    HISTORY = "history"
    LEGEND = "legend"
    ARCHITECTURE = "architecture"
    FACT = "fact"
    ANECDOTE = "anecdote"


class Coords(BaseModel):
    """Географические координаты."""
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class Passage(BaseModel):
    """
    Чанк текста о достопримечательности, хранится в Chroma.

    passage_id генерируется как sha256(place_id + source + text[:200])
    для идемпотентности при повторном инджесте (ARCHITECTURE ADR-8).
    """
    passage_id: str = Field(default="")
    place_id: str
    text_ru: str = Field(..., min_length=1)
    topic: PassageTopic = PassageTopic.FACT
    source: str = Field(default="")

    # Embedding не хранится в модели — он в Chroma
    # embedding: list[float]  — управляется ChromaStore

    def compute_passage_id(self) -> str:
        """
        Вычисляет детерминированный ID чанка.

        Формула: sha256(place_id + source + text[:200])
        Гарантирует идемпотентность при повторном инджесте.
        """
        raw = f"{self.place_id}{self.source}{self.text_ru[:200]}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def model_post_init(self, __context: object) -> None:
        """Автозаполнение passage_id, если не задан."""
        if not self.passage_id:
            self.passage_id = self.compute_passage_id()


class Place(BaseModel):
    """
    Каноническая запись о достопримечательности (TECH_SPEC §3.1).

    Хранится в KB (Chroma metadata + SQLite place_coords).
    """
    place_id: str = Field(..., pattern=r"^[a-z0-9\-]+$")
    name_ru: str = Field(..., min_length=1)
    name_original: str = Field(default="")
    aliases: list[str] = Field(default_factory=list)
    city: City = City.RIGA
    coords: Optional[Coords] = None
    address: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    passages: list[Passage] = Field(default_factory=list)
    summary_ru: Optional[str] = None
    last_updated: date = Field(default_factory=date.today)
    sources: list[str] = Field(default_factory=list)
