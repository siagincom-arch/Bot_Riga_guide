"""
RAG node: text_search — поиск place_id по свободному тексту.

M5.3 — Claude task.
TECH_SPEC §5.2: text_search — {query} → {place_id, candidates?}, timeout 2 s.

Комбинирует Chroma semantic search и rapidfuzz по name_ru (ARCHITECTURE ADR-7).
rapidfuzz ловит транслит и опечатки, которые embeddings плохо обрабатывают для
славянских названий.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Protocol

from rapidfuzz import fuzz, process

from src.kb.store import KBStore
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.text_search")


# Порог косинусной дистанции Chroma: чем меньше, тем ближе.
# 0.20 — строгое совпадение, 0.5 — приемлемое, > 0.5 — шум.
_DISTANCE_STRICT = 0.20
_DISTANCE_ACCEPTABLE = 0.50

# Пороги rapidfuzz (0..100): 90 = почти точное, 75 = хорошее.
_FUZZ_STRONG = 90
_FUZZ_ACCEPTABLE = 75


class _EmbedQueryCapable(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


async def text_search(
    state: dict[str, Any],
    *,
    kb_store: KBStore,
    gemini_client: _EmbedQueryCapable,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Находит место по тексту пользовательского запроса.

    Логика:
    1. Пробуем Chroma semantic search. Если top-1 дистанция < 0.20 → берём его.
    2. Иначе пробуем rapidfuzz по name_ru из таблицы place_coords.
       Если score >= 90 → берём.
    3. Если semantic top-1 < 0.50 или fuzz >= 75 → возвращаем как
       основной вариант, но если оба топ-2 близки по качеству — candidates
       для clarifier.
    4. Иначе — status = "not_recognized".

    Returns:
        state с place_id, place_name, candidates (если неоднозначно),
        или status="not_recognized".
    """
    query = (state.get("query") or "").strip()
    if not query:
        logger.warning("text_search.empty_query")
        return {**state, "status": "not_recognized", "error": "empty_query"}

    logger.info("text_search.start", query=query[:100])

    # --- 1. Semantic search через Chroma ---
    semantic_hit: dict | None = None
    try:
        embedding = await gemini_client.embed_query(query)
        results = kb_store.semantic_search(query_embedding=embedding, top_k=top_k)
        if results:
            semantic_hit = results[0]
    except Exception as exc:
        logger.warning("text_search.semantic_failed", error=repr(exc))

    # --- 2. Fuzzy fallback по name_ru ---
    fuzz_hit = _fuzzy_place_lookup(kb_store, query)

    # --- 3. Решаем, какой вариант выбрать ---
    chosen = _choose_match(semantic_hit, fuzz_hit)
    if chosen is None:
        logger.info("text_search.not_found", query=query[:100])
        return {**state, "status": "not_recognized"}

    place_id = chosen["place_id"]
    place_name = chosen.get("name_ru") or ""

    # Candidates для clarifier: если semantic top-2 близки друг к другу по score
    candidates: list[dict] = []
    if semantic_hit and isinstance(results, list) and len(results) >= 2:
        d0, d1 = results[0]["distance"], results[1]["distance"]
        if d1 - d0 < 0.05 and d1 < _DISTANCE_ACCEPTABLE:
            # Показать пользователю выбор из 2-3 близких мест
            candidates = [
                {"place_id": r.get("place_id", ""), "text_ru": r.get("text_ru", "")[:80]}
                for r in results[:3]
            ]

    logger.info(
        "text_search.resolved",
        place_id=place_id,
        via=chosen.get("_via"),
        candidates_count=len(candidates),
    )

    return {
        **state,
        "place_id": place_id,
        "place_name": place_name,
        "candidates": candidates,
    }


def _choose_match(semantic: dict | None, fuzz_match: dict | None) -> dict | None:
    """Выбирает лучший кандидат из semantic и fuzzy результатов."""
    sem_ok = (
        semantic is not None
        and semantic.get("distance", 99) < _DISTANCE_ACCEPTABLE
        and semantic.get("place_id")
    )
    fuzz_ok = (
        fuzz_match is not None
        and fuzz_match.get("score", 0) >= _FUZZ_ACCEPTABLE
    )

    if not sem_ok and not fuzz_ok:
        return None

    # Приоритет: если оба согласны (одинаковый place_id) — берём fuzz_match,
    # у него есть name_ru. Иначе — тот, что уверенней.
    if sem_ok and fuzz_ok and semantic["place_id"] == fuzz_match["place_id"]:
        return {**fuzz_match, "_via": "both"}

    if sem_ok and semantic.get("distance", 99) < _DISTANCE_STRICT:
        return {**semantic, "_via": "semantic_strict"}

    if fuzz_ok and fuzz_match.get("score", 0) >= _FUZZ_STRONG:
        return {**fuzz_match, "_via": "fuzz_strong"}

    # Оба посредственные — берём semantic, он учитывает смысл
    if sem_ok:
        return {**semantic, "_via": "semantic_acceptable"}

    return {**fuzz_match, "_via": "fuzz_acceptable"} if fuzz_ok else None


def _fuzzy_place_lookup(kb_store: KBStore, query: str) -> dict | None:
    """
    Ищет место по name_ru через rapidfuzz.

    Читаем все (place_id, name_ru) из place_coords — для MVP (150-300 мест)
    это дешёвая операция в памяти.
    """
    try:
        rows = kb_store._sqlite_conn.execute(
            "SELECT place_id, name_ru FROM place_coords"
        ).fetchall()
    except sqlite3.Error as exc:
        logger.warning("text_search.sqlite_failed", error=repr(exc))
        return None

    if not rows:
        return None

    by_name = {name: place_id for place_id, name in rows}
    best = process.extractOne(query, by_name.keys(), scorer=fuzz.WRatio)
    if best is None:
        return None

    name, score, _ = best
    return {"place_id": by_name[name], "name_ru": name, "score": score}
