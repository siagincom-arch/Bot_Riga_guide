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
        Синтез речи (TTS) и сохранение в файл с перекодированием в Opus для Telegram Voice.

        Args:
            text: Текст для озвучивания (рекомендуется не более 4096 символов).
            output_path: Куда сохранить сгенерированный OGG Opus.
        """
        import os
        import shutil
        from tempfile import NamedTemporaryFile

        temp_wav_path = None
        try:
            # 1. Генерируем WAV файл через OpenAI TTS
            with NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav_file:
                temp_wav_path = temp_wav_file.name

            response = await self._client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format="wav"
            )

            response.write_to_file(temp_wav_path)

            logger.info("openai.tts.wav_created", temp_path=temp_wav_path, text_len=len(text))

            # 2. Перекодируем WAV в Telegram-совместимый OGG/Opus через ffmpeg
            try:
                cmd = [
                    "ffmpeg", "-y", "-i", temp_wav_path,
                    "-c:a", "libopus",
                    "-b:a", "32k",
                    "-ar", "48000",
                    "-ac", "1",
                    str(output_path)
                ]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(
                        "openai.tts.ffmpeg_failed",
                        returncode=process.returncode,
                        stdout=stdout.decode(errors="ignore"),
                        stderr=stderr.decode(errors="ignore")
                    )
                    raise RuntimeError(f"ffmpeg conversion failed with code {process.returncode}")

                logger.info("openai.tts.success", output_path=str(output_path), text_len=len(text))
            except FileNotFoundError:
                # Безопасный фоллбек: если ffmpeg не установлен на локальной машине разработчика
                logger.warning("openai.tts.ffmpeg_not_found_fallback", output_path=str(output_path))
                shutil.copy(temp_wav_path, output_path)
                logger.info("openai.tts.fallback_copied_wav_as_ogg", output_path=str(output_path))

        except Exception as e:
            logger.error("openai.tts.failed", error=str(e), text_len=len(text))
            raise RuntimeError(f"Ошибка генерации голоса: {e}")
        finally:
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception as cleanup_err:
                    logger.error("openai.tts.cleanup_failed", error=str(cleanup_err))

# Синглтон клиента
openai_client = None
if settings and settings.OPENAI_API_KEY:
    try:
         openai_client = OpenAIClient()
    except Exception as e:
         logger.warning("openai.client_init_failed", error=str(e))
