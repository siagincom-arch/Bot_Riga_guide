"""
Entry point бота: python -m src.bot

M6.1 — AG task.
Инициализирует Application (long polling), регистрирует хендлеры из gateway.
"""

from __future__ import annotations

import asyncio
import sys

from src.config import settings
from src.telemetry.log import get_logger, setup_logging


logger = get_logger("bot.main")


def main() -> None:
    """Точка входа: настройка логирования → регистрация хендлеров → запуск polling."""

    if settings is None:
        print("ОШИБКА: не удалось загрузить конфигурацию. Проверьте .env файл.", file=sys.stderr)
        sys.exit(1)

    # Настраиваем логирование
    setup_logging(log_path=settings.LOG_PATH, log_level=settings.LOG_LEVEL)
    logger.info("bot.starting", log_level=settings.LOG_LEVEL)

    # Импортируем тут, чтобы setup_logging был до любого логирования
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    from src.bot.gateway import (
        on_about,
        on_help,
        on_location,
        on_photo,
        on_start,
        on_text,
        on_voice,
        on_fact,
        on_callback,
    )

    # Создаём Application
    token = settings.TELEGRAM_BOT_TOKEN.get_secret_value()
    app = Application.builder().token(token).build()

    # --- Регистрация хендлеров (порядок важен) ---

    # Команды
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_help))
    app.add_handler(CommandHandler("about", on_about))
    app.add_handler(CommandHandler("fact", on_fact))

    # Фото
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))

    # Геолокация
    app.add_handler(MessageHandler(filters.LOCATION, on_location))

    # Голосовые сообщения (M12)
    app.add_handler(MessageHandler(filters.VOICE, on_voice))

    # Текст (не команда)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Callback-кнопки (tell, more_legend, nearby)
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("bot.handlers_registered")

    # --- Запуск long polling ---
    logger.info("bot.polling_start")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
