"""
Firecrawl scraper — клиент Firecrawl API с файловым кешем.

M7.3 — AG task (AG5.2).
IMPLEMENTATION_PLAN §8 M7.3: firecrawl scraper with cache.

Кеш: data/raw/<sha1(url)>.md — повторный вызов читает из кеша (митигация R2).

Требует env-переменную FIRECRAWL_API_KEY.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

try:
    from firecrawl import FirecrawlApp
except ImportError as e:
    raise ImportError(
        "Для работы Firecrawl scraper нужна библиотека firecrawl-py: "
        "pip install firecrawl-py"
    ) from e

from src.telemetry.log import get_logger

logger = get_logger("ingest.scrapers.firecrawl")

# Директория кеша по умолчанию
DEFAULT_CACHE_DIR = Path("data/raw")


class FirecrawlScraper:
    """
    Scraper через Firecrawl API с локальным файловым кешем.

    Кеш хранится в data/raw/<sha1(url)>.md.
    Повторный вызов scrape() для того же URL читает из кеша,
    не тратя квоту Firecrawl API (митигация риска R2).
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        """
        Args:
            api_key: Firecrawl API key (или из env FIRECRAWL_API_KEY).
            cache_dir: директория кеша (по умолчанию data/raw/).
        """
        self._api_key = api_key or os.getenv("FIRECRAWL_API_KEY", "")
        if not self._api_key:
            logger.warning("firecrawl.no_api_key", msg="FIRECRAWL_API_KEY не задан")

        self._cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._app: Optional[FirecrawlApp] = None

    def _get_app(self) -> FirecrawlApp:
        """Lazy init Firecrawl клиента."""
        if self._app is None:
            self._app = FirecrawlApp(api_key=self._api_key)
        return self._app

    @staticmethod
    def _url_hash(url: str) -> str:
        """SHA1 от URL для имени файла кеша."""
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _cache_path(self, url: str) -> Path:
        """Путь к файлу кеша для URL."""
        return self._cache_dir / f"{self._url_hash(url)}.md"

    def _read_cache(self, url: str) -> str | None:
        """Читает закешированный markdown, если есть."""
        path = self._cache_path(url)
        if path.exists():
            logger.info("firecrawl.cache_hit", url=url)
            return path.read_text(encoding="utf-8")
        return None

    def _write_cache(self, url: str, content: str) -> None:
        """Записывает markdown в кеш."""
        path = self._cache_path(url)
        path.write_text(content, encoding="utf-8")
        logger.info("firecrawl.cache_write", url=url, path=str(path))

    def scrape(self, url: str, force: bool = False) -> str:
        """
        Скрапит URL через Firecrawl API, возвращает markdown.

        Args:
            url: URL для скрапинга.
            force: если True — игнорирует кеш и скачивает заново.

        Returns:
            Markdown-текст страницы.
        """
        # Проверяем кеш
        if not force:
            cached = self._read_cache(url)
            if cached is not None:
                return cached

        logger.info("firecrawl.scrape_start", url=url)

        try:
            app = self._get_app()
            result = app.scrape_url(
                url,
                params={"formats": ["markdown"]},
            )

            # Firecrawl возвращает dict с ключом 'markdown'
            markdown = ""
            if isinstance(result, dict):
                markdown = result.get("markdown", "") or ""
            elif hasattr(result, "markdown"):
                markdown = result.markdown or ""

            if not markdown:
                logger.warning("firecrawl.empty_result", url=url)
                return ""

            # Записываем в кеш
            self._write_cache(url, markdown)

            logger.info("firecrawl.ok", url=url, chars=len(markdown))
            return markdown

        except Exception as e:
            logger.error("firecrawl.error", url=url, error=str(e))
            return ""

    def scrape_many(self, urls: list[str], force: bool = False) -> dict[str, str]:
        """
        Скрапит список URL.

        Args:
            urls: список URL.
            force: игнорировать кеш.

        Returns:
            dict {url: markdown}.
        """
        results = {}
        for url in urls:
            results[url] = self.scrape(url, force=force)
        return results
