"""
Photo download helper — скачивание крупнейшего фото из Telegram-сообщения.

M6.6 — AG task (AG1.1).
Выбирает самый крупный PhotoSize, скачивает через Bot API.
"""

from __future__ import annotations

from telegram import Message

from src.telemetry.log import get_logger

logger = get_logger("bot.photo_utils")


async def download_largest(message: Message, max_bytes: int = 10_000_000) -> bytes:
    """
    Скачивает самый крупный вариант фото из сообщения.

    Args:
        message: Telegram-сообщение с photo.
        max_bytes: максимальный размер файла в байтах (по умолчанию 10 МБ).

    Returns:
        Байты изображения.

    Raises:
        ValueError: если нет фото в сообщении или файл превышает max_bytes.
    """
    if not message.photo:
        raise ValueError("Сообщение не содержит фото")

    # Telegram отдаёт photo как список PhotoSize, отсортированный по возрастанию
    # Берём последний (самый крупный) — у него максимальные width*height
    largest = max(message.photo, key=lambda ps: ps.width * ps.height)

    logger.info(
        "photo.download_start",
        file_id=largest.file_id,
        width=largest.width,
        height=largest.height,
        file_size=largest.file_size,
    )

    # Проверяем размер до скачивания (если Telegram отдал file_size)
    if largest.file_size and largest.file_size > max_bytes:
        raise ValueError(
            f"Фото слишком большое: {largest.file_size} байт "
            f"(максимум {max_bytes})"
        )

    # Скачиваем через Bot API
    file = await largest.get_file()
    data = await file.download_as_bytearray()

    # Перепроверяем фактический размер после скачивания
    if len(data) > max_bytes:
        raise ValueError(
            f"Скачанное фото слишком большое: {len(data)} байт "
            f"(максимум {max_bytes})"
        )

    logger.info("photo.download_ok", bytes=len(data))

    return bytes(data)
