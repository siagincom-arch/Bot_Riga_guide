"""
RAG node: geo_nearby — поиск ближайших мест по координатам.

M5.2 — AG task.
TECH_SPEC §5.2: geo_nearby — {lat, lon} → list[place_id] (≤3, sorted by distance), timeout 1s.
"""

from __future__ import annotations

from typing import Any

from src.kb.store import KBStore
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.geo")


async def geo_nearby(
    state: dict[str, Any],
    kb_store: KBStore,
    radius_m: int = 300,
    limit: int = 3,
) -> dict[str, Any]:
    """
    Находит ближайшие места по координатам пользователя.

    Args:
        state: состояние графа, должно содержать lat и lon.
        kb_store: экземпляр KBStore.
        radius_m: радиус поиска в метрах (из config).
        limit: максимум результатов.

    Returns:
        Обновлённый state с полями:
        - nearby_places: list[dict] с place_id, name_ru, distance_m.
        - error: строка ошибки, если координаты отсутствуют.
    """
    lat = state.get("lat")
    lon = state.get("lon")

    if lat is None or lon is None:
        logger.warning("geo.no_coords")
        return {**state, "nearby_places": [], "error": "no_coordinates"}

    logger.info("geo.search", lat=lat, lon=lon, radius_m=radius_m)

    results = kb_store.geo_nearby(lat=lat, lon=lon, radius_m=radius_m, limit=limit)

    logger.info("geo.found", count=len(results))

    return {
        **state,
        "nearby_places": results,
        "error": None if results else "no_places_nearby",
    }
