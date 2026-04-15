#!/usr/bin/env python3
"""
HITL Runner — прогон тестового набора фото и текстов через RAG.

M9.5 — AG task (AG3.1).
IMPLEMENTATION_PLAN §10 M9.5: HITL smoke pack runner.

Итерирует фото и тексты, зовёт run_rag, пишет CSV с результатами.

Использование:
    python scripts/run_hitl.py --photos-dir tests/fixtures/photos --text-pack docs/hitl_text_pack.yaml --out results.csv
    python scripts/run_hitl.py --text-pack docs/hitl_text_pack.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

from src.rag.singleton import get_rag_graph, run_rag


def load_text_pack(path: Path) -> list[dict[str, str]]:
    """
    Загружает текстовый pack из YAML или JSON.

    Ожидаемый формат:
        queries:
          - text: "Домский собор"
          - text: "чёрные головы"
          - text: "Domskij sobor"
    """
    if not path.exists():
        print(f"⚠ Text pack не найден: {path}", file=sys.stderr)
        return []

    content = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            print("⚠ Для YAML нужна библиотека PyYAML: pip install pyyaml", file=sys.stderr)
            return []
    elif path.suffix == ".json":
        data = json.loads(content)
    else:
        # Простой текстовый формат — одна строка = один запрос
        return [{"text": line.strip()} for line in content.splitlines() if line.strip()]

    queries = data.get("queries", [])
    return queries


def list_photos(photos_dir: Path) -> list[Path]:
    """Возвращает список файлов изображений в директории."""
    if not photos_dir.exists():
        return []

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    photos = [
        f for f in sorted(photos_dir.iterdir())
        if f.is_file() and f.suffix.lower() in extensions
    ]
    return photos


async def run_text_query(query: str) -> dict[str, Any]:
    """Прогон текстового запроса через RAG-граф."""
    start = time.monotonic()
    result: dict[str, Any] = {
        "input": query,
        "input_type": "text",
        "place_id": "",
        "status": "error",
        "latency_ms": 0,
        "recognized_confidence": None,
    }

    try:
        state = {
            "input_type": "text",
            "query": query,
        }
        output = await run_rag(state)

        result["place_id"] = output.get("place_id", "")
        result["status"] = output.get("status", "ok")
        result["recognized_confidence"] = output.get("recognized_confidence")

    except Exception as e:
        result["status"] = f"error: {e}"

    result["latency_ms"] = int((time.monotonic() - start) * 1000)
    return result


async def run_photo_query(photo_path: Path) -> dict[str, Any]:
    """Прогон фото через RAG-граф."""
    start = time.monotonic()
    result: dict[str, Any] = {
        "input": str(photo_path.name),
        "input_type": "photo",
        "place_id": "",
        "status": "error",
        "latency_ms": 0,
        "recognized_confidence": None,
    }

    try:
        image_bytes = photo_path.read_bytes()
        state = {
            "input_type": "photo",
            "image_bytes": image_bytes,
        }
        output = await run_rag(state)

        result["place_id"] = output.get("place_id", "")
        result["status"] = output.get("status", "ok")
        result["recognized_confidence"] = output.get("recognized_confidence")

    except Exception as e:
        result["status"] = f"error: {e}"

    result["latency_ms"] = int((time.monotonic() - start) * 1000)
    return result


async def run_all(
    photos: list[Path],
    text_queries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Прогоняет все тесты последовательно."""
    results: list[dict[str, Any]] = []

    # Фото
    for photo in photos:
        print(f"  📸 {photo.name}...", end=" ", flush=True)
        r = await run_photo_query(photo)
        print(f"{r['status']} ({r['latency_ms']}ms)")
        results.append(r)

    # Тексты
    for q in text_queries:
        text = q.get("text", "")
        if not text:
            continue
        print(f"  ✏️  {text[:50]}...", end=" ", flush=True)
        r = await run_text_query(text)
        print(f"{r['status']} ({r['latency_ms']}ms)")
        results.append(r)

    return results


def write_csv(results: list[dict[str, Any]], out_path: Path) -> None:
    """Записывает результаты в CSV."""
    fieldnames = ["input", "input_type", "place_id", "status", "latency_ms", "recognized_confidence"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    print(f"\n📄 Результаты записаны в {out_path}")


def print_summary(results: list[dict[str, Any]]) -> None:
    """Печатает сводку."""
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    errors = total - ok

    photos = [r for r in results if r["input_type"] == "photo"]
    texts = [r for r in results if r["input_type"] == "text"]

    photo_ok = sum(1 for r in photos if r["status"] == "ok")
    text_ok = sum(1 for r in texts if r["status"] == "ok")

    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    print("\n" + "=" * 50)
    print(f"📊 HITL Summary")
    print(f"   Total: {total} | OK: {ok} | Errors: {errors}")
    if photos:
        print(f"   Photos: {photo_ok}/{len(photos)}")
    if texts:
        print(f"   Texts: {text_ok}/{len(texts)}")
    if latencies:
        print(f"   Avg latency: {avg_latency:.0f}ms")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HITL Runner — прогон тестового набора через RAG-граф."
    )
    parser.add_argument(
        "--photos-dir",
        type=Path,
        default=None,
        help="Директория с тестовыми фото (jpg/png/webp).",
    )
    parser.add_argument(
        "--text-pack",
        type=Path,
        default=None,
        help="Путь к файлу с текстовыми запросами (yaml/json/txt).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("hitl_results.csv"),
        help="Путь для CSV-результатов (по умолчанию hitl_results.csv).",
    )
    args = parser.parse_args()

    if args.photos_dir is None and args.text_pack is None:
        parser.error("Укажите хотя бы --photos-dir или --text-pack")

    # Инициализируем RAG-граф (lazy singleton)
    print("🔄 Инициализация RAG-графа...")
    get_rag_graph()  # форсируем lazy-init, чтобы ошибки конфига были сразу

    # Загружаем данные
    photos = list_photos(args.photos_dir) if args.photos_dir else []
    text_queries = load_text_pack(args.text_pack) if args.text_pack else []

    if not photos and not text_queries:
        print("⚠ Нет данных для тестирования.", file=sys.stderr)
        sys.exit(1)

    print(f"📁 Фото: {len(photos)} | Текстовых запросов: {len(text_queries)}")
    print()

    # Прогон
    results = asyncio.run(run_all(photos, text_queries))

    # Результаты
    write_csv(results, args.out)
    print_summary(results)


if __name__ == "__main__":
    main()
