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

    async def text_to_speech(self, text: str, output_path: str | Path, max_retries: int = 1) -> None:
        """
        Синтез речи (TTS) и сохранение в файл.

        Args:
            text: Текст для озвучивания (рекомендуется не более 4096 символов).
            output_path: Куда сохранить сгенерированный OGG Opus.
            max_retries: Количество повторных попыток при сетевых ошибках.
        """
        last_error: Exception | None = None

        for attempt in range(1 + max_retries):
            try:
                response = await self._client.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
                    input=text,
                    response_format="opus"
                )

                # Читаем всё содержимое в память — надёжнее чем stream_to_file,
                # который в разных версиях SDK может быть sync или async
                audio_bytes = response.read()

                if not audio_bytes or len(audio_bytes) < 100:
                    logger.warning(
                        "openai.tts.empty_response",
                        attempt=attempt + 1,
                        bytes_received=len(audio_bytes) if audio_bytes else 0,
                    )
                    last_error = RuntimeError("TTS вернул пустой или слишком короткий ответ")
                    if attempt < max_retries:
                        await asyncio.sleep(1.5)
                        continue
                    raise last_error

                # Записываем байты в файл вручную
                Path(output_path).write_bytes(audio_bytes)

                file_size = Path(output_path).stat().st_size
                logger.info(
                    "openai.tts.success",
                    output_path=str(output_path),
                    text_len=len(text),
                    file_size=file_size,
                    attempt=attempt + 1,
                )
                return  # Успех — выходим

            except RuntimeError:
                raise  # Пробрасываем наши собственные ошибки
            except Exception as e:
                last_error = e
                logger.warning(
                    "openai.tts.attempt_failed",
                    error=repr(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    text_len=len(text),
                )
                if attempt < max_retries:
                    await asyncio.sleep(1.5)
                    continue

        # Все попытки исчерпаны
        logger.error("openai.tts.failed", error=repr(last_error), text_len=len(text))
        raise RuntimeError(f"Ошибка генерации голоса после {1 + max_retries} попыток: {last_error}")

# Синглтон клиента
openai_client = None
if settings and settings.OPENAI_API_KEY:
    try:
         openai_client = OpenAIClient()
    except Exception as e:
         logger.warning("openai.client_init_failed", error=str(e))
