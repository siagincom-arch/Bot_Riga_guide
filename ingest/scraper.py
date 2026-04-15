"""
Web Scraper — извлечение текста со страниц о достопримечательностях.

M7.1 — AG task.
ARCHITECTURE §5: ingest — scrape → chunk → embed → store.

Использует httpx + BeautifulSoup для извлечения текста.
Поддерживает Wikipedia, Latvia.travel, LiveRiga и произвольные страницы.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from src.telemetry.log import get_logger

logger = get_logger("ingest.scraper")


@dataclass
class ScrapedPage:
    """Результат скрапинга одной страницы."""
    url: str
    title: str = ""
    text: str = ""
    lang: str = "ru"
    success: bool = True
    error: Optional[str] = None


class Scraper:
    """
    HTTP scraper для извлечения текста с веб-страниц.

    Поддерживает:
    - Wikipedia (русская/латышская)
    - Latvia.travel
    - LiveRiga.com
    - Произвольные страницы
    """

    # Заголовки для вежливого скрапинга
    DEFAULT_HEADERS = {
        "User-Agent": "RigaGuideBot/0.1 (educational project; +https://github.com/riga-guide-bot)",
        "Accept-Language": "ru,lv;q=0.9,en;q=0.8",
    }

    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout

    async def scrape(self, url: str) -> ScrapedPage:
        """
        Скрапит одну страницу, возвращает ScrapedPage.

        Args:
            url: URL для скрапинга.

        Returns:
            ScrapedPage с текстом или ошибкой.
        """
        logger.info("scraper.start", url=url)

        try:
            async with httpx.AsyncClient(
                headers=self.DEFAULT_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Удаляем шум
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            # Извлекаем заголовок
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Извлекаем текст в зависимости от домена
            text = self._extract_text(soup, url)

            # Нормализуем пробелы
            text = self._normalize_whitespace(text)

            logger.info("scraper.ok", url=url, chars=len(text))

            return ScrapedPage(url=url, title=title, text=text)

        except httpx.HTTPStatusError as e:
            logger.warning("scraper.http_error", url=url, status=e.response.status_code)
            return ScrapedPage(url=url, success=False, error=f"HTTP {e.response.status_code}")

        except Exception as e:
            logger.error("scraper.error", url=url, error=str(e))
            return ScrapedPage(url=url, success=False, error=str(e))

    async def scrape_many(self, urls: list[str]) -> list[ScrapedPage]:
        """
        Скрапит список URL (последовательно, чтобы не DDoS'ить).

        Args:
            urls: список URL.

        Returns:
            Список ScrapedPage.
        """
        results = []
        for url in urls:
            page = await self.scrape(url)
            results.append(page)
        return results

    def _extract_text(self, soup: BeautifulSoup, url: str) -> str:
        """Извлекает основной текст в зависимости от домена."""

        # Wikipedia: #mw-content-text
        if "wikipedia.org" in url:
            content = soup.find(id="mw-content-text")
            if content:
                # Удаляем таблицы infobox, навигацию, ссылки [1]
                for cls in ["infobox", "navbox", "reflist", "toc", "mw-editsection",
                            "reference", "thumb", "mw-empty-elt"]:
                    for el in content.find_all(class_=cls):
                        el.decompose()
                # Удаляем sup (сноски [1], [2])
                for sup in content.find_all("sup"):
                    sup.decompose()
                return content.get_text(separator="\n", strip=True)

        # Latvia.travel: article body
        if "latvia.travel" in url:
            content = soup.find("article") or soup.find(class_="content")
            if content:
                return content.get_text(separator="\n", strip=True)

        # LiveRiga: main content
        if "liveriga" in url:
            content = soup.find("main") or soup.find(class_="content")
            if content:
                return content.get_text(separator="\n", strip=True)

        # Fallback: <main> или <article> или <body>
        for tag in ["main", "article"]:
            content = soup.find(tag)
            if content:
                return content.get_text(separator="\n", strip=True)

        # Последний fallback — body
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return ""

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Нормализация: схлопывание пробелов, удаление пустых строк."""
        # Заменяем множественные пробелы внутри строки
        text = re.sub(r"[ \t]+", " ", text)
        # Удаляем пустые строки (оставляем максимум 2 подряд)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
