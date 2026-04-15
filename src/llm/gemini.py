"""
Thin client для Google Gemini API — generate, embed, embed_batch, vision.

TECH_SPEC §2 (C2, C6, C9, C10): Vision, Embeddings, Generator, Checker.
ARCHITECTURE §10: google-generativeai.

Retry-политику (M4.3) добавит Claude.
"""

from __future__ import annotations

import base64
from typing import Optional

import google.generativeai as genai

from src.telemetry.log import get_logger

logger = get_logger("llm.gemini")


class GeminiClient:
    """
    Обёртка над google-generativeai для Riga Guide Bot.

    Методы:
        generate(prompt) → текстовый ответ.
        embed(text) → вектор 768 dim.
        embed_batch(texts) → список векторов.
        vision(image_bytes, prompt) → JSON-строка от модели.
    """

    # Модели (TECH_SPEC §8)
    TEXT_MODEL = "gemini-2.5-flash"
    EMBED_MODEL = "text-embedding-004"

    def __init__(self, api_key: str) -> None:
        """
        Args:
            api_key: GEMINI_API_KEY из .env.
        """
        genai.configure(api_key=api_key)
        self._text_model = genai.GenerativeModel(self.TEXT_MODEL)

    async def generate(self, prompt: str) -> str:
        """
        Генерация текста по промпту.

        Args:
            prompt: полный промпт (уже отрендеренный из .j2 шаблона).

        Returns:
            Текстовый ответ модели.

        Raises:
            Exception: при ошибке API (retry добавит Claude в M4.3).
        """
        logger.debug("gemini.generate", prompt_len=len(prompt))
        response = await self._text_model.generate_content_async(prompt)
        text = response.text or ""
        logger.debug("gemini.generate.ok", response_len=len(text))
        return text

    async def vision(self, image_bytes: bytes, prompt: str) -> str:
        """
        Мультимодальный запрос: фото + текст → ответ.

        Args:
            image_bytes: байты изображения (JPEG/PNG).
            prompt: текстовый промпт (из vision.j2).

        Returns:
            Текстовый ответ модели (ожидается JSON).
        """
        logger.debug("gemini.vision", image_size=len(image_bytes), prompt_len=len(prompt))

        # Формируем мультимодальный контент
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_bytes,
        }
        response = await self._text_model.generate_content_async([prompt, image_part])
        text = response.text or ""
        logger.debug("gemini.vision.ok", response_len=len(text))
        return text

    async def embed(self, text: str) -> list[float]:
        """
        Получает эмбеддинг для одного текста.

        Args:
            text: текст для эмбеддинга.

        Returns:
            Вектор размерности 768.
        """
        result = await genai.embed_content_async(
            model=f"models/{self.EMBED_MODEL}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Получает эмбеддинги для списка текстов.

        Args:
            texts: список текстов.

        Returns:
            Список векторов размерности 768.
        """
        if not texts:
            return []

        # google-generativeai поддерживает batch через список content
        result = await genai.embed_content_async(
            model=f"models/{self.EMBED_MODEL}",
            content=texts,
            task_type="retrieval_document",
        )
        return result["embedding"]

    async def embed_query(self, text: str) -> list[float]:
        """
        Эмбеддинг для поискового запроса (task_type=retrieval_query).

        Отличается от embed() задачей — оптимизирован для поиска.
        """
        result = await genai.embed_content_async(
            model=f"models/{self.EMBED_MODEL}",
            content=text,
            task_type="retrieval_query",
        )
        return result["embedding"]
