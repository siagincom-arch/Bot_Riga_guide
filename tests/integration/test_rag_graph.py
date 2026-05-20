"""
Интеграционный тест RAG-графа: вход → граф → {summary, story, place_id}.

M5.10 — Claude task.
Проверяет сборку LangGraph: маршрутизацию по input_type, цепочку узлов,
условные переходы grade→web_search.

KBStore здесь — lightweight фейк (_FakeKBStore), т.к. проверяем проводку
графа, а не хранилище (это делает tests/integration/test_kb.py).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from src.rag.graph import build_graph, run_rag
from tests.fixtures.fake_gemini import (
    FakeGeminiClient,
    FakeTavilyClient,
    fake_gemini_with_generate,
)


# === Фикстура: 3 тестовых места ===

_PLACES: list[dict[str, Any]] = [
    {
        "place_id": "dome-cathedral",
        "name_ru": "Домский собор",
        "lat": 56.9496,
        "lon": 24.1040,
        "passages": [
            {
                "passage_id": "p1",
                "place_id": "dome-cathedral",
                "text_ru": "Домский собор основан в 1211 году, крупнейший в Прибалтике.",
                "topic": "history",
                "source": "wiki",
            },
            {
                "passage_id": "p2",
                "place_id": "dome-cathedral",
                "text_ru": "Орган собора насчитывает почти семь тысяч труб.",
                "topic": "fact",
                "source": "wiki",
            },
            {
                "passage_id": "p3",
                "place_id": "dome-cathedral",
                "text_ru": "По легенде, первый архитектор не дожил до окончания стройки.",
                "topic": "legend",
                "source": "wiki",
            },
        ],
    },
    {
        "place_id": "black-heads",
        "name_ru": "Дом Черноголовых",
        "lat": 56.9476,
        "lon": 24.1060,
        "passages": [
            {
                "passage_id": "b1",
                "place_id": "black-heads",
                "text_ru": "Дом Черноголовых — купеческий дом братства, восстановлен в 2000 году.",
                "topic": "history",
                "source": "wiki",
            },
            {
                "passage_id": "b2",
                "place_id": "black-heads",
                "text_ru": "Фасад украшен статуями и астрономическими часами.",
                "topic": "fact",
                "source": "wiki",
            },
        ],
    },
    {
        "place_id": "riga-castle",
        "name_ru": "Рижский замок",
        "lat": 56.9509,
        "lon": 24.0997,
        "passages": [
            {
                "passage_id": "r1",
                "place_id": "riga-castle",
                "text_ru": "Рижский замок — резиденция президента Латвии.",
                "topic": "fact",
                "source": "wiki",
            },
        ],
    },
]


class _FakeKBStore:
    """
    Минимальный фейк KBStore для проверки графа.
    Реализует только методы, которые вызывают узлы.
    """

    def __init__(self, places: list[dict[str, Any]]) -> None:
        self._places = places
        self._by_id = {p["place_id"]: p for p in places}
        # in-memory sqlite для rapidfuzz fallback в text_search
        self._sqlite_conn = sqlite3.connect(":memory:")
        self._sqlite_conn.execute(
            "CREATE TABLE place_coords (place_id TEXT PRIMARY KEY, name_ru TEXT, lat REAL, lon REAL)"
        )
        self._sqlite_conn.executemany(
            "INSERT INTO place_coords VALUES (?, ?, ?, ?)",
            [(p["place_id"], p["name_ru"], p["lat"], p["lon"]) for p in places],
        )
        self._sqlite_conn.commit()
        self._cache = {}

    def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 6,
        place_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Простая заглушка: возвращаем первое место с дистанцией 0.2 (проходит strict).
        # Этого достаточно, чтобы text_search вернул место без опоры на fuzz.
        pid = place_id if place_id else self._places[0]["place_id"]
        place = self._by_id.get(pid, self._places[0])
        return [
            {
                "place_id": place["place_id"],
                "name_ru": place["name_ru"],
                "text_ru": place["passages"][0]["text_ru"],
                "distance": 0.2,
            }
        ]

    def query_by_place(
        self, *, place_id: str, top_k: int = 6
    ) -> list[dict[str, Any]]:
        place = self._by_id.get(place_id)
        if not place:
            return []
        return list(place["passages"])[:top_k]

    def geo_nearby(
        self, *, lat: float, lon: float, radius_m: int = 300, limit: int = 3
    ) -> list[dict[str, Any]]:
        # Для теста возвращаем Дом Черноголовых как ближайший
        return [
            {
                "place_id": "black-heads",
                "name_ru": "Дом Черноголовых",
                "distance_m": 120,
            }
        ]

    def get_cache(self, query_hash: str) -> str | None:
        return self._cache.get(query_hash)

    def set_cache(self, query_hash: str, response_json: str) -> None:
        self._cache[query_hash] = response_json


# === Тесты ===


@pytest.mark.asyncio
async def test_graph_text_query_returns_answer() -> None:
    """Текстовый запрос: text_search → retrieve → grade → generate → halluck → END."""
    kb = _FakeKBStore(_PLACES)
    gemini = FakeGeminiClient(
        vision_routing={},
    )
    call_count = {"n": 0}
    def fn(prompt: str) -> str:
        call_count["n"] += 1
        return (
            "Домский собор — крупнейший средневековый храм Прибалтики.\n"
            "\n"
            "Он стоит здесь с XIII века и видел всё: купцов, орган и пожары. "
            "Внутри — орган почти в семь тысяч труб. "
            "Легенда говорит, что первый архитектор не дожил до конца стройки. "
            "Но стены помнят его чертежи. "
            "Зимой здесь играют органные концерты. "
            "Акустика такая, что мурашки. "
            "Сюда приходят не только молиться, но и слушать. "
            "И каждый слышит что-то своё."
        )

    gemini = fake_gemini_with_generate(fn)
    tavily = FakeTavilyClient()

    graph = build_graph(
        kb_store=kb,  # type: ignore[arg-type]
        gemini_client=gemini,
        tavily_client=tavily,  # type: ignore[arg-type]
    )

    result = await run_rag(
        graph,
        {
            "input_type": "text",
            "query": "Домский собор",
            "chat_id": 1,
        },
    )

    assert result["place_id"] == "dome-cathedral"
    assert result["summary"], "summary должен быть непустым"
    assert result["story"], "story должен быть непустым"
    assert result.get("status") == "ok"


@pytest.mark.asyncio
async def test_graph_geo_query_uses_nearby() -> None:
    """Гео-запрос: geo_nearby → geo_select → retrieve → generate → END."""
    kb = _FakeKBStore(_PLACES)

    def fn(prompt: str) -> str:
        return (
            "Дом Черноголовых — купеческий дом, восстановленный в 2000 году.\n"
            "\n"
            "Он стоял в сердце Старого города много веков. "
            "Братство моряков собиралось здесь после плаваний. "
            "Фасад украшают статуи и часы. "
            "В войну дом был разрушен. "
            "Горожане долго спорили, стоит ли его восстанавливать. "
            "Восстановили — и не пожалели. "
            "Теперь здесь концерты и приёмы. "
            "И снова слышны шаги купцов."
        )

    gemini = fake_gemini_with_generate(fn)
    tavily = FakeTavilyClient()

    graph = build_graph(
        kb_store=kb,  # type: ignore[arg-type]
        gemini_client=gemini,
        tavily_client=tavily,  # type: ignore[arg-type]
    )

    result = await run_rag(
        graph,
        {
            "input_type": "geo",
            "lat": 56.9476,
            "lon": 24.1060,
            "chat_id": 2,
        },
    )

    assert result["place_id"] == "black-heads"
    assert result["summary"]
    assert result["story"]


@pytest.mark.asyncio
async def test_graph_photo_flow_recognized() -> None:
    """Фото: vision (узнал) → text_search → retrieve → generate → END."""
    kb = _FakeKBStore(_PLACES)

    vision_json = json.dumps(
        {"name_ru": "Домский собор", "confidence": 0.9, "why": "стиль"},
        ensure_ascii=False,
    )

    def fn(prompt: str) -> str:
        return (
            "Это Домский собор — визитка средневековой Риги.\n"
            "\n"
            "Храм XIII века вырос на берегу Даугавы. "
            "Его орган — один из крупнейших в Европе. "
            "Легенда о первом архитекторе до сих пор ходит. "
            "Здесь венчались, молились, прощались. "
            "В советское время он был музеем. "
            "Потом — снова храмом. "
            "Под сводами репетируют хоры. "
            "И каждый звук остаётся надолго."
        )

    gemini = fake_gemini_with_generate(fn)
    gemini._vision_response = vision_json  # noqa: SLF001
    tavily = FakeTavilyClient()

    graph = build_graph(
        kb_store=kb,  # type: ignore[arg-type]
        gemini_client=gemini,
        tavily_client=tavily,  # type: ignore[arg-type]
    )

    result = await run_rag(
        graph,
        {
            "input_type": "photo",
            "image_bytes": b"fake-jpg-bytes",
            "chat_id": 3,
        },
    )

    assert result.get("vision_name") == "Домский собор"
    assert result["place_id"] == "dome-cathedral"
    assert result["summary"]


@pytest.mark.asyncio
async def test_graph_photo_not_recognized_exits_early() -> None:
    """Фото с низким confidence → status=not_recognized, без retrieve/generate."""
    kb = _FakeKBStore(_PLACES)

    vision_json = json.dumps(
        {"name_ru": "", "confidence": 0.1, "why": "не Латвия"},
        ensure_ascii=False,
    )
    gemini = FakeGeminiClient(vision_response=vision_json)
    tavily = FakeTavilyClient()

    graph = build_graph(
        kb_store=kb,  # type: ignore[arg-type]
        gemini_client=gemini,
        tavily_client=tavily,  # type: ignore[arg-type]
    )

    result = await run_rag(
        graph,
        {
            "input_type": "photo",
            "image_bytes": b"unknown",
            "chat_id": 4,
        },
    )

    assert result.get("status") == "not_recognized"
    assert not result.get("place_id")
    assert not result.get("summary")
