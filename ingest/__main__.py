"""Riga Guide Bot — Ingest CLI entry point.

Запуск: python -m ingest --source wikipedia --cities riga --limit 5
Реализация появится в M7 (Ingest Pipeline).
"""

import sys


def main() -> None:
    """Точка входа ingest CLI. Заглушка до M7."""
    print(f"Riga Guide Ingest — Python {sys.version}")
    print("Ingest pipeline ещё не реализован. См. IMPLEMENTATION_PLAN.md → M7.")


if __name__ == "__main__":
    main()
