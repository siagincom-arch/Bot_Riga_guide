"""
Узлы кэширования ответов в RAG-графе.

M11 — Оптимизация скорости ответа (Latency).
"""

from __future__ import annotations

import json
from typing import Any

from src.kb.store import KBStore
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.cache")


def _compute_cache_hash(state: dict[str, Any]) -> str:
    """Вычисляет хэш для кэширования запроса."""
    input_type = state.get("input_type", "")
    place_id = state.get("place_id", "")
    query = state.get("query", "").strip().lower()
    
    # Для followup запросов или когда есть история - кэшировать сложнее
    # В рамках M11 упростим: кэшируем только чистые запросы
    if state.get("session_history"):
        return ""
        
    if input_type == "photo" and place_id:
        return f"photo:{place_id}"
    elif input_type == "geo" and place_id:
        return f"geo:{place_id}"
    elif input_type == "text" and query:
        return f"text:{query}"
    
    return ""


async def check_cache(
    state: dict[str, Any],
    kb_store: KBStore,
) -> dict[str, Any]:
    """
    Узел проверки кэша (перед generate).
    Если находим ответ, сразу возвращаем summary/story и ставим status=ok.
    """
    cache_hash = _compute_cache_hash(state)
    if not cache_hash:
        return state
        
    logger.debug("check_cache.start", cache_hash=cache_hash)
    
    cached_str = kb_store.get_cache(cache_hash)
    if cached_str:
        try:
            cached_data = json.loads(cached_str)
            logger.info("check_cache.hit", cache_hash=cache_hash)
            return {
                **state,
                "summary": cached_data.get("summary", ""),
                "story": cached_data.get("story", ""),
                "raw_answer": cached_data.get("raw_answer", ""),
                "status": "ok",
                "cache_hit": True,
            }
        except Exception as e:
            logger.warning("check_cache.parse_error", error=str(e))
            
    return state


async def update_cache(
    state: dict[str, Any],
    kb_store: KBStore,
) -> dict[str, Any]:
    """
    Узел обновления кэша (после generate).
    Если генерация прошла успешно и кэш-хэш есть, сохраняем.
    """
    if state.get("status") in ("llm_error", "timeout") or state.get("cache_hit"):
        return state
        
    cache_hash = _compute_cache_hash(state)
    if not cache_hash:
        return state
        
    summary = state.get("summary", "")
    story = state.get("story", "")
    raw_answer = state.get("raw_answer", "")
    
    if summary and story:
        cached_data = {
            "summary": summary,
            "story": story,
            "raw_answer": raw_answer,
        }
        try:
            kb_store.set_cache(cache_hash, json.dumps(cached_data, ensure_ascii=False))
            logger.debug("update_cache.saved", cache_hash=cache_hash)
        except Exception as e:
            logger.warning("update_cache.error", error=str(e))
            
    return state
