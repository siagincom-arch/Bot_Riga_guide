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
    gemini_client: Any = None,
    top_k: int = 6,
) -> dict[str, Any]:
    """
    Извлекает passages из KB для идентифицированного места.
    Если есть query и gemini_client, делает семантический поиск,
    иначе откатывается на query_by_place.

    Args:
        state: состояние графа, должно содержать place_id или query.
        kb_store: экземпляр KBStore.
        gemini_client: клиент для получения эмбеддингов.
        top_k: число чанков для извлечения.

    Returns:
        Обновлённый state с полем passages: list[dict].
    """
    place_id = state.get("place_id")
    query = (state.get("query") or "").strip()

    if not place_id and not query:
        logger.warning("retrieve.no_place_id_and_query")
        return {**state, "passages": []}

    logger.info("retrieve.start", place_id=place_id, has_query=bool(query), top_k=top_k)

    results = []
    
    # 1. Пробуем семантический поиск, если есть текст запроса
    if query and gemini_client:
        try:
            # Получаем эмбеддинг, если его нет в state
            embedding = state.get("query_embedding")
            if not embedding:
                embedding = await gemini_client.embed_query(query)
            
            # Если place_id = dyn_*, значит точное место не найдено, ищем по всей базе
            filter_place_id = place_id
            if place_id and place_id.startswith("dyn_"):
                filter_place_id = None
                
            results = kb_store.semantic_search(
                query_embedding=embedding,
                top_k=top_k * 3,
                place_id=filter_place_id
            )
        except Exception as e:
            logger.error("retrieve.semantic_search_failed", error=repr(e))

    # 2. Фолбэк на запрос всех фактов для места, если нет результатов семантического поиска
    if not results and place_id and not place_id.startswith("dyn_"):
        results = kb_store.query_by_place(place_id=place_id, top_k=top_k * 3)

    session_history = state.get("session_history", [])
    history_text = " ".join([m["text"] for m in session_history if m["role"] == "bot"]).lower()

    if history_text and results:
        filtered = []
        history_words = set(history_text.split())
        for r in results:
            text = r.get("text_ru", "").lower()
            words = set(text.split())
            if not words:
                continue
            overlap = len(words.intersection(history_words)) / len(words)
            # Если меньше половины слов из чанка есть в недавней истории — считаем новым
            if overlap < 0.5:
                filtered.append(r)
        
        # Если после фильтрации совсем ничего не осталось (мало фактов), 
        # откатываемся ко всем результатам
        if len(filtered) > 0:
            results = filtered

    results = results[:top_k]

    logger.info("retrieve.done", place_id=place_id, passages_count=len(results))

    return {**state, "passages": results}
