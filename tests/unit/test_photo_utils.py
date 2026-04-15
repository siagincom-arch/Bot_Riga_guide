"""
Юнит-тесты для photo_utils — скачивание фото из Telegram.

M6.6 — AG task (AG1.1).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.photo_utils import download_largest


def _make_photo_size(file_id: str, width: int, height: int, file_size: int | None = None):
    """Создаёт мок PhotoSize."""
    ps = MagicMock()
    ps.file_id = file_id
    ps.file_unique_id = f"unique_{file_id}"
    ps.width = width
    ps.height = height
    ps.file_size = file_size
    return ps


def _make_message_with_photos(photos: list, bot_file_data: bytes = b"fake_image"):
    """Создаёт мок Message с photo и Bot.get_file."""
    message = MagicMock()
    message.photo = photos

    # Настраиваем get_file() → download_as_bytearray()
    fake_file = AsyncMock()
    fake_file.download_as_bytearray = AsyncMock(return_value=bytearray(bot_file_data))

    for ps in photos:
        ps.get_file = AsyncMock(return_value=fake_file)

    return message


class TestDownloadLargest:
    """Выбор крупнейшего фото и скачивание."""

    @pytest.mark.asyncio
    async def test_selects_largest_photo(self) -> None:
        """Выбирает PhotoSize с наибольшим width*height."""
        small = _make_photo_size("small", 320, 240)
        medium = _make_photo_size("medium", 800, 600)
        large = _make_photo_size("large", 1280, 960)

        message = _make_message_with_photos([small, medium, large])
        result = await download_largest(message)

        # Проверяем, что get_file() вызван у largest
        large.get_file.assert_awaited_once()
        small.get_file.assert_not_awaited()
        medium.get_file.assert_not_awaited()

        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_returns_bytes(self) -> None:
        """Возвращает bytes, а не bytearray."""
        photo = _make_photo_size("img", 640, 480)
        message = _make_message_with_photos([photo], bot_file_data=b"JPEG_DATA")
        result = await download_largest(message)

        assert result == b"JPEG_DATA"
        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_single_photo(self) -> None:
        """Одно фото — берёт его."""
        photo = _make_photo_size("only", 500, 500)
        message = _make_message_with_photos([photo])
        result = await download_largest(message)

        photo.get_file.assert_awaited_once()
        assert isinstance(result, bytes)


class TestDownloadLargestSizeLimit:
    """Проверка лимита размера."""

    @pytest.mark.asyncio
    async def test_rejects_large_file_by_file_size(self) -> None:
        """Отклоняет фото, если file_size > max_bytes (до скачивания)."""
        photo = _make_photo_size("huge", 4000, 3000, file_size=15_000_000)
        message = _make_message_with_photos([photo])

        with pytest.raises(ValueError, match="слишком большое"):
            await download_largest(message, max_bytes=10_000_000)

    @pytest.mark.asyncio
    async def test_rejects_large_file_after_download(self) -> None:
        """Отклоняет фото, если фактический размер > max_bytes."""
        photo = _make_photo_size("big", 2000, 1500, file_size=None)
        # file_size=None → проверка только после скачивания
        huge_data = b"x" * 5_000_000
        message = _make_message_with_photos([photo], bot_file_data=huge_data)

        with pytest.raises(ValueError, match="слишком большое"):
            await download_largest(message, max_bytes=1_000_000)

    @pytest.mark.asyncio
    async def test_accepts_within_limit(self) -> None:
        """Принимает фото в пределах лимита."""
        photo = _make_photo_size("ok", 800, 600, file_size=500_000)
        small_data = b"x" * 500_000
        message = _make_message_with_photos([photo], bot_file_data=small_data)

        result = await download_largest(message, max_bytes=1_000_000)
        assert len(result) == 500_000


class TestDownloadLargestErrors:
    """Обработка ошибок."""

    @pytest.mark.asyncio
    async def test_no_photo_raises(self) -> None:
        """Сообщение без фото → ValueError."""
        message = MagicMock()
        message.photo = []  # пустой список

        with pytest.raises(ValueError, match="не содержит фото"):
            await download_largest(message)

    @pytest.mark.asyncio
    async def test_none_photo_raises(self) -> None:
        """message.photo = None → ValueError."""
        message = MagicMock()
        message.photo = None

        with pytest.raises(ValueError, match="не содержит фото"):
            await download_largest(message)
