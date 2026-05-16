"""
OpenAI API клиент для обработки аудио (TTS и STT).

Используется для:
1) Перевода голосовых сообщений туристов в текст (Whisper).
2) Озвучивания исторических справок для отправки ответом (TTS).
"""

from __future__ import annotations

import structlog
from pathlib import Path
import asyncio

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from src.config import settings

logger = structlog.get_logger(__name__)

class OpenAIClient:
    """Клиент для работы с аудио через OpenAI API."""

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не задан")
        if not AsyncOpenAI:
            raise RuntimeError("Пакет openai не установлен. Выполните pip install openai")
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())

    async def speech_to_text(self, audio_path: str | Path) -> str:
        """
        Перевод аудио-файла в текст (STT) через Whisper.

        Args:
            audio_path: Путь к скачанному .ogg файлу.

        Returns:
            Распознанный текст на русском языке.
        """
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru",
                    response_format="text"
                )
            # При `response_format="text"` возвращается просто строка
            return str(transcript).strip()
        except Exception as e:
            logger.error("openai.stt.failed", error=str(e), path=str(audio_path))
            raise RuntimeError(f"Ошибка распознавания речи: {e}")

    async def text_to_speech(self, text: str, output_path: str | Path) -> None:
        """
        Синтез речи (TTS) и сохранение в файл.

        Args:
            text: Текст для озвучивания (рекомендуется не более 4096 символов).
            output_path: Куда сохранить сгенерированный OGG Opus или MP3.
        """
        try:
            # Для Telegram Voice (send_voice) лучше всего подходит формат opus (.ogg)
            response = await self._client.audio.speech.create(
                model="tts-1",
                voice="alloy", # можно поменять на onyx, echo, fable, nova, shimmer
                input=text,
                response_format="opus"
            )
            
            import inspect
            res = response.stream_to_file(output_path)
            if inspect.iscoroutine(res):
                await res
                
            logger.info("openai.tts.success", output_path=str(output_path), text_len=len(text))
        except Exception as e:
            logger.error("openai.tts.failed", error=str(e), text_len=len(text))
            raise RuntimeError(f"Ошибка генерации голоса: {e}")

# Синглтон клиента
openai_client = None
if settings and settings.OPENAI_API_KEY:
    try:
         openai_client = OpenAIClient()
    except Exception as e:
         logger.warning("openai.client_init_failed", error=str(e))
