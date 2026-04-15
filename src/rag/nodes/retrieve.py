"""
RAG node: retrieve — top-k passages из Chroma по place_id.

M5.4 — AG task.
TECH_SPEC §5.2: retrieve — {place_id} → list[Passage] (top-6 by similarity), timeout 1s.
"""

from __future__ import annotations

from typing import Any

from src.kb.store import KBStore
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.retrieve")


async def retrieve(
    state: dict[str, Any],
    kb_store: KBStore,
    top_k: int = 6,
) -> dict[str, Any]:
    """
    Извлекает passages из KB для идентифицированного места.

    Args:
        state: состояние графа, должно содержать place_id.
        kb_store: экземпляр KBStore.
        top_k: число чанков для извлечения.

    Returns:
        Обновлённый state с полем passages: list[dict].
    """
    place_id = state.get("place_id")

    if not place_id:
        logger.warning("retrieve.no_place_id")
        return {**state, "passages": []}

    logger.info("retrieve.start", place_id=place_id, top_k=top_k)

    results = kb_store.query_by_place(place_id=place_id, top_k=top_k)

    logger.info("retrieve.done", place_id=place_id, passages_count=len(results))

    return {**state, "passages": results}
