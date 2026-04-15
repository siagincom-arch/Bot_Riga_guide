"""
Lazy-инициализация RAG-графа и его зависимостей как процесс-уровневых синглтонов.

Блок B — Claude task.
Нужен в двух местах:
- `src/bot/gateway.py` — хендлеры зовут `get_rag_graph()` при первом входящем сообщении.
- `scripts/run_hitl.py` — HITL-runner зовёт тот же граф.

Единая точка сборки гарантирует, что Chroma и Gemini-клиент создаются ровно один раз
на процесс (TECH_SPEC §15.1: «Single Python process»).
"""

from __future__ import annotations

from typing import Any, Optional

from src.config import settings
from src.kb.store import KBStore
from src.llm.gemini import GeminiClient
from src.llm.tavily import TavilyClient
from src.rag.graph import build_graph, run_rag as _run_rag
from src.telemetry.log import get_logger

logger = get_logger("rag.singleton")


# --- Процесс-уровневый кеш ---
_kb_store: Optional[KBStore] = None
_gemini_client: Optional[GeminiClient] = None
_tavily_client: Optional[TavilyClient] = None
_graph: Any = None


def _get_settings() -> Any:
    if settings is None:
        raise RuntimeError(
            "Settings не загружены — проверь .env и src.config.settings"
        )
    return settings


def get_kb_store() -> KBStore:
    global _kb_store
    if _kb_store is None:
        s = _get_settings()
        _kb_store = KBStore(chroma_path=s.CHROMA_PATH, sqlite_path=s.SQLITE_PATH)
        logger.info("kb_store.init", chroma=str(s.CHROMA_PATH), sqlite=str(s.SQLITE_PATH))
    return _kb_store


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        s = _get_settings()
        _gemini_client = GeminiClient(api_key=s.GEMINI_API_KEY.get_secret_value())
        logger.info("gemini_client.init")
    return _gemini_client


def get_tavily_client() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        s = _get_settings()
        _tavily_client = TavilyClient(api_key=s.TAVILY_API_KEY.get_secret_value())
        logger.info("tavily_client.init")
    return _tavily_client


def get_rag_graph() -> Any:
    """
    Скомпилированный LangGraph. Lazy init — собирается при первом вызове.

    Конфиг берётся из `settings` (пороги, top_k, nearby radius).
    """
    global _graph
    if _graph is None:
        s = _get_settings()
        _graph = build_graph(
            kb_store=get_kb_store(),
            gemini_client=get_gemini_client(),
            tavily_client=get_tavily_client(),
            config={
                "vision_threshold": s.VISION_CONFIDENCE_THRESHOLD,
                "grade_threshold": s.RAG_GRADE_THRESHOLD,
                "top_k": s.RAG_TOP_K,
                "nearby_radius_m": s.NEARBY_RADIUS_M,
            },
        )
        logger.info("rag_graph.compiled")
    return _graph


async def run_rag(initial_state: dict[str, Any]) -> dict[str, Any]:
    """Удобный хелпер: берёт граф-синглтон и прогоняет состояние."""
    return await _run_rag(get_rag_graph(), initial_state)


def reset_cache() -> None:
    """Сбросить все синглтоны (для тестов и graceful reload)."""
    global _kb_store, _gemini_client, _tavily_client, _graph
    _kb_store = None
    _gemini_client = None
    _tavily_client = None
    _graph = None
    logger.info("singleton.reset")
