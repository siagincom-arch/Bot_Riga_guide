"""
Text Chunker — разбивает скрапленный текст на passages для KB.

M7.3 — AG task.
ARCHITECTURE §5: ingest — scrape → chunk → embed → store.

Стратегия: рекурсивный split по абзацам → предложениям.
Размер чанка: ~300-600 символов (оптимально для embedding и RAG).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.kb.models import Passage, PassageTopic
from src.telemetry.log import get_logger

logger = get_logger("ingest.chunker")


@dataclass
class ChunkConfig:
    """Конфигурация чанкера."""
    max_chars: int = 600
    min_chars: int = 100
    overlap_chars: int = 50


class Chunker:
    """
    Рекурсивный текстовый чанкер.

    Разбивает текст на части:
    1. Сначала по двойным переносам (абзацы).
    2. Если абзац > max_chars — по предложениям.
    3. Склеивает маленькие чанки с соседними.
    """

    def __init__(self, config: ChunkConfig | None = None) -> None:
        self._config = config or ChunkConfig()

    def chunk(
        self,
        text: str,
        place_id: str,
        source: str = "",
        topic: PassageTopic = PassageTopic.FACT,
    ) -> list[Passage]:
        """
        Разбивает текст на passages.

        Args:
            text: полный текст.
            place_id: ID места.
            source: URL источника.
            topic: тема (history, legend, etc).

        Returns:
            Список Passage с автосгенерированными passage_id.
        """
        if not text.strip():
            return []

        raw_chunks = self._split_text(text)

        logger.info(
            "chunker.done",
            place_id=place_id,
            input_chars=len(text),
            chunks_count=len(raw_chunks),
        )

        passages = []
        for chunk_text in raw_chunks:
            passage = Passage(
                place_id=place_id,
                text_ru=chunk_text,
                topic=topic,
                source=source,
            )
            passages.append(passage)

        return passages

    def _split_text(self, text: str) -> list[str]:
        """Рекурсивный split: абзацы → предложения → merge маленьких."""
        max_chars = self._config.max_chars
        min_chars = self._config.min_chars

        # 1. Разбиваем по двойным переносам (абзацы)
        paragraphs = re.split(r"\n{2,}", text.strip())
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks: list[str] = []

        for para in paragraphs:
            if len(para) <= max_chars:
                chunks.append(para)
            else:
                # Абзац слишком длинный — разбиваем по предложениям
                sentences = self._split_sentences(para)
                current = ""
                for sent in sentences:
                    if current and len(current) + len(sent) + 1 > max_chars:
                        chunks.append(current.strip())
                        current = sent
                    else:
                        current = f"{current} {sent}".strip() if current else sent
                if current:
                    chunks.append(current.strip())

        # 2. Merge маленьких чанков с соседними
        merged = self._merge_small(chunks, min_chars, max_chars)

        return merged

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Разбивает текст на предложения (русский + латинский)."""
        # Разделители: . ! ? за которыми идёт пробел или конец строки
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in parts if s.strip()]

    @staticmethod
    def _merge_small(chunks: list[str], min_chars: int, max_chars: int) -> list[str]:
        """Склеивает чанки меньше min_chars с соседями."""
        if not chunks:
            return []

        merged: list[str] = []
        buffer = ""

        for chunk in chunks:
            if not buffer:
                buffer = chunk
            # Склеиваем, только если хотя бы один из них слишком мал, и они вместе помещаются в лимит
            elif (len(buffer) < min_chars or len(chunk) < min_chars) and (len(buffer) + len(chunk) + 1 <= max_chars):
                buffer = f"{buffer}\n{chunk}"
            else:
                merged.append(buffer)
                buffer = chunk

        if buffer:
            # Если последний чанк или предыдущий чанк маленький — склеиваем их (если помещаются)
            if merged and (len(buffer) < min_chars or len(merged[-1]) < min_chars) and len(merged[-1]) + len(buffer) + 1 <= max_chars:
                merged[-1] = f"{merged[-1]}\n{buffer}"
            else:
                merged.append(buffer)

        return merged
