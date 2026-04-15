"""
Geo Enrichment — обогащение Place координатами через Nominatim (OSM).

M7.2 — AG task.
ARCHITECTURE §5: ingest step — scrape → chunk → embed → store.

Если в YAML-источнике нет координат — пытаемся найти через Nominatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from src.telemetry.log import get_logger

logger = get_logger("ingest.geo")


@dataclass
class GeoResult:
    """Результат геокодирования."""
    lat: float
    lon: float
    display_name: str = ""
    source: str = "nominatim"


class GeoEnricher:
    """
    Геокодирование через Nominatim (OSM) — бесплатно, без API-ключа.

    Ограничения:
    - 1 req/sec (Nominatim usage policy).
    - Для 30 мест MVP — достаточно.
    """

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    HEADERS = {
        "User-Agent": "RigaGuideBot/0.1 (educational project; +https://github.com/riga-guide-bot)",
    }

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout

    async def geocode(self, name: str, city: str = "Riga") -> Optional[GeoResult]:
        """
        Геокодирует название объекта → координаты.

        Args:
            name: название (на русском или латышском).
            city: город для уточнения поиска.

        Returns:
            GeoResult или None, если не найдено.
        """
        query = f"{name}, {city}, Latvia"
        logger.info("geo.geocode", query=query)

        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=self._timeout,
            ) as client:
                response = await client.get(
                    self.NOMINATIM_URL,
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 1,
                        "addressdetails": 0,
                    },
                )
                response.raise_for_status()

            results = response.json()

            if not results:
                logger.warning("geo.not_found", query=query)
                return None

            first = results[0]
            geo = GeoResult(
                lat=float(first["lat"]),
                lon=float(first["lon"]),
                display_name=first.get("display_name", ""),
            )

            logger.info("geo.found", query=query, lat=geo.lat, lon=geo.lon)
            return geo

        except Exception as e:
            logger.error("geo.error", query=query, error=str(e))
            return None
