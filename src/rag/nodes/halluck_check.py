"""
RAG node: halluck_check — проверка галлюцинаций + 1 retry.

M5.8 — Claude task (дописано AG по плану Claude).
TECH_SPEC §5.2: halluck_check — {passages, raw_answer} → {pass/fail, issues}, timeout 8s.

Логика:
1. Рендерит halluck.j2 с passages и answer.
2. Вызывает Gemini → парсит JSON {pass, issues}.
3. Если pass=false и retry_count=0 → регенерация через generate node.
4. Если pass=false и retry_count>=1 → маркер «возможно, неточно» (uncertain=true).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader

from src.llm.retry import retry_async
from src.telemetry.log import get_logger

logger = get_logger("rag.nodes.halluck_check")


class _GenerateCapable(Protocol):
    async def generate(self, prompt: str) -> str: ...


_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    keep_trailing_newline=True,
)


def _parse_halluck_json(raw: str) -> dict[str, Any]:
    """
    Парсит JSON-ответ фактчекера. Устойчив к markdown-обёрткам.

    Возвращает {"pass": False, "issues": ["parse_error"]} при невалидном JSON.
    """
    text = raw.strip()
    # Снимаем ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {
                "pass": bool(data.get("pass", False)),
                "issues": list(data.get("issues", [])),
            }
    except json.JSONDecodeError:
        logger.warning("halluck.parse.json_invalid", raw_preview=text[:200])

    return {"pass": False, "issues": ["JSON parse error from checker"]}


async def halluck_check(
    state: dict[str, Any],
    *,
    gemini_client: _GenerateCapable,
    max_retries: int = 1,
) -> dict[str, Any]:
    """
    Проверяет сгенерированный ответ на галлюцинации.

    Если ответ не прошёл проверку и retry_count < max_retries:
    - Помечает для регенерации (halluck_passed=False, retry_count++).
    Если retry_count >= max_retries:
    - Пропускает с маркером uncertain=True (ответ всё равно отправляется,
      но с дисклеймером «возможно, неточно»).

    Args:
        state: RAGState с passages, raw_answer.
        gemini_client: GeminiClient с методом generate.
        max_retries: максимум регенераций (по плану = 1).

    Returns:
        state с halluck_passed, halluck_issues, halluck_retry_count, uncertain.
    """
    passages = state.get("passages", [])
    raw_answer = state.get("raw_answer", "")
    retry_count = state.get("halluck_retry_count", 0)

    if not raw_answer:
        logger.warning("halluck.no_answer")
        return {
            **state,
            "halluck_passed": True,  # нечего проверять
            "halluck_issues": [],
            "uncertain": False,
        }

    # Рендер промпта
    template = _jinja_env.get_template("halluck.j2")
    prompt = template.render(
        passages=passages,
        answer=raw_answer,
    )

    logger.info("halluck.start", answer_len=len(raw_answer), retry_count=retry_count)

    try:
        # Один retry на сетевую ошибку (не на контент)
        checker_raw = await retry_async(
            lambda: gemini_client.generate(prompt),
            attempts=2,
            backoff_seconds=0.5,
            label="halluck_check",
        )
    except Exception as exc:
        logger.error("halluck.llm_error", error=repr(exc))
        # При ошибке checker'а — пропускаем с uncertain
        return {
            **state,
            "halluck_passed": True,
            "halluck_issues": [f"checker_error: {exc!r}"],
            "uncertain": True,
        }

    result = _parse_halluck_json(checker_raw)
    passed = result["pass"]
    issues = result["issues"]

    logger.info("halluck.result", passed=passed, issues_count=len(issues))

    if passed:
        return {
            **state,
            "halluck_passed": True,
            "halluck_issues": [],
            "halluck_retry_count": retry_count,
            "uncertain": False,
        }

    # Не прошёл проверку
    if retry_count < max_retries:
        # Есть ещё попытки — помечаем для регенерации
        logger.info("halluck.retry", retry_count=retry_count, issues=issues[:3])
        return {
            **state,
            "halluck_passed": False,
            "halluck_issues": issues,
            "halluck_retry_count": retry_count + 1,
            "uncertain": False,
        }

    # Все попытки исчерпаны — отправляем с дисклеймером
    logger.warning("halluck.exhausted", issues=issues[:3])
    return {
        **state,
        "halluck_passed": True,  # пропускаем, но с uncertain
        "halluck_issues": issues,
        "halluck_retry_count": retry_count,
        "uncertain": True,
    }
