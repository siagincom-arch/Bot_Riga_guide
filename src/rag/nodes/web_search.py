"""
RAG node: web_search — обёртка вокруг Tavily + merge в контекст.

M5.6 — AG task.
TECH_SPEC §5.2: web_search — {place_name} → list[str] (merged snippets), timeout 5s.
Вызывается, когда grade_context решил, что KB-контекста недостаточно.
"""

from __future__ import annotations

from typing import Any

from src.llm.tavily import TavilyClient
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.web_search")


async def web_search(
    state: dict[str, Any],
    tavily_client: TavilyClient,
    max_results: int = 5,
) -> dict[str, Any]:
    """
    Выполняет веб-поиск и объединяет результаты с существующим контекстом.

    Args:
        state: состояние графа, должно содержать place_name.
        tavily_client: экземпляр TavilyClient.
        max_results: максимум результатов поиска.

    Returns:
        Обновлённый state с дополненными passages.
    """
    place_name = state.get("place_name", "")

    if not place_name:
        logger.warning("web_search.no_place_name")
        return state

    # Формируем запрос на русском — для контекста
    query = f"{place_name} Рига Латвия история легенды"

    logger.info("web_search.start", query=query, max_results=max_results)

    snippets = await tavily_client.search(query=query, max_results=max_results)

    if not snippets:
        logger.info("web_search.empty")
        return state

    logger.info("web_search.done", snippets_count=len(snippets))

    # Merge: добавляем web-сниппеты как дополнительные passages
    existing_passages = state.get("passages", [])
    web_passages = [
        {
            "passage_id": f"web_{i}",
            "text_ru": snippet,
            "topic": "fact",
            "source": "tavily_web_search",
            "place_id": state.get("place_id", ""),
        }
        for i, snippet in enumerate(snippets)
    ]

    return {
        **state,
        "passages": existing_passages + web_passages,
        "web_search_used": True,
    }
