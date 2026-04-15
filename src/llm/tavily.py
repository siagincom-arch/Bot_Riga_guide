"""
Thin client для Tavily API — web search fallback.

TECH_SPEC §2 (C7): Web Search Fallback.
ARCHITECTURE §10: tavily-python.

Используется, когда KB имеет низкое покрытие (grade_context.score < threshold).
"""

from __future__ import annotations

from tavily import AsyncTavilyClient

from src.telemetry.log import get_logger

logger = get_logger("llm.tavily")


class TavilyClient:
    """
    Обёртка над Tavily API для веб-поиска.

    Возвращает список текстовых сниппетов, которые
    merge'ятся в контекст RAG-графа.
    """

    def __init__(self, api_key: str) -> None:
        """
        Args:
            api_key: TAVILY_API_KEY из .env.
        """
        self._client = AsyncTavilyClient(api_key=api_key)

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        """
        Поиск по запросу, возвращает текстовые сниппеты.

        Args:
            query: поисковый запрос (на русском или английском).
            max_results: максимум результатов (по умолчанию 5).

        Returns:
            Список строк-сниппетов. Пустой список при ошибке.
        """
        logger.debug("tavily.search", query=query, max_results=max_results)

        try:
            response = await self._client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
                include_answer=False,
            )

            snippets = []
            for result in response.get("results", []):
                content = result.get("content", "").strip()
                if content:
                    snippets.append(content)

            logger.debug("tavily.search.ok", snippets_count=len(snippets))
            return snippets

        except Exception as e:
            # TECH_SPEC §11: Tavily failure → silent fallback (skip web search)
            logger.warning("tavily.search.error", error=str(e))
            return []
