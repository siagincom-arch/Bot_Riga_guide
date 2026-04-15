"""
Юнит-тесты для ingest/tagger.py — автоклассификация чанков через Gemini.

AG task — M7.3 (H/I pipeline).
Тесты: happy-path, invalid-json → None, пустой chunk → None.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingest.tagger import (
    VALID_TAGS,
    _extract_json,
    _validate_result,
    tag_chunk,
)


# ============================================================
# _extract_json — парсинг ответа модели
# ============================================================

class TestExtractJson:
    """Извлечение JSON из сырого ответа модели."""

    def test_clean_json(self) -> None:
        """Чистый JSON без обёрток."""
        raw = '{"place_id": "dome", "place_name": "Собор", "tags": ["history"]}'
        result = _extract_json(raw)
        assert result is not None
        assert result["place_id"] == "dome"

    def test_json_with_markdown_wrapper(self) -> None:
        """JSON в ```json ... ``` обёртке."""
        raw = '```json\n{"place_id": "dome", "place_name": "Собор", "tags": ["fact"]}\n```'
        result = _extract_json(raw)
        assert result is not None
        assert result["place_id"] == "dome"

    def test_json_with_trailing_text(self) -> None:
        """JSON с текстом после."""
        raw = '{"place_id": "dome", "place_name": "Собор", "tags": ["fact"]} \n\n(вот так)'
        result = _extract_json(raw)
        assert result is not None
        assert result["place_id"] == "dome"

    def test_invalid_json_returns_none(self) -> None:
        """Невалидный JSON → None."""
        assert _extract_json("это не JSON вообще") is None
        assert _extract_json("{broken json ahaha") is None
        assert _extract_json("") is None

    def test_nested_json_parsed(self) -> None:
        """JSON с вложенным объектом coords."""
        raw = '{"place_id": "dome", "place_name": "Собор", "tags": ["history"], "coords": {"lat": 56.95, "lon": 24.10}}'
        result = _extract_json(raw)
        assert result is not None
        assert result["coords"]["lat"] == 56.95


# ============================================================
# _validate_result — валидация и нормализация
# ============================================================

class TestValidateResult:
    """Валидация и нормализация результата."""

    def test_valid_result(self) -> None:
        """Полностью валидный результат."""
        data = {
            "place_id": "dome-cathedral",
            "place_name": "Домский собор",
            "tags": ["history", "architecture"],
            "coords": {"lat": 56.95, "lon": 24.10},
            "era": "XIII век",
        }
        result = _validate_result(data)
        assert result is not None
        assert result["place_id"] == "dome-cathedral"
        assert result["tags"] == ["history", "architecture"]
        assert result["coords"]["lat"] == 56.95
        assert result["era"] == "XIII век"

    def test_missing_place_id(self) -> None:
        """Без place_id → None."""
        data = {"place_name": "Собор", "tags": ["fact"]}
        assert _validate_result(data) is None

    def test_missing_place_name(self) -> None:
        """Без place_name → None."""
        data = {"place_id": "dome", "tags": ["fact"]}
        assert _validate_result(data) is None

    def test_missing_tags(self) -> None:
        """Без tags → None."""
        data = {"place_id": "dome", "place_name": "Собор"}
        assert _validate_result(data) is None

    def test_invalid_place_id_format(self) -> None:
        """Невалидный place_id (пробелы, кириллица) → None."""
        data = {"place_id": "Домский Собор", "place_name": "Собор", "tags": ["fact"]}
        assert _validate_result(data) is None

    def test_invalid_tags_fallback_to_fact(self) -> None:
        """Невалидные теги → fallback к ["fact"]."""
        data = {"place_id": "dome", "place_name": "Собор", "tags": ["unknown", "weird"]}
        result = _validate_result(data)
        assert result is not None
        assert result["tags"] == ["fact"]

    def test_coords_none_when_invalid(self) -> None:
        """Невалидные coords → None."""
        data = {"place_id": "dome", "place_name": "Собор", "tags": ["fact"], "coords": "not a dict"}
        result = _validate_result(data)
        assert result is not None
        assert result["coords"] is None

    def test_era_none_when_missing(self) -> None:
        """Без era → None."""
        data = {"place_id": "dome", "place_name": "Собор", "tags": ["fact"]}
        result = _validate_result(data)
        assert result is not None
        assert result["era"] is None


# ============================================================
# tag_chunk — интеграция с Gemini
# ============================================================

class TestTagChunkHappyPath:
    """Happy-path: модель возвращает валидный JSON."""

    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        """Модель отвечает корректным JSON → dict с метаданными."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=(
            '{"place_id": "dome-cathedral", "place_name": "Домский собор", '
            '"tags": ["history", "architecture"], '
            '"coords": {"lat": 56.9496, "lon": 24.1040}, '
            '"era": "XIII век"}'
        ))

        result = await tag_chunk(
            "Домский собор в Риге — один из крупнейших средневековых храмов.",
            gemini_client=mock_client,
        )

        assert result is not None
        assert result["place_id"] == "dome-cathedral"
        assert result["place_name"] == "Домский собор"
        assert "history" in result["tags"]
        assert "architecture" in result["tags"]
        assert result["coords"]["lat"] == pytest.approx(56.9496)
        assert result["era"] == "XIII век"

        # Проверяем, что generate() был вызван с промптом, содержащим текст чанка
        call_args = mock_client.generate.call_args[0][0]
        assert "Домский собор" in call_args

    @pytest.mark.asyncio
    async def test_happy_path_minimal(self) -> None:
        """Минимальный валидный ответ — без coords и era."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=(
            '{"place_id": "freedom-monument", "place_name": "Памятник Свободы", '
            '"tags": ["history", "fact"], "coords": null, "era": null}'
        ))

        result = await tag_chunk(
            "Памятник Свободы — главный символ Латвии.",
            gemini_client=mock_client,
        )

        assert result is not None
        assert result["place_id"] == "freedom-monument"
        assert result["coords"] is None
        assert result["era"] is None

    @pytest.mark.asyncio
    async def test_happy_path_markdown_wrapped(self) -> None:
        """Модель обернула JSON в markdown — всё равно парсится."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=(
            '```json\n'
            '{"place_id": "turaida-castle", "place_name": "Турайдский замок", '
            '"tags": ["legend"], "coords": {"lat": 57.18, "lon": 24.85}, "era": "XIII век"}\n'
            '```'
        ))

        result = await tag_chunk("Легенда о Турайдской Розе...", gemini_client=mock_client)

        assert result is not None
        assert result["place_id"] == "turaida-castle"
        assert "legend" in result["tags"]


class TestTagChunkInvalidJson:
    """Невалидный JSON от модели → None (без исключения)."""

    @pytest.mark.asyncio
    async def test_garbage_response(self) -> None:
        """Модель ответила текстом без JSON → None."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="Это просто текст, не JSON")

        result = await tag_chunk("Какой-то текст о Риге.", gemini_client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_broken_json(self) -> None:
        """Битый JSON → None."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value='{"place_id": "dome", "tags": [oops}')

        result = await tag_chunk("Текст о Домском соборе.", gemini_client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_required_field(self) -> None:
        """JSON без обязательного поля → None."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value='{"place_name": "Собор", "tags": ["fact"]}')

        result = await tag_chunk("Текст о соборе.", gemini_client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_gemini_api_error(self) -> None:
        """Ошибка API Gemini → None (не падаем)."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("API rate limit"))

        result = await tag_chunk("Текст для тестирования.", gemini_client=mock_client)
        assert result is None


class TestTagChunkEmptyInput:
    """Пустой / whitespace-only вход → None."""

    @pytest.mark.asyncio
    async def test_empty_string(self) -> None:
        """Пустая строка → None, generate() не вызывается."""
        mock_client = AsyncMock()
        result = await tag_chunk("", gemini_client=mock_client)
        assert result is None
        mock_client.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_whitespace_only(self) -> None:
        """Только пробелы → None."""
        mock_client = AsyncMock()
        result = await tag_chunk("   \n\t  ", gemini_client=mock_client)
        assert result is None
        mock_client.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_none_like_empty(self) -> None:
        """None → None (не падаем)."""
        mock_client = AsyncMock()
        # tag_chunk ожидает str, но None должен обрабатываться gracefully
        result = await tag_chunk(None, gemini_client=mock_client)  # type: ignore[arg-type]
        assert result is None
