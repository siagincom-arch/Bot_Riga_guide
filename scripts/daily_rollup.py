#!/usr/bin/env python3
"""
Daily Rollup — подсчёт метрик M2/M3/M5 из logs/bot.jsonl.

M10.2 — AG task (AG4.2).
ARCHITECTURE §8.2: reads JSONL, prints markdown report.

Только stdlib — никаких внешних зависимостей.

Использование:
    python scripts/daily_rollup.py
    python scripts/daily_rollup.py --log-path logs/bot.jsonl --days 3
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def load_records(log_path: Path) -> list[dict[str, Any]]:
    """Загружает записи из JSONL-файла."""
    records: list[dict[str, Any]] = []
    if not log_path.exists():
        return records

    with open(log_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                print(f"⚠ Строка {line_num}: невалидный JSON, пропускаю", file=sys.stderr)

    return records


def filter_by_date(records: list[dict], target_date: str) -> list[dict]:
    """Фильтрует записи за конкретную дату (YYYY-MM-DD)."""
    filtered = []
    for r in records:
        ts = r.get("ts") or r.get("timestamp") or ""
        if isinstance(ts, str) and ts.startswith(target_date):
            filtered.append(r)
    return filtered


def compute_m2(records: list[dict]) -> dict[str, Any]:
    """
    M2: Success ratio — ok / total.

    Returns:
        {ok, total, ratio}
    """
    total = len(records)
    ok = sum(1 for r in records if r.get("status") == "ok")
    ratio = ok / total if total > 0 else 0.0
    return {"ok": ok, "total": total, "ratio": round(ratio, 4)}


def compute_m3(records: list[dict]) -> dict[str, dict[str, float]]:
    """
    M3: p50/p95 latency по input_type.

    Returns:
        {input_type: {p50, p95, count}}
    """
    by_type: dict[str, list[float]] = defaultdict(list)
    for r in records:
        input_type = r.get("input_type", "unknown")
        latency = r.get("latency_ms")
        if latency is not None:
            try:
                by_type[input_type].append(float(latency))
            except (ValueError, TypeError):
                pass

    result = {}
    for itype, latencies in sorted(by_type.items()):
        latencies.sort()
        n = len(latencies)
        if n == 0:
            continue
        p50 = _percentile(latencies, 50)
        p95 = _percentile(latencies, 95)
        result[itype] = {
            "p50": round(p50, 1),
            "p95": round(p95, 1),
            "count": n,
        }

    return result


def compute_m5(records: list[dict], trailing_days: int = 3) -> dict[str, Any]:
    """
    M5: Уникальные chat_id за trailing N дней.

    Args:
        records: все записи (не отфильтрованные по дате).
        trailing_days: окно в днях.

    Returns:
        {unique_chats, trailing_days, daily_breakdown: {date: count}}
    """
    cutoff = datetime.now() - timedelta(days=trailing_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    all_chats: set[str] = set()
    daily: dict[str, set[str]] = defaultdict(set)

    for r in records:
        ts = r.get("ts") or r.get("timestamp") or ""
        if isinstance(ts, str) and ts >= cutoff_str:
            chat_id = str(r.get("chat_id", ""))
            if chat_id:
                all_chats.add(chat_id)
                day = ts[:10]
                daily[day].add(chat_id)

    breakdown = {day: len(chats) for day, chats in sorted(daily.items())}

    return {
        "unique_chats": len(all_chats),
        "trailing_days": trailing_days,
        "daily_breakdown": breakdown,
    }


def _percentile(sorted_data: list[float], pct: int) -> float:
    """Вычисляет перцентиль из отсортированного списка."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    idx = (pct / 100) * (n - 1)
    lower = int(idx)
    upper = min(lower + 1, n - 1)
    frac = idx - lower
    return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac


def format_report(
    date_str: str,
    m2: dict[str, Any],
    m3: dict[str, dict[str, float]],
    m5: dict[str, Any],
) -> str:
    """Форматирует markdown-отчёт."""
    lines = [
        f"# Daily Rollup — {date_str}",
        "",
        "## M2: Success Ratio",
        "",
        f"- **OK:** {m2['ok']} / {m2['total']}",
        f"- **Ratio:** {m2['ratio']:.2%}",
        "",
    ]

    # M3
    lines.append("## M3: Latency (p50 / p95)")
    lines.append("")
    if m3:
        lines.append("| input_type | count | p50 (ms) | p95 (ms) |")
        lines.append("|------------|------:|--------:|--------:|")
        for itype, stats in m3.items():
            lines.append(
                f"| {itype} | {stats['count']} | {stats['p50']} | {stats['p95']} |"
            )
    else:
        lines.append("_Нет данных о latency._")
    lines.append("")

    # M5
    lines.append("## M5: Unique Users (trailing 3 days)")
    lines.append("")
    lines.append(f"- **Уникальных chat_id:** {m5['unique_chats']}")
    lines.append(f"- **Окно:** {m5['trailing_days']} дней")
    if m5["daily_breakdown"]:
        lines.append("")
        lines.append("| Дата | Уникальных |")
        lines.append("|------|----------:|")
        for day, count in m5["daily_breakdown"].items():
            lines.append(f"| {day} | {count} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily rollup: M2/M3/M5 метрики из bot.jsonl"
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("logs/bot.jsonl"),
        help="Путь к JSONL-логу (по умолчанию logs/bot.jsonl)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Дата для отчёта в формате YYYY-MM-DD (по умолчанию — вчера)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Trailing-окно для M5 в днях (по умолчанию 3)",
    )
    args = parser.parse_args()

    # Определяем дату
    if args.date:
        target_date = args.date
    else:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Загружаем записи
    all_records = load_records(args.log_path)
    if not all_records:
        print(f"⚠ Нет записей в {args.log_path}", file=sys.stderr)
        print(format_report(target_date, compute_m2([]), {}, compute_m5([], args.days)))
        return

    # Фильтруем за целевую дату (M2, M3)
    day_records = filter_by_date(all_records, target_date)

    # Считаем метрики
    m2 = compute_m2(day_records)
    m3 = compute_m3(day_records)
    m5 = compute_m5(all_records, trailing_days=args.days)

    # Печатаем отчёт
    print(format_report(target_date, m2, m3, m5))


if __name__ == "__main__":
    main()
