"""
Интеграционные тесты для KBStore — реальный Chroma (tmp) + SQLite (tmp).

M3.7 — AG task.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.kb.models import City, Coords, Passage, PassageTopic, Place
from src.kb.store import KBStore, haversine_distance


# === Фикстуры: 3 тестовых места ===

def _make_dome_cathedral() -> tuple[Place, list[Passage], list[list[float]]]:
    """Домский собор — тестовое место #1."""
    place = Place(
        place_id="dome-cathedral-riga",
        name_ru="Домский собор",
        name_original="Rīgas Doms",
        aliases=["Домский", "Dome Cathedral"],
        city=City.RIGA,
        coords=Coords(lat=56.9496, lon=24.1040),
        categories=["church", "medieval"],
    )
    passages = [
        Passage(
            place_id="dome-cathedral-riga",
            text_ru="Домский собор — крупнейший средневековый собор Прибалтики, основанный в 1211 году.",
            topic=PassageTopic.HISTORY,
            source="https://ru.wikipedia.org/wiki/Домский_собор_(Рига)",
        ),
        Passage(
            place_id="dome-cathedral-riga",
            text_ru="Легенда гласит, что собор строили так долго, что первый архитектор не дожил до окончания.",
            topic=PassageTopic.LEGEND,
            source="https://latvia.travel",
        ),
    ]
    # Фейковые эмбеддинги (768-мерные)
    embeddings = [
        [0.1] * 768,
        [0.2] * 768,
    ]
    return place, passages, embeddings


def _make_freedom_monument() -> tuple[Place, list[Passage], list[list[float]]]:
    """Памятник Свободы — тестовое место #2."""
    place = Place(
        place_id="freedom-monument-riga",
        name_ru="Памятник Свободы",
        name_original="Brīvības piemineklis",
        city=City.RIGA,
        coords=Coords(lat=56.9515, lon=24.1134),
        categories=["monument", "art-deco"],
    )
    passages = [
        Passage(
            place_id="freedom-monument-riga",
            text_ru="Памятник Свободы — 42-метровая колонна, установленная в 1935 году.",
            topic=PassageTopic.FACT,
            source="https://ru.wikipedia.org/wiki/Памятник_Свободы",
        ),
    ]
    embeddings = [[0.3] * 768]
    return place, passages, embeddings


def _make_rundale_palace() -> tuple[Place, list[Passage], list[list[float]]]:
    """Рундальский дворец — тестовое место #3 (далеко от Риги)."""
    place = Place(
        place_id="rundale-palace",
        name_ru="Рундальский дворец",
        name_original="Rundāles pils",
        city=City.RUNDALE,
        coords=Coords(lat=56.4136, lon=24.0233),
        categories=["palace", "baroque"],
    )
    passages = [
        Passage(
            place_id="rundale-palace",
            text_ru="Рундальский дворец — шедевр барокко, построенный Растрелли для герцога Бирона.",
            topic=PassageTopic.ARCHITECTURE,
            source="https://rundale.net",
        ),
    ]
    embeddings = [[0.5] * 768]
    return place, passages, embeddings


@pytest.fixture
def store(tmp_path: Path) -> KBStore:
    """Создаёт KBStore с Chroma и SQLite во временной директории."""
    chroma = tmp_path / "chroma"
    sqlite = tmp_path / "test_kb.db"
    s = KBStore(chroma_path=chroma, sqlite_path=sqlite)
    yield s
    s.close()


@pytest.fixture
def populated_store(store: KBStore) -> KBStore:
    """Store с 3 предзагруженными местами."""
    for make_fn in [_make_dome_cathedral, _make_freedom_monument, _make_rundale_palace]:
        place, passages, embeddings = make_fn()
        store.upsert(place, passages, embeddings)
    return store


# === Тесты ===

class TestKBStoreUpsert:
    """Upsert: добавление и обновление мест."""

    def test_upsert_adds_passages(self, store: KBStore) -> None:
        """Upsert записывает passages в Chroma."""
        place, passages, embeddings = _make_dome_cathedral()
        count = store.upsert(place, passages, embeddings)
        assert count == 2
        assert store.count_passages() == 2

    def test_idempotent_upsert(self, store: KBStore) -> None:
        """Повторный upsert с теми же данными не дублирует записи."""
        place, passages, embeddings = _make_dome_cathedral()
        store.upsert(place, passages, embeddings)
        store.upsert(place, passages, embeddings)
        assert store.count_passages() == 2  # не 4

    def test_upsert_validates_lengths(self, store: KBStore) -> None:
        """Несовпадение числа passages и embeddings — ошибка."""
        place, passages, _ = _make_dome_cathedral()
        with pytest.raises(ValueError, match="≠"):
            store.upsert(place, passages, [[0.1] * 768])  # 2 passages, 1 embedding


class TestKBStoreSemanticSearch:
    """Semantic search через Chroma."""

    def test_search_returns_results(self, populated_store: KBStore) -> None:
        """Поиск по эмбеддингу возвращает результаты."""
        query_emb = [0.1] * 768  # близок к dome cathedral
        results = populated_store.semantic_search(query_emb, top_k=3)
        assert len(results) > 0
        assert "passage_id" in results[0]
        assert "text_ru" in results[0]
        assert "place_id" in results[0]

    def test_search_with_place_filter(self, populated_store: KBStore) -> None:
        """Фильтр по place_id ограничивает результаты."""
        query_emb = [0.15] * 768
        results = populated_store.semantic_search(
            query_emb, top_k=10, place_id="dome-cathedral-riga"
        )
        # Все результаты должны быть от Домского собора
        for r in results:
            assert r["place_id"] == "dome-cathedral-riga"


class TestKBStoreQueryByPlace:
    """Запрос passages по place_id (без эмбеддинга)."""

    def test_query_existing_place(self, populated_store: KBStore) -> None:
        """Запрос по place_id возвращает его passages."""
        results = populated_store.query_by_place("dome-cathedral-riga")
        assert len(results) == 2
        topics = {r["topic"] for r in results}
        assert "history" in topics
        assert "legend" in topics

    def test_query_nonexistent_place(self, populated_store: KBStore) -> None:
        """Запрос по несуществующему place_id → пустой список."""
        results = populated_store.query_by_place("nonexistent-place")
        assert results == []


class TestKBStoreGeoNearby:
    """Geo-поиск через Haversine."""

    def test_finds_nearby_places(self, populated_store: KBStore) -> None:
        """Поиск рядом с центром Риги находит рижские места."""
        results = populated_store.geo_nearby(
            lat=56.950, lon=24.110, radius_m=1000
        )
        # Домский собор и Памятник Свободы — оба в пределах 1 км от центра
        assert len(results) >= 1
        place_ids = {r["place_id"] for r in results}
        assert "dome-cathedral-riga" in place_ids or "freedom-monument-riga" in place_ids

    def test_excludes_far_places(self, populated_store: KBStore) -> None:
        """Рундале (~60 км от Риги) не попадает в радиус 1 км."""
        results = populated_store.geo_nearby(
            lat=56.950, lon=24.110, radius_m=1000
        )
        place_ids = {r["place_id"] for r in results}
        assert "rundale-palace" not in place_ids

    def test_sorted_by_distance(self, populated_store: KBStore) -> None:
        """Результаты отсортированы по расстоянию."""
        results = populated_store.geo_nearby(
            lat=56.950, lon=24.110, radius_m=5000
        )
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["distance_m"] <= results[i + 1]["distance_m"]

    def test_respects_limit(self, populated_store: KBStore) -> None:
        """Параметр limit ограничивает число результатов."""
        results = populated_store.geo_nearby(
            lat=56.950, lon=24.110, radius_m=5000, limit=1
        )
        assert len(results) <= 1


class TestKBStoreDelete:
    """Удаление мест."""

    def test_delete_removes_from_chroma_and_sqlite(self, populated_store: KBStore) -> None:
        """delete_place удаляет из обоих хранилищ."""
        initial_count = populated_store.count_passages()
        populated_store.delete_place("dome-cathedral-riga")

        # Passages удалены
        assert populated_store.count_passages() < initial_count

        # Geo-запрос не находит
        results = populated_store.query_by_place("dome-cathedral-riga")
        assert results == []

        geo = populated_store.geo_nearby(lat=56.9496, lon=24.1040, radius_m=100)
        place_ids = {r["place_id"] for r in geo}
        assert "dome-cathedral-riga" not in place_ids


class TestHaversineDistance:
    """Юнит-тесты для функции haversine_distance."""

    def test_zero_distance(self) -> None:
        """Одна и та же точка → 0 м."""
        d = haversine_distance(56.949, 24.104, 56.949, 24.104)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_known_distance_riga_center(self) -> None:
        """Домский собор → Памятник Свободы ≈ 700-800 м."""
        d = haversine_distance(56.9496, 24.1040, 56.9515, 24.1134)
        assert 500 < d < 1200  # грубая проверка

    def test_riga_to_rundale(self) -> None:
        """Рига → Рундале ≈ 60 км."""
        d = haversine_distance(56.9496, 24.1040, 56.4136, 24.0233)
        assert 55_000 < d < 65_000
