"""
Типизированное состояние RAG-графа.

M5 — Claude task.
TypedDict вместо dataclass — требование LangGraph для MergeableState.
Используется во всех узлах (vision, text_search, grade, generate, halluck_check)
и сборке в graph.py.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


InputType = Literal["photo", "geo", "text", "followup"]
Status = Literal[
    "ok",
    "not_recognized",
    "no_kb",
    "llm_error",
    "timeout",
    "out_of_coverage",
]


class RAGState(TypedDict, total=False):
    """
    Состояние, которое протекает через граф.

    `total=False` — все поля опциональны; каждый узел добавляет свои.
    """

    # --- Вход ---
    input_type: InputType
    query: str              # для text; также заполняется vision'ом для photo
    image_bytes: bytes       # для photo
    lat: float               # для geo
    lon: float
    chat_id: int

    # --- После vision ---
    vision_name: str         # name_ru от Gemini Vision
    vision_confidence: float

    # --- После text_search ---
    place_id: Optional[str]
    place_name: Optional[str]
    candidates: list[dict]   # для clarifier (несколько близких совпадений)
    query_embedding: list[float]  # эмбеддинг запроса для retrieve

    # --- После geo ---
    nearby_places: list[dict]

    # --- После retrieve / web_search ---
    passages: list[dict]     # [{passage_id, text_ru, topic, source, place_id, ...}]
    web_search_used: bool

    # --- После grade ---
    grade_sufficient: bool
    grade_score: float

    # --- После check_cache ---
    cache_hit: bool

    # --- Стриминг ---
    stream_callback: Any

    # --- После generate ---
    summary: str             # 2–3 предложения
    story: str               # 7–8 предложений
    raw_answer: str          # сырой ответ LLM до парсинга

    # --- Сессия ---
    session_history: list[dict]  # [{role, text}, ...]

    # --- Итог ---
    status: Status
    error: Optional[str]
