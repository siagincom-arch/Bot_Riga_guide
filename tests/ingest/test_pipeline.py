"""
Юнит-тесты для ingest/pipeline.py — оркестратор ingest.

AG task — блок H.
Тесты: happy-path, пустой текст, tag fallback, embed error.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingest.pipeline import IngestPipeline, IngestStats, _tags_to_topic, _title_to_place_id
from src.kb.models import PassageTopic


# ============================================================
# _title_to_place_id — транслитерация
# ============================================================

class TestTitleToPlaceId:
    """Конвертация заголовков в kebab-case place_id."""

    def test_cyrillic_title(self) -> None:
        """Кириллический заголовок → транслитерация."""
        result = _title_to_place_id("Домский собор")
        assert result == "domskij-sobor"

    def test_title_with_parens(self) -> None:
        """Заголовок с скобками — скобки становятся дефисами."""
        result = _title_to_place_id("Домский собор (Рига)")
        # "(Рига)" → "-riga-" → "riga" после strip
        assert "domskij" in result
        assert "riga" in result

    def test_english_title(self) -> None:
        """Английский заголовок → lowercase kebab."""
        result = _title_to_place_id("Freedom Monument")
        assert result == "freedom-monument"

    def test_empty_title(self) -> None:
        """Пустой заголовок → 'unknown'."""
        assert _title_to_place_id("") == "unknown"

    def test_mixed_title(self) -> None:
        """Смешанный заголовок."""
        result = _title_to_place_id("Замок Turaida-123")
        assert "zamok" in result
        assert "turaida" in result
        assert "123" in result


# ============================================================
# _tags_to_topic — маппинг тегов
# ============================================================

class TestTagsToTopic:
    """Маппинг тегов из tagger → PassageTopic."""

    def test_history_tag(self) -> None:
        assert _tags_to_topic(["history"]) == PassageTopic.HISTORY

    def test_legend_tag(self) -> None:
        assert _tags_to_topic(["legend", "history"]) == PassageTopic.LEGEND

    def test_unknown_tags_default(self) -> None:
        """Неизвестные теги → FACT."""
        assert _tags_to_topic(["unknown"]) == PassageTopic.FACT

    def test_empty_tags(self) -> None:
        """Пустой список → FACT."""
        assert _tags_to_topic([]) == PassageTopic.FACT


# ============================================================
# IngestStats
# ============================================================

class TestIngestStats:
    """Проверка статистики."""

    def test_summary_format(self) -> None:
        stats = IngestStats(sources_total=5, sources_ok=3, chunks_total=20, chunks_stored=18, places_created=3)
        s = stats.summary()
        assert "3/5" in s
        assert "20" in s
        assert "18" in s
        assert "3" in s

    def test_default_values(self) -> None:
        stats = IngestStats()
        assert stats.sources_total == 0
        assert stats.errors == []


# ============================================================
# IngestPipeline.ingest_document — happy path
# ============================================================

class TestIngestDocumentHappyPath:
    """Happy-path: document → chunk → tag → embed → store."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self) -> None:
        """Полный прогон: текст → Place в KB."""
        # Мокаем GeminiClient
        mock_gemini = AsyncMock()
        # tag_chunk вызовет gemini.generate() — мокаем через patch tag_chunk
        mock_gemini.embed_batch = AsyncMock(return_value=[
            [0.1] * 768,  # для каждого чанка
        ])

        # Мокаем KBStore
        mock_kb = MagicMock()
        mock_kb.upsert = MagicMock(return_value=1)

        pipeline = IngestPipeline(
            kb_store=mock_kb,
            gemini_client=mock_gemini,
        )

        # Мокаем tag_chunk чтобы не вызывать Gemini
        tag_result = {
            "place_id": "dome-cathedral",
            "place_name": "Домский собор",
            "tags": ["history", "architecture"],
            "coords": {"lat": 56.95, "lon": 24.10},
            "era": "XIII век",
        }

        with patch("ingest.pipeline.tag_chunk", new_callable=AsyncMock) as mock_tag:
            mock_tag.return_value = tag_result

            place = await pipeline.ingest_document(
                title="Домский собор",
                text="Домский собор в Риге — один из крупнейших средневековых храмов Прибалтики.",
                source="https://ru.wikipedia.org/wiki/Домский_собор",
            )

        assert place is not None
        assert place.place_id == "dome-cathedral"
        assert place.name_ru == "Домский собор"
        assert place.coords is not None
        assert place.coords.lat == pytest.approx(56.95)

        # Проверяем что upsert был вызван
        mock_kb.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_chunk_document(self) -> None:
        """Документ с несколькими чанками."""
        mock_gemini = AsyncMock()
        mock_gemini.embed_batch = AsyncMock(return_value=[
            [0.1] * 768,
            [0.2] * 768,
        ])

        mock_kb = MagicMock()
        mock_kb.upsert = MagicMock(return_value=2)

        pipeline = IngestPipeline(kb_store=mock_kb, gemini_client=mock_gemini)

        # Длинный текст, который разобьётся на 2+ чанка
        long_text = "Домский собор в Риге. " * 50 + "\n\n" + "Легенда о соборе. " * 50

        tag_result = {
            "place_id": "dome-cathedral",
            "place_name": "Домский собор",
            "tags": ["history"],
            "coords": None,
            "era": None,
        }

        with patch("ingest.pipeline.tag_chunk", new_callable=AsyncMock) as mock_tag:
            mock_tag.return_value = tag_result
            stats = IngestStats()
            place = await pipeline.ingest_document(
                title="Dome",
                text=long_text,
                source="test",
                stats=stats,
            )

        assert place is not None
        assert stats.chunks_total >= 2
        assert stats.chunks_stored == 2  # mock вернул 2


# ============================================================
# IngestPipeline.ingest_document — edge cases
# ============================================================

class TestIngestDocumentEdgeCases:
    """Edge cases: пустой текст, tag failure, embed error."""

    @pytest.mark.asyncio
    async def test_empty_text_returns_none(self) -> None:
        """Пустой текст → None, ничего не сохранено."""
        pipeline = IngestPipeline(
            kb_store=MagicMock(),
            gemini_client=AsyncMock(),
        )
        stats = IngestStats()
        result = await pipeline.ingest_document(title="Test", text="", stats=stats)
        assert result is None
        assert "Empty text" in stats.errors[0]

    @pytest.mark.asyncio
    async def test_tag_failure_uses_title_fallback(self) -> None:
        """Если tagger вернул None → place_id из заголовка."""
        mock_gemini = AsyncMock()
        mock_gemini.embed_batch = AsyncMock(return_value=[[0.1] * 768])

        mock_kb = MagicMock()
        mock_kb.upsert = MagicMock(return_value=1)

        pipeline = IngestPipeline(kb_store=mock_kb, gemini_client=mock_gemini)

        with patch("ingest.pipeline.tag_chunk", new_callable=AsyncMock) as mock_tag:
            mock_tag.return_value = None  # тегер не смог

            place = await pipeline.ingest_document(
                title="Памятник Свободы",
                text="Памятник Свободы — символ независимости Латвии.",
                source="manual",
            )

        assert place is not None
        assert "pamyatnik" in place.place_id  # транслитерация
        assert place.coords is None

    @pytest.mark.asyncio
    async def test_embed_error_returns_none(self) -> None:
        """Ошибка embed → None, место не сохранено."""
        mock_gemini = AsyncMock()
        mock_gemini.embed_batch = AsyncMock(side_effect=Exception("API quota exceeded"))

        mock_kb = MagicMock()

        pipeline = IngestPipeline(kb_store=mock_kb, gemini_client=mock_gemini)

        tag_result = {
            "place_id": "dome",
            "place_name": "Собор",
            "tags": ["fact"],
            "coords": None,
            "era": None,
        }

        with patch("ingest.pipeline.tag_chunk", new_callable=AsyncMock) as mock_tag:
            mock_tag.return_value = tag_result
            stats = IngestStats()
            result = await pipeline.ingest_document(
                title="Dome",
                text="Some text here for chunking.",
                stats=stats,
            )

        assert result is None
        assert any("Embed error" in e for e in stats.errors)

    @pytest.mark.asyncio
    async def test_store_error_returns_none(self) -> None:
        """Ошибка store → None."""
        mock_gemini = AsyncMock()
        mock_gemini.embed_batch = AsyncMock(return_value=[[0.1] * 768])

        mock_kb = MagicMock()
        mock_kb.upsert = MagicMock(side_effect=Exception("DB locked"))

        pipeline = IngestPipeline(kb_store=mock_kb, gemini_client=mock_gemini)

        tag_result = {
            "place_id": "dome",
            "place_name": "Собор",
            "tags": ["fact"],
            "coords": None,
            "era": None,
        }

        with patch("ingest.pipeline.tag_chunk", new_callable=AsyncMock) as mock_tag:
            mock_tag.return_value = tag_result
            stats = IngestStats()
            result = await pipeline.ingest_document(
                title="Dome",
                text="Some text for the pipeline.",
                stats=stats,
            )

        assert result is None
        assert any("Store error" in e for e in stats.errors)


# ============================================================
# run_text — высокоуровневый метод
# ============================================================

class TestRunText:
    """Тест run_text — обёртка над ingest_document."""

    @pytest.mark.asyncio
    async def test_run_text_ok(self) -> None:
        """Успешный run_text."""
        mock_gemini = AsyncMock()
        mock_gemini.embed_batch = AsyncMock(return_value=[[0.1] * 768])

        mock_kb = MagicMock()
        mock_kb.upsert = MagicMock(return_value=1)

        pipeline = IngestPipeline(kb_store=mock_kb, gemini_client=mock_gemini)

        tag_result = {
            "place_id": "dome",
            "place_name": "Собор",
            "tags": ["history"],
            "coords": None,
            "era": None,
        }

        with patch("ingest.pipeline.tag_chunk", new_callable=AsyncMock) as mock_tag:
            mock_tag.return_value = tag_result
            stats = await pipeline.run_text(
                title="Собор",
                text="Домский собор в Риге — средневековый храм.",
                source="manual",
            )

        assert stats.sources_ok == 1
        assert stats.sources_error == 0
        assert stats.places_created == 1

    @pytest.mark.asyncio
    async def test_run_text_empty(self) -> None:
        """Пустой текст → sources_error = 1."""
        pipeline = IngestPipeline(kb_store=MagicMock(), gemini_client=AsyncMock())
        stats = await pipeline.run_text(title="Empty", text="", source="test")
        assert stats.sources_error == 1
        assert stats.sources_ok == 0
