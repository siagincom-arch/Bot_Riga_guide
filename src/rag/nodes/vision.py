"""
RAG node: vision_identify — распознавание достопримечательности по фото.

M5.1 — Claude task.
TECH_SPEC §5.2: vision_identify — {image_bytes} → {name, confidence, place_id?}, timeout 8 s.

Использует Gemini Vision с промптом из vision.j2.
Не делает lookup в KB — это работа text_search с query=vision_name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader

from src.llm.retry import with_vision_retry
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.vision")


class _VisionCapable(Protocol):
    async def vision(self, image_bytes: bytes, prompt: str) -> str: ...


_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    keep_trailing_newline=True,
)


def _parse_vision_json(raw: str) -> dict[str, Any]:
    """
    Парсит ответ Gemini Vision в dict. Устойчив к markdown-обёрткам.

    Возвращает {} при полностью невалидном JSON — тогда узел пометит
    состояние как not_recognized.
    """
    text = raw.strip()
    # Снимаем ```json ... ``` или ``` ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logger.warning("vision.parse.json_invalid", raw_preview=text[:200])
        return {}


async def vision_identify(
    state: dict[str, Any],
    *,
    gemini_client: _VisionCapable,
    confidence_threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Определяет название места на фото.

    Args:
        state: RAGState — должен содержать `image_bytes`.
        gemini_client: GeminiClient с методом vision(bytes, prompt).
        confidence_threshold: порог ниже которого считаем «не распознано».

    Returns:
        Обновлённый state с полями:
        - vision_name, vision_confidence
        - query (= vision_name, чтобы следующий узел text_search подхватил)
        - status = "not_recognized" если confidence < threshold
    """
    image_bytes = state.get("image_bytes")
    if not image_bytes:
        logger.warning("vision.no_image")
        return {**state, "status": "not_recognized", "error": "no_image"}

    prompt = _jinja_env.get_template("vision.j2").render()
    logger.info("vision.start", image_size=len(image_bytes))

    try:
        raw = await with_vision_retry(lambda: gemini_client.vision(image_bytes, prompt))
    except Exception as exc:
        logger.error("vision.llm_error", error=repr(exc))
        return {**state, "status": "llm_error", "error": repr(exc)}

    parsed = _parse_vision_json(raw)
    name_ru = (parsed.get("name_ru") or "").strip()
    confidence = float(parsed.get("confidence") or 0.0)

    logger.info("vision.result", name_ru=name_ru, confidence=confidence)

    if not name_ru or confidence < confidence_threshold:
        return {
            **state,
            "vision_name": name_ru,
            "vision_confidence": confidence,
            "status": "not_recognized",
        }

    return {
        **state,
        "vision_name": name_ru,
        "vision_confidence": confidence,
        "query": name_ru,  # для передачи в text_search
    }
