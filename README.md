# Riga Guide Bot

Telegram-бот — персональный гид-рассказчик по Риге, Сигулде и Рундале для русскоязычных гостей. Принимает фото, геолокацию или текстовый запрос — отвечает короткой справкой и живой историей в тоне влюблённого в город рижанина.

**Статус:** в разработке (MVP). Методика: Молянов (spec-driven), pet-project.

## Запуск

```bash
cp .env.example .env            # заполнить токены (Telegram, Gemini, Tavily)
docker compose build

# Первый раз: наполнить knowledge base
docker compose --profile manual run --rm ingest --source wikipedia --cities riga --limit 30

# Запустить бота
docker compose up -d bot
docker compose logs -f bot      # смотреть логи
```

## Документация

- [docs/USER_SPEC.md](docs/USER_SPEC.md) — кто пользователь, что делает, метрики успеха
- [docs/TECH_SPEC.md](docs/TECH_SPEC.md) — API-контракты, модели данных, RAG-pipeline
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — компоненты, деплой, sequence-диаграммы
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — план разработки (Claude + Antigravity + owner)
- [PROTOCOL.md](PROTOCOL.md) — рабочий журнал проекта
- [CLAUDE_BRIEF.md](CLAUDE_BRIEF.md) — бриф research-фазы

## Стек

Python 3.12 · python-telegram-bot · LangGraph · Google Gemini 2.5 Flash · Chroma · Tavily · SQLite · Docker Compose · self-hosted VPS.
