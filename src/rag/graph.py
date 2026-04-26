"""
Сборка RAG-графа на LangGraph.

M5.9 — Claude task.
TECH_SPEC §5, ARCHITECTURE §4: адаптивный RAG с условными переходами.

Маршрутизация:
- input_type=photo → vision → text_search → retrieve → grade → [web_search?] → generate → halluck → END
- input_type=geo   → geo_nearby → geo_select → retrieve → grade → [web_search?] → generate → halluck → END
- input_type=text  → text_search → retrieve → grade → [web_search?] → generate → halluck → END
- input_type=followup с place_id → retrieve → ... (минуя идентификацию)

Цикл halluck_check → generate активен до 1 повторной генерации (retry_count в state).
"""

from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

from src.kb.store import KBStore
from src.llm.tavily import TavilyClient
from src.rag.nodes.cache import check_cache, update_cache
from src.rag.nodes.generate import generate
from src.rag.nodes.geo import geo_nearby
from src.rag.nodes.grade import grade_context
from src.rag.nodes.retrieve import retrieve
from src.rag.nodes.text_search import text_search
from src.rag.nodes.vision import vision_identify
from src.rag.nodes.web_search import web_search
from src.rag.state import RAGState
from src.telemetry.log import get_logger

logger = get_logger("rag.graph")


# ---------- Router / utility nodes ----------


async def _entry(state: dict[str, Any]) -> dict[str, Any]:
    """Нулевой узел — нужен, чтобы повесить на него conditional edges."""
    return state


def _route_input(state: dict[str, Any]) -> str:
    """Маршрутизация по input_type → имя первого узла."""
    input_type = state.get("input_type")
    if input_type == "followup" and state.get("place_id"):
        return "retrieve"
    if input_type == "photo":
        return "vision"
    if input_type == "geo":
        return "geo_nearby"
    return "text_search"


def _after_vision(state: dict[str, Any]) -> str:
    """Если Vision не узнал — END. Иначе запускаем text_search (query=vision_name)."""
    if state.get("status") == "not_recognized":
        return "END"
    return "text_search"


def _after_text_search(state: dict[str, Any]) -> str:
    if state.get("status") == "not_recognized":
        return "END"
    return "retrieve"


async def _geo_select(state: dict[str, Any]) -> dict[str, Any]:
    """Post-geo: берём ближайшее место как основной place_id."""
    nearby = state.get("nearby_places") or []
    if not nearby:
        return {**state, "status": "out_of_coverage"}
    first = nearby[0]
    return {
        **state,
        "place_id": first.get("place_id"),
        "place_name": first.get("name_ru", ""),
    }


def _after_geo(state: dict[str, Any]) -> str:
    if state.get("status") == "out_of_coverage":
        return "END"
    return "retrieve"


def _after_grade(state: dict[str, Any]) -> str:
    """Если KB-контекста хватает — к check_cache, иначе web_search."""
    return "check_cache" if state.get("grade_sufficient") else "web_search"


def _after_check_cache(state: dict[str, Any]) -> str:
    """Если нашли в кэше — в END. Иначе — в generate."""
    if state.get("cache_hit"):
        return "END"
    return "generate"


# ---------- Build ----------


def build_graph(
    *,
    kb_store: KBStore,
    gemini_client: Any,
    tavily_client: TavilyClient,
    config: dict[str, Any] | None = None,
) -> Any:
    """
    Компилирует RAG-граф.

    Dependency injection через functools.partial — узлы видят только state.

    Args:
        kb_store: инициализированный KBStore (Chroma + SQLite).
        gemini_client: клиент с методами generate/vision/embed_query.
        tavily_client: клиент веб-поиска.
        config: опциональные пороги (vision_threshold, grade_threshold, top_k,
                nearby_radius_m).

    Returns:
        Скомпилированный LangGraph, вызывается через `.ainvoke(state)`.
    """
    cfg = config or {}

    g = StateGraph(RAGState)

    # --- Узлы ---
    g.add_node("entry", _entry)
    g.add_node(
        "vision",
        partial(
            vision_identify,
            gemini_client=gemini_client,
            confidence_threshold=cfg.get("vision_threshold", 0.5),
        ),
    )
    g.add_node(
        "text_search",
        partial(text_search, kb_store=kb_store, gemini_client=gemini_client),
    )
    g.add_node(
        "geo_nearby",
        partial(
            geo_nearby,
            kb_store=kb_store,
            radius_m=cfg.get("nearby_radius_m", 300),
        ),
    )
    g.add_node("geo_select", _geo_select)
    g.add_node(
        "retrieve",
        partial(retrieve, kb_store=kb_store, top_k=cfg.get("top_k", 6)),
    )
    g.add_node(
        "grade",
        partial(grade_context, threshold=cfg.get("grade_threshold", 0.6)),
    )
    g.add_node("web_search", partial(web_search, tavily_client=tavily_client))
    g.add_node("check_cache", partial(check_cache, kb_store=kb_store))
    g.add_node("generate", partial(generate, gemini_client=gemini_client))
    g.add_node("update_cache", partial(update_cache, kb_store=kb_store))

    # --- Рёбра ---
    g.set_entry_point("entry")

    g.add_conditional_edges(
        "entry",
        _route_input,
        {
            "vision": "vision",
            "geo_nearby": "geo_nearby",
            "text_search": "text_search",
            "retrieve": "retrieve",
        },
    )

    g.add_conditional_edges(
        "vision",
        _after_vision,
        {"text_search": "text_search", "END": END},
    )

    g.add_conditional_edges(
        "text_search",
        _after_text_search,
        {"retrieve": "retrieve", "END": END},
    )

    g.add_edge("geo_nearby", "geo_select")
    g.add_conditional_edges(
        "geo_select",
        _after_geo,
        {"retrieve": "retrieve", "END": END},
    )

    g.add_edge("retrieve", "grade")

    g.add_conditional_edges(
        "grade",
        _after_grade,
        {"check_cache": "check_cache", "web_search": "web_search"},
    )

    g.add_edge("web_search", "check_cache")
    
    g.add_conditional_edges(
        "check_cache",
        _after_check_cache,
        {"generate": "generate", "END": END},
    )

    g.add_edge("generate", "update_cache")
    g.add_edge("update_cache", END)

    return g.compile()


async def _curate_web_fact(state: dict[str, Any]) -> None:
    place_id = state.get("place_id")
    answer = state.get("answer")
    if not place_id or not answer:
        return
        
    from src.config import settings
    from src.kb.store import KBStore
    from src.kb.models import Passage, PassageTopic
    
    if settings is None:
        return
        
    try:
        kb_store = KBStore(chroma_path=settings.CHROMA_PATH, sqlite_path=settings.SQLITE_PATH)
        passage = Passage(
            place_id=place_id,
            text_ru=answer,
            topic=PassageTopic.FACT,
            source="web_fact"
        )
        import asyncio
        await asyncio.to_thread(kb_store.append_passages, place_id, [passage])
        logger.info("web_search_loopback.saved", place_id=place_id)
    except Exception as e:
        logger.error("web_search_loopback.error", error=str(e))

async def run_rag(graph: Any, initial_state: dict[str, Any]) -> dict[str, Any]:
    """Раннер графа. Гарантирует status='ok' в успехе."""
    result = await graph.ainvoke(initial_state)
    if not result.get("status"):
        result = {**result, "status": "ok"}
        
    if result.get("web_search_used"):
        import asyncio
        asyncio.create_task(_curate_web_fact(result))
        
    return result
