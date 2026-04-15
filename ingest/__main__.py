"""
Riga Guide Bot — Ingest CLI entry point.

Запуск:
    python -m ingest --source wikipedia --limit 5
    python -m ingest --source firecrawl --urls https://latvia.travel/ru/article/riga
    python -m ingest --source text --title "Домский собор" --text-file dome.txt

M7 — AG task (блок I).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ingest.pipeline import IngestPipeline


def build_parser() -> argparse.ArgumentParser:
    """Строит CLI-парсер."""
    parser = argparse.ArgumentParser(
        description="Riga Guide Bot — Ingest Pipeline CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Примеры:\n"
            "  python -m ingest --source wikipedia --limit 5\n"
            "  python -m ingest --source wikipedia --seeds ingest/seeds/riga.yaml\n"
            "  python -m ingest --source firecrawl --urls https://example.com/page1 https://example.com/page2\n"
            "  python -m ingest --source text --title 'Домский собор' --text-file content.txt\n"
        ),
    )

    parser.add_argument(
        "--source",
        choices=["wikipedia", "firecrawl", "text"],
        required=True,
        help="Тип источника: wikipedia, firecrawl, или text (ручной ввод).",
    )
    parser.add_argument(
        "--seeds",
        type=Path,
        default=None,
        help="Путь к YAML с seed-страницами Wikipedia (по умолчанию ingest/seeds/riga.yaml).",
    )
    parser.add_argument(
        "--urls",
        nargs="+",
        default=[],
        help="URL для Firecrawl (можно несколько через пробел).",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Заголовок для ручного текста.",
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        default=None,
        help="Путь к файлу с текстом (для --source text).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Максимум источников для обработки.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Игнорировать кеш Firecrawl.",
    )

    return parser


async def run(args: argparse.Namespace) -> int:
    """Запускает pipeline в зависимости от источника."""
    pipeline = IngestPipeline()

    if args.source == "wikipedia":
        print("🔄 Запуск Wikipedia ingest...")
        stats = await pipeline.run_wikipedia(
            seeds_path=args.seeds,
            limit=args.limit,
        )

    elif args.source == "firecrawl":
        if not args.urls:
            print("⚠ --urls обязательны для --source firecrawl", file=sys.stderr)
            return 1
        print(f"🔄 Запуск Firecrawl ingest ({len(args.urls)} URLs)...")
        stats = await pipeline.run_firecrawl(
            urls=args.urls,
            force=args.force,
            limit=args.limit,
        )

    elif args.source == "text":
        if not args.text_file:
            print("⚠ --text-file обязателен для --source text", file=sys.stderr)
            return 1
        if not args.text_file.exists():
            print(f"⚠ Файл не найден: {args.text_file}", file=sys.stderr)
            return 1

        title = args.title or args.text_file.stem
        text = args.text_file.read_text(encoding="utf-8")
        print(f"🔄 Запуск Text ingest: {title} ({len(text)} символов)...")
        stats = await pipeline.run_text(
            title=title,
            text=text,
            source=f"file:{args.text_file.name}",
        )

    else:
        print(f"⚠ Неизвестный источник: {args.source}", file=sys.stderr)
        return 1

    # Вывод результатов
    print()
    print("=" * 60)
    print(f"📊 {stats.summary()}")
    print("=" * 60)

    if stats.errors:
        print(f"\n⚠ Ошибки ({len(stats.errors)}):")
        for err in stats.errors[:10]:
            print(f"  • {err}")
        if len(stats.errors) > 10:
            print(f"  ... и ещё {len(stats.errors) - 10}")

    return 0 if stats.sources_error == 0 else 1


def main() -> None:
    """Точка входа ingest CLI."""
    parser = build_parser()
    args = parser.parse_args()

    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
