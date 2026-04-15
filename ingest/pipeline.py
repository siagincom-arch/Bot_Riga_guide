"""
Ingest Pipeline — оркестратор: scrape → chunk → tag → embed → store.

M7 — AG task (блок H).
TECH_SPEC §7.1: Collect → Normalize → Enrich → Embed → Index.
ARCHITECTURE §5: ingest pipeline.

Использование:
    from ingest.pipeline import IngestPipeline
    pipeline = IngestPipeline()
    stats = await pipeline.run_wikipedia(seeds_path="ingest/seeds/riga.yaml", limit=5)
    stats = await pipeline.run_firecrawl(urls=["https://..."], limit=3)
    stats = await pipeline.run_text(title="Dome Cathedral", text="...", source="manual")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ingest.chunker import Chunker
from ingest.tagger import tag_chunk
from src.kb.models import City, Coords, Passage, PassageTopic, Place
from src.telemetry.log import get_logger

logger = get_logger("ingest.pipeline")


# ============================================================
# Статистика прогона
# ============================================================

@dataclass
class IngestStats:
    """Статистика одного прогона pipeline."""
    sources_total: int = 0
    sources_ok: int = 0
    sources_error: int = 0
    chunks_total: int = 0
    chunks_tagged: int = 0
    chunks_tag_failed: int = 0
    chunks_stored: int = 0
    places_created: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Человекочитаемая сводка."""
        return (
            f"Sources: {self.sources_ok}/{self.sources_total} OK | "
            f"Chunks: {self.chunks_total} total, {self.chunks_tagged} tagged, "
            f"{self.chunks_stored} stored | "
            f"Places: {self.places_created} | "
            f"Errors: {len(self.errors)}"
        )


# ============================================================
# Маппинг тегов → PassageTopic
# ============================================================

_TAG_TO_TOPIC: dict[str, PassageTopic] = {
    "history": PassageTopic.HISTORY,
    "legend": PassageTopic.LEGEND,
    "architecture": PassageTopic.ARCHITECTURE,
    "fact": PassageTopic.FACT,
    "anecdote": PassageTopic.ANECDOTE,
}


def _tags_to_topic(tags: list[str]) -> PassageTopic:
    """Выбирает основной PassageTopic из списка тегов (первый валидный)."""
    for tag in tags:
        if tag in _TAG_TO_TOPIC:
            return _TAG_TO_TOPIC[tag]
    return PassageTopic.FACT


# ============================================================
# Pipeline
# ============================================================

class IngestPipeline:
    """
    Оркестратор: scrape → chunk → tag → embed → store.

    Lazy-загрузка тяжёлых зависимостей (GeminiClient, KBStore)
    через singleton — не создаются до первого вызова.
    """

    def __init__(
        self,
        chunker: Chunker | None = None,
        kb_store: Any = None,
        gemini_client: Any = None,
        city: City = City.RIGA,
    ) -> None:
        """
        Args:
            chunker: экземпляр Chunker (по умолчанию — дефолтный).
            kb_store: KBStore (если None — из singleton).
            gemini_client: GeminiClient (если None — из singleton).
            city: город по умолчанию для Place.
        """
        self._chunker = chunker or Chunker()
        self._kb_store = kb_store
        self._gemini_client = gemini_client
        self._city = city

    def _get_kb_store(self) -> Any:
        """Lazy-загрузка KBStore из singleton."""
        if self._kb_store is None:
            from src.rag.singleton import get_kb_store
            self._kb_store = get_kb_store()
        return self._kb_store

    def _get_gemini_client(self) -> Any:
        """Lazy-загрузка GeminiClient из singleton."""
        if self._gemini_client is None:
            from src.rag.singleton import get_gemini_client
            self._gemini_client = get_gemini_client()
        return self._gemini_client

    # ----------------------------------------------------------
    # Основной метод: обработка одного текстового документа
    # ----------------------------------------------------------

    async def ingest_document(
        self,
        title: str,
        text: str,
        source: str = "",
        stats: IngestStats | None = None,
    ) -> Optional[Place]:
        """
        Полный pipeline для одного документа:
        chunk → tag (каждый чанк) → embed → store.

        Args:
            title: заголовок документа (для логирования).
            text: полный текст.
            source: URL источника.
            stats: объект статистики (мутируется in-place).

        Returns:
            Place если успешно, None если нет чанков.
        """
        if stats is None:
            stats = IngestStats()

        if not text or not text.strip():
            logger.warning("pipeline.empty_text", title=title)
            stats.errors.append(f"Empty text: {title}")
            return None

        gemini = self._get_gemini_client()
        kb_store = self._get_kb_store()

        # 1. Chunk — предварительный split с временным place_id
        temp_place_id = "temp"
        raw_passages = self._chunker.chunk(
            text=text,
            place_id=temp_place_id,
            source=source,
            topic=PassageTopic.FACT,  # будет перезаписан тегером
        )

        if not raw_passages:
            logger.warning("pipeline.no_chunks", title=title)
            stats.errors.append(f"No chunks: {title}")
            return None

        stats.chunks_total += len(raw_passages)
        logger.info("pipeline.chunked", title=title, chunks=len(raw_passages))

        # 2. Tag — каждый чанк через Gemini
        # Тегируем первый чанк для определения place_id/place_name
        first_tag = await tag_chunk(raw_passages[0].text_ru, gemini_client=gemini)

        if first_tag is None:
            # Fallback: если первый чанк не распозналось — пробуем второй
            if len(raw_passages) > 1:
                first_tag = await tag_chunk(raw_passages[1].text_ru, gemini_client=gemini)

        if first_tag is None:
            # Всё равно не удалось — используем title как fallback
            logger.warning("pipeline.tag_fallback", title=title)
            place_id = _title_to_place_id(title)
            place_name = title
            place_coords = None
            place_era = None
        else:
            place_id = first_tag["place_id"]
            place_name = first_tag["place_name"]
            place_coords = first_tag.get("coords")
            place_era = first_tag.get("era")
            stats.chunks_tagged += 1

        # Тегируем остальные чанки (для topic/tags)
        chunk_tags: list[Optional[dict]] = [first_tag]
        for passage in raw_passages[1:]:
            tag_result = await tag_chunk(passage.text_ru, gemini_client=gemini)
            chunk_tags.append(tag_result)
            if tag_result is not None:
                stats.chunks_tagged += 1
            else:
                stats.chunks_tag_failed += 1

        # 3. Rebuild passages с реальным place_id и topic
        final_passages: list[Passage] = []
        for passage, tag_data in zip(raw_passages, chunk_tags):
            topic = PassageTopic.FACT
            if tag_data is not None:
                topic = _tags_to_topic(tag_data.get("tags", ["fact"]))

            final_passage = Passage(
                place_id=place_id,
                text_ru=passage.text_ru,
                topic=topic,
                source=source,
            )
            final_passages.append(final_passage)

        # 4. Embed — batch-эмбеддинг всех чанков
        texts_to_embed = [p.text_ru for p in final_passages]
        try:
            embeddings = await gemini.embed_batch(texts_to_embed)
        except Exception as e:
            logger.error("pipeline.embed_error", title=title, error=str(e))
            stats.errors.append(f"Embed error: {title} — {e}")
            return None

        # 5. Store — upsert Place + Passages в KB
        coords = None
        if place_coords and isinstance(place_coords, dict):
            try:
                coords = Coords(lat=place_coords["lat"], lon=place_coords["lon"])
            except (KeyError, ValueError):
                coords = None

        place = Place(
            place_id=place_id,
            name_ru=place_name,
            city=self._city,
            coords=coords,
            sources=[source] if source else [],
        )

        try:
            stored = kb_store.upsert(place, final_passages, embeddings)
            stats.chunks_stored += stored
            stats.places_created += 1
            logger.info(
                "pipeline.stored",
                place_id=place_id,
                place_name=place_name,
                passages=stored,
            )
        except Exception as e:
            logger.error("pipeline.store_error", place_id=place_id, error=str(e))
            stats.errors.append(f"Store error: {place_id} — {e}")
            return None

        return place

    # ----------------------------------------------------------
    # Высокоуровневые методы: Wikipedia / Firecrawl / text
    # ----------------------------------------------------------

    async def run_wikipedia(
        self,
        seeds_path: str | Path | None = None,
        limit: int | None = None,
    ) -> IngestStats:
        """
        Запускает pipeline для Wikipedia-источников.

        Args:
            seeds_path: путь к YAML с seed-страницами.
            limit: максимум страниц (None = все).

        Returns:
            Статистика прогона.
        """
        from ingest.scrapers.wikipedia import WikipediaScraper

        stats = IngestStats()
        scraper = WikipediaScraper(lang="ru")

        logger.info("pipeline.wikipedia.start", seeds_path=str(seeds_path))
        results = scraper.fetch_seeds(seeds_path)

        if limit is not None:
            results = results[:limit]

        stats.sources_total = len(results)

        for doc in results:
            text = doc.get("text", "")
            title = doc.get("title", "")
            url = doc.get("url", "")
            error = doc.get("error")

            if error or not text:
                stats.sources_error += 1
                stats.errors.append(f"Scrape error: {title} — {error or 'empty'}")
                logger.warning("pipeline.wikipedia.skip", title=title, error=error)
                continue

            stats.sources_ok += 1
            await self.ingest_document(
                title=title,
                text=text,
                source=url,
                stats=stats,
            )

        logger.info("pipeline.wikipedia.done", summary=stats.summary())
        return stats

    async def run_firecrawl(
        self,
        urls: list[str],
        force: bool = False,
        limit: int | None = None,
    ) -> IngestStats:
        """
        Запускает pipeline для Firecrawl-источников.

        Args:
            urls: список URL для скрапинга.
            force: игнорировать кеш.
            limit: максимум URL (None = все).

        Returns:
            Статистика прогона.
        """
        from ingest.scrapers.firecrawl import FirecrawlScraper

        stats = IngestStats()
        scraper = FirecrawlScraper()

        if limit is not None:
            urls = urls[:limit]

        stats.sources_total = len(urls)
        logger.info("pipeline.firecrawl.start", urls_count=len(urls))

        for url in urls:
            try:
                text = scraper.scrape(url, force=force)
            except Exception as e:
                stats.sources_error += 1
                stats.errors.append(f"Firecrawl error: {url} — {e}")
                logger.error("pipeline.firecrawl.scrape_error", url=url, error=str(e))
                continue

            if not text:
                stats.sources_error += 1
                stats.errors.append(f"Empty scrape: {url}")
                continue

            stats.sources_ok += 1
            await self.ingest_document(
                title=url.split("/")[-1] or url,
                text=text,
                source=url,
                stats=stats,
            )

        logger.info("pipeline.firecrawl.done", summary=stats.summary())
        return stats

    async def run_text(
        self,
        title: str,
        text: str,
        source: str = "manual",
    ) -> IngestStats:
        """
        Запускает pipeline для одного текста (ручной ввод).

        Args:
            title: название.
            text: полный текст.
            source: источник.

        Returns:
            Статистика прогона.
        """
        stats = IngestStats()
        stats.sources_total = 1

        place = await self.ingest_document(
            title=title,
            text=text,
            source=source,
            stats=stats,
        )

        if place is not None:
            stats.sources_ok += 1
        else:
            stats.sources_error += 1

        logger.info("pipeline.text.done", summary=stats.summary())
        return stats


# ============================================================
# Утилиты
# ============================================================

def _title_to_place_id(title: str) -> str:
    """
    Конвертирует заголовок в kebab-case place_id.

    Пример: "Домский собор (Рига)" → "domskij-sobor-riga"
    """
    import re
    import unicodedata

    # Транслитерация кириллицы → латиница (простая таблица)
    translit_map = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
        "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k",
        "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    }

    result = []
    for char in title.lower():
        if char in translit_map:
            result.append(translit_map[char])
        elif char.isascii() and char.isalnum():
            result.append(char)
        elif char in (" ", "-", "_", "(", ")"):
            result.append("-")
        # Пропускаем остальные символы

    # Убираем дублированные и крайние дефисы
    text = "".join(result)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")

    return text or "unknown"
