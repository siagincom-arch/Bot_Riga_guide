"""
Wikipedia scraper — обёртка вокруг библиотеки wikipedia (pypi).

M7.2 — AG task (AG5.1).
IMPLEMENTATION_PLAN §8 M7.2: wikipedia scraper с seed-страницами.

Использование:
    from ingest.scrapers.wikipedia import WikipediaScraper
    scraper = WikipediaScraper(lang="ru")
    result = scraper.fetch("Домский собор (Рига)")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

try:
    import wikipedia
except ImportError as e:
    raise ImportError(
        "Для работы Wikipedia scraper нужна библиотека wikipedia: "
        "pip install wikipedia"
    ) from e

from src.telemetry.log import get_logger

logger = get_logger("ingest.scrapers.wikipedia")


@dataclass
class WikiResult:
    """Результат скрапинга одной Wikipedia-страницы."""
    title: str
    text: str
    url: str
    summary: str
    success: bool = True
    error: Optional[str] = None


class WikipediaScraper:
    """
    Scraper для Wikipedia через pypi-библиотеку `wikipedia`.

    Поддерживает:
    - Поиск и скачивание страниц по заголовку
    - Автоматический fallback при неоднозначности (берёт первый вариант)
    - Загрузка seed-списка из YAML
    """

    def __init__(self, lang: str = "ru") -> None:
        self._lang = lang
        wikipedia.set_lang(lang)

    def fetch(self, title: str, lang: str | None = None, _depth: int = 0) -> dict[str, Any]:
        """
        Скачивает статью из Wikipedia.

        Args:
            title: заголовок статьи.
            lang: язык (по умолчанию — из конструктора).
            _depth: счётчик рекурсии (внутренний, не передавать).

        Returns:
            dict с ключами: title, text, url, summary.
        """
        if lang and lang != self._lang:
            wikipedia.set_lang(lang)
            self._lang = lang

        logger.info("wikipedia.fetch", title=title, lang=self._lang)

        try:
            page = wikipedia.page(title, auto_suggest=False)
            result = WikiResult(
                title=page.title,
                text=page.content,
                url=page.url,
                summary=page.summary[:500],
            )
            logger.info("wikipedia.ok", title=result.title, chars=len(result.text))
            return {
                "title": result.title,
                "text": result.text,
                "url": result.url,
                "summary": result.summary,
            }

        except wikipedia.exceptions.DisambiguationError as e:
            logger.warning("wikipedia.disambig", title=title, options=e.options[:5])

            # Защита от бесконечной рекурсии: максимум 1 уровень
            if _depth >= 1:
                logger.error("wikipedia.disambig_loop", title=title)
                return {
                    "title": title,
                    "text": "",
                    "url": "",
                    "summary": "",
                    "error": f"Disambiguation loop: {e.options[:3]}",
                }

            # Пробуем найти вариант, отличающийся от исходного заголовка
            candidate = None
            for opt in e.options:
                if opt.lower() != title.lower():
                    candidate = opt
                    break

            if candidate is None and e.options:
                # Все варианты совпадают с запросом — пробуем первый с другим регистром
                candidate = e.options[0] if e.options[0] != title else None

            if candidate:
                return self.fetch(candidate, lang=lang, _depth=_depth + 1)

            return {
                "title": title,
                "text": "",
                "url": "",
                "summary": "",
                "error": f"Disambiguation: {e.options[:5]}",
            }

        except wikipedia.exceptions.PageError:
            logger.warning("wikipedia.not_found", title=title)
            return {
                "title": title,
                "text": "",
                "url": "",
                "summary": "",
                "error": f"Page not found: {title}",
            }

        except Exception as e:
            logger.error("wikipedia.error", title=title, error=str(e))
            return {
                "title": title,
                "text": "",
                "url": "",
                "summary": "",
                "error": str(e),
            }

    def fetch_seeds(self, seeds_path: str | Path | None = None) -> list[dict[str, Any]]:
        """
        Загружает seed-список из YAML и скачивает все страницы.

        Args:
            seeds_path: путь к YAML (по умолчанию ingest/seeds/riga.yaml).

        Returns:
            Список результатов fetch().
        """
        if seeds_path is None:
            seeds_path = Path(__file__).parent.parent / "seeds" / "riga.yaml"
        else:
            seeds_path = Path(seeds_path)

        if not seeds_path.exists():
            logger.error("wikipedia.seeds_not_found", path=str(seeds_path))
            return []

        with open(seeds_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        seeds = data.get("seeds", [])
        logger.info("wikipedia.seeds_loaded", count=len(seeds))

        results = []
        for seed in seeds:
            title = seed if isinstance(seed, str) else seed.get("title", "")
            lang = seed.get("lang", self._lang) if isinstance(seed, dict) else self._lang
            if title:
                result = self.fetch(title, lang=lang)
                results.append(result)

        return results
