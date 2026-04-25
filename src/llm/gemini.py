"""
Thin client для Google Gemini API — generate, embed, embed_batch, vision.

TECH_SPEC §2 (C2, C6, C9, C10): Vision, Embeddings, Generator, Checker.
ARCHITECTURE §10: google-genai (новый SDK, заменяет google-generativeai).

Retry-политику (M4.3) добавит Claude.
"""

from __future__ import annotations

from typing import Optional, AsyncGenerator

from google import genai
from google.genai import types as genai_types

from src.telemetry.log import get_logger

logger = get_logger("llm.gemini")


class GeminiClient:
    """
    Обёртка над google-genai для Riga Guide Bot.

    Методы:
        generate(prompt) → текстовый ответ.
        embed(text) → вектор 768 dim.
        embed_batch(texts) → список векторов.
        vision(image_bytes, prompt) → JSON-строка от модели.
    """

    # Модели (TECH_SPEC §8)
    TEXT_MODEL = "gemini-2.5-flash"
    EMBED_MODEL = "gemini-embedding-001"
    EMBED_DIM = 768

    def __init__(self, api_key: str) -> None:
        """
        Args:
            api_key: GEMINI_API_KEY из .env.
        """
        # Новый SDK: клиент создаётся напрямую с api_key
        self._client = genai.Client(api_key=api_key)

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
        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=prompt,
        )
        text = response.text or ""
        logger.debug("gemini.generate.ok", response_len=len(text))
        return text

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Генерация текста потоком (streaming).

        Args:
            prompt: полный промпт (уже отрендеренный из .j2 шаблона).

        Yields:
            Текстовые чанки по мере их готовности.
        """
        logger.debug("gemini.generate_stream", prompt_len=len(prompt))
        try:
            async for chunk in await self._client.aio.models.generate_content_stream(
                model=self.TEXT_MODEL,
                contents=prompt,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error("gemini.generate_stream.error", error=repr(e))
            raise

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

        # Новый SDK: Part.from_bytes для передачи байт изображения
        image_part = genai_types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg",
        )
        response = await self._client.aio.models.generate_content(
            model=self.TEXT_MODEL,
            contents=[prompt, image_part],
        )
        text = response.text or ""
        logger.debug("gemini.vision.ok", response_len=len(text))
        return text

    async def _embed_one(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        """
        Эмбеддинг одного текста через новый SDK.

        API-ключ передаётся внутри Client, не попадает в логи/URL.
        outputDimensionality гарантирует 768 dim (модель по умолчанию
        возвращает 3072).
        """
        response = await self._client.aio.models.embed_content(
            model=self.EMBED_MODEL,
            contents=text,
            config=genai_types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.EMBED_DIM,
            ),
        )
        return response.embeddings[0].values  # type: ignore[union-attr]

    async def embed(self, text: str) -> list[float]:
        """
        Получает эмбеддинг для одного текста.

        Args:
            text: текст для эмбеддинга.

        Returns:
            Вектор размерности 768.
        """
        return await self._embed_one(text, task_type="RETRIEVAL_DOCUMENT")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Получает эмбеддинги для списка текстов (sequential — API не поддерживает true batch).

        Args:
            texts: список текстов.

        Returns:
            Список векторов размерности 768.
        """
        if not texts:
            return []

        results = []
        for text in texts:
            vec = await self._embed_one(text, task_type="RETRIEVAL_DOCUMENT")
            results.append(vec)
        return results

    async def embed_query(self, text: str) -> list[float]:
        """
        Эмбеддинг для поискового запроса (task_type=RETRIEVAL_QUERY).

        Отличается от embed() задачей — оптимизирован для поиска.
        """
        return await self._embed_one(text, task_type="RETRIEVAL_QUERY")
