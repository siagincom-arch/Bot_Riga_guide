"""
Knowledge Base Store — обёртка над Chroma + SQLite (place_coords).

TECH_SPEC §7, ARCHITECTURE §4:
- Chroma collection `places_ru` для векторного поиска.
- SQLite таблица `place_coords` для Haversine geo-запросов.
- Идемпотентный upsert через passage_id.

Использование:
    store = KBStore(chroma_path="./data/chroma", sqlite_path="./data/bot.db")
    store.upsert(place, passages)
    results = store.semantic_search("Домский собор", top_k=6)
    nearby = store.geo_nearby(lat=56.949, lon=24.105, radius_m=300)
"""

from __future__ import annotations

import math
import json
import sqlite3
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.kb.models import Coords, Passage, PassageTopic, Place


# SQL для создания таблицы координат
_CREATE_PLACE_COORDS = """
CREATE TABLE IF NOT EXISTS place_coords (
    place_id   TEXT PRIMARY KEY,
    name_ru    TEXT NOT NULL,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    city       TEXT NOT NULL DEFAULT 'riga'
);
"""

# Радиус Земли в метрах (для Haversine)
_EARTH_RADIUS_M = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Расстояние между двумя точками на Земле в метрах (Haversine formula).

    Args:
        lat1, lon1: координаты первой точки (градусы).
        lat2, lon2: координаты второй точки (градусы).

    Returns:
        Расстояние в метрах.
    """
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _EARTH_RADIUS_M * c


class KBStore:
    """
    Обёртка над Chroma (vector) + SQLite (geo).

    Один экземпляр на процесс (MVP).
    """

    COLLECTION_NAME = "places_ru"

    def __init__(self, chroma_path: str | Path, sqlite_path: str | Path) -> None:
        self._chroma_path = str(chroma_path)
        self._sqlite_path = str(sqlite_path)

        # Chroma client (persistent)
        Path(self._chroma_path).mkdir(parents=True, exist_ok=True)
        self._chroma_client = chromadb.PersistentClient(
            path=self._chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Riga Guide Bot — places KB"},
        )

        # SQLite для geo-координат
        Path(self._sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(self._sqlite_path, check_same_thread=False)
        self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
        self._sqlite_conn.execute(_CREATE_PLACE_COORDS)
        self._sqlite_conn.commit()

    def upsert(self, place: Place, passages: list[Passage], embeddings: list[list[float]]) -> int:
        """
        Добавляет или обновляет место и его чанки.

        Args:
            place: модель Place.
            passages: список Passage для этого места.
            embeddings: вектора эмбеддингов (по одному на passage).

        Returns:
            Число добавленных/обновлённых чанков.
        """
        if len(passages) != len(embeddings):
            raise ValueError(
                f"Число passages ({len(passages)}) ≠ числу embeddings ({len(embeddings)})"
            )

        # Upsert в Chroma
        if passages:
            self._collection.upsert(
                ids=[p.passage_id for p in passages],
                documents=[p.text_ru for p in passages],
                embeddings=embeddings,
                metadatas=[
                    {
                        "place_id": p.place_id,
                        "topic": p.topic.value,
                        "source": p.source,
                    }
                    for p in passages
                ],
            )

        # Upsert координаты в SQLite (если есть)
        if place.coords:
            self._sqlite_conn.execute(
                """
                INSERT INTO place_coords (place_id, name_ru, lat, lon, city)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(place_id) DO UPDATE SET
                    name_ru = excluded.name_ru,
                    lat = excluded.lat,
                    lon = excluded.lon,
                    city = excluded.city
                """,
                (place.place_id, place.name_ru, place.coords.lat, place.coords.lon, place.city.value),
            )
            self._sqlite_conn.commit()

        return len(passages)

    def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 6,
        place_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Векторный поиск по Chroma.

        Args:
            query_embedding: эмбеддинг запроса.
            top_k: число результатов.
            place_id: если задан — фильтрация по конкретному месту.

        Returns:
            Список dict с полями: passage_id, text_ru, topic, source, place_id, distance.
        """
        where = {"place_id": place_id} if place_id else None

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        items = []
        if results["ids"] and results["ids"][0]:
            for i, pid in enumerate(results["ids"][0]):
                items.append({
                    "passage_id": pid,
                    "text_ru": results["documents"][0][i] if results["documents"] else "",
                    "topic": results["metadatas"][0][i].get("topic", "") if results["metadatas"] else "",
                    "source": results["metadatas"][0][i].get("source", "") if results["metadatas"] else "",
                    "place_id": results["metadatas"][0][i].get("place_id", "") if results["metadatas"] else "",
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })

        return items

    def query_by_place(self, place_id: str, top_k: int = 6) -> list[dict]:
        """
        Получает все passages для конкретного места (без эмбеддинга запроса).

        Использует Chroma get с фильтром.
        """
        results = self._collection.get(
            where={"place_id": place_id},
            limit=top_k,
            include=["documents", "metadatas"],
        )

        items = []
        if results["ids"]:
            for i, pid in enumerate(results["ids"]):
                items.append({
                    "passage_id": pid,
                    "text_ru": results["documents"][i] if results["documents"] else "",
                    "topic": results["metadatas"][i].get("topic", "") if results["metadatas"] else "",
                    "source": results["metadatas"][i].get("source", "") if results["metadatas"] else "",
                    "place_id": results["metadatas"][i].get("place_id", "") if results["metadatas"] else "",
                })

        return items

    def geo_nearby(
        self,
        lat: float,
        lon: float,
        radius_m: int = 300,
        limit: int = 3,
    ) -> list[dict]:
        """
        Находит ближайшие места в радиусе (Haversine, TECH_SPEC §5.2 geo_nearby).

        Args:
            lat, lon: координаты запроса.
            radius_m: радиус поиска в метрах.
            limit: максимум результатов.

        Returns:
            Список dict с полями: place_id, name_ru, lat, lon, distance_m — отсортирован по distance.
        """
        # Грубый фильтр по bbox (для ускорения — не сканируем всю планету)
        # 1 градус ≈ 111 км, radius_m/111000 даёт грубую дельту
        delta_deg = radius_m / 111_000 + 0.01  # запас

        rows = self._sqlite_conn.execute(
            """
            SELECT place_id, name_ru, lat, lon
            FROM place_coords
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
            """,
            (lat - delta_deg, lat + delta_deg, lon - delta_deg, lon + delta_deg),
        ).fetchall()

        # Точный Haversine-фильтр
        candidates = []
        for row in rows:
            pid, name, plat, plon = row
            dist = haversine_distance(lat, lon, plat, plon)
            if dist <= radius_m:
                candidates.append({
                    "place_id": pid,
                    "name_ru": name,
                    "lat": plat,
                    "lon": plon,
                    "distance_m": round(dist, 1),
                })

        # Сортировка по расстоянию, обрезка до limit
        candidates.sort(key=lambda x: x["distance_m"])
        return candidates[:limit]

    def delete_place(self, place_id: str) -> None:
        """Удаляет место из Chroma и SQLite."""
        # Удаляем passages из Chroma
        try:
            existing = self._collection.get(where={"place_id": place_id})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:
            pass

        # Удаляем из SQLite
        self._sqlite_conn.execute(
            "DELETE FROM place_coords WHERE place_id = ?", (place_id,)
        )
        self._sqlite_conn.commit()

    def count_passages(self) -> int:
        """Общее число passages в Chroma."""
        return self._collection.count()

    def close(self) -> None:
        """Закрывает SQLite соединение."""
        self._sqlite_conn.close()
