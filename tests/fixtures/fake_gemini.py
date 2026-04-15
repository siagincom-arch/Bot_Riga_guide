"""
Детерминированный фейк GeminiClient для тестов.

M4.6 — Claude task.
Используется в юнит-тестах RAG-узлов и интеграционных тестах графа,
чтобы не дёргать настоящий API и не зависеть от нестабильных LLM-ответов.

Контракт совпадает с src/llm/gemini.GeminiClient: generate, vision, embed, embed_batch, embed_query.
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable


class FakeGeminiClient:
    """
    Фейковый клиент. Все методы async, чтобы drop-in заменить настоящий.

    По умолчанию:
    - generate возвращает "СПРАВКА-stub.\\n\\nИСТОРИЯ-stub." (формат двух блоков).
    - vision возвращает JSON с name_ru="Тестовое место", confidence=0.9.
    - embed возвращает детерминированный 768-мерный вектор на основе хэша текста.

    Для точечного управления — задать `responses` в конструкторе или использовать setters.
    """

    def __init__(
        self,
        *,
        generate_response: str | None = None,
        vision_response: str | None = None,
        vision_routing: dict[str, str] | None = None,
    ) -> None:
        self._generate_response = generate_response
        self._vision_response = vision_response
        self._vision_routing = vision_routing or {}

        # Счётчики вызовов — для проверки в тестах
        self.generate_calls: list[str] = []
        self.vision_calls: list[tuple[bytes, str]] = []
        self.embed_calls: list[str] = []

    # --- Text generation ---

    async def generate(self, prompt: str) -> str:
        self.generate_calls.append(prompt)
        if self._generate_response is not None:
            return self._generate_response
        # Дефолтный ответ в формате, который генератор из USER_SPEC §4 ожидает
        return (
            "Это тестовое место в центре Риги, построено в XIII веке.\n"
            "\n"
            "Легенда гласит, что по ночам здесь можно услышать шаги старого стража. "
            "Однажды ученик органиста спрятался внутри и услышал, как камни переговариваются. "
            "С тех пор дети приходят сюда загадывать желания. "
            "Местные говорят, что место помнит всё — и доброе, и плохое. "
            "В годы войны здесь прятали людей. "
            "А в мирное время — влюблённых. "
            "Каждый камень знает свою историю. "
            "И если постоять тихо — она сама зазвучит."
        )

    # --- Vision ---

    async def vision(self, image_bytes: bytes, prompt: str) -> str:
        self.vision_calls.append((image_bytes, prompt))

        # Подмена по ключу в prompt (для сценариев "не Латвия", "не узнал" и т.п.)
        for key, resp in self._vision_routing.items():
            if key in prompt:
                return resp

        if self._vision_response is not None:
            return self._vision_response

        return json.dumps(
            {
                "name_ru": "Тестовое место",
                "name_lv": "Testa vieta",
                "confidence": 0.9,
                "why": "stub для тестов",
            },
            ensure_ascii=False,
        )

    # --- Embeddings ---

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return _deterministic_vector(text)

    async def embed_query(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return _deterministic_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.extend(texts)
        return [_deterministic_vector(t) for t in texts]


class FakeTavilyClient:
    """Детерминированный фейк Tavily для тестов."""

    def __init__(self, response: list[str] | None = None) -> None:
        self._response = response
        self.calls: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        self.calls.append(query)
        if self._response is not None:
            return self._response[:max_results]
        return [f"Stub snippet about '{query}' #{i}" for i in range(min(2, max_results))]


def _deterministic_vector(text: str, dim: int = 768) -> list[float]:
    """Хэш-базированный псевдо-эмбеддинг. Один и тот же текст → один и тот же вектор."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Растягиваем 32-байтовый дайджест до `dim` float-ов в диапазоне [-1, 1]
    repeats = (dim // len(digest)) + 1
    extended = (digest * repeats)[:dim]
    return [(b - 128) / 128.0 for b in extended]


# Удобная фабрика для callable-стиля (если тесту нужно менять generate между вызовами)
def fake_gemini_with_generate(fn: Callable[[str], str]) -> FakeGeminiClient:
    """Клиент, у которого generate вызывает произвольную функцию от prompt."""
    client = FakeGeminiClient()

    async def patched(prompt: str) -> str:
        client.generate_calls.append(prompt)
        return fn(prompt)

    client.generate = patched  # type: ignore[assignment]
    return client
