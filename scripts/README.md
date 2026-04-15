# Scripts — утилиты для Riga Guide Bot

## backup.sh — Ночной бэкап данных

Копирует `data/chroma/` и `data/bot.db` в `backups/YYYY-MM-DD/`.
Удаляет бэкапы старше 7 дней.

### Запуск

```bash
cd /opt/riga-guide
./scripts/backup.sh
```

### Настройка cron

```bash
crontab -e
# Добавить строку:
0 3 * * *  cd /opt/riga-guide && ./scripts/backup.sh >> logs/backup.log 2>&1
```

### Восстановление из бэкапа

```bash
docker compose stop bot
rm -rf data/chroma data/bot.db
cp -r backups/2026-04-15/chroma data/
cp    backups/2026-04-15/bot.db data/
docker compose start bot
```

---

## daily_rollup.py — Метрики M2/M3/M5

Читает `logs/bot.jsonl`, считает:
- **M2:** Success ratio (ok / total)
- **M3:** p50/p95 latency по input_type
- **M5:** Уникальные chat_id за trailing 3 дня

Выводит markdown-отчёт в stdout.

### Запуск

```bash
# Отчёт за вчера
python scripts/daily_rollup.py

# Отчёт за конкретную дату
python scripts/daily_rollup.py --date 2026-04-14

# Кастомный путь к логу
python scripts/daily_rollup.py --log-path /app/logs/bot.jsonl

# Trailing окно 7 дней для M5
python scripts/daily_rollup.py --days 7
```

### Зависимости

Только stdlib — дополнительных библиотек не требуется.

---

## run_hitl.py — HITL smoke-тест

Прогоняет набор тестовых фото и текстовых запросов через RAG-граф.
Пишет результаты в CSV.

### Запуск

```bash
# Только текстовые запросы
python scripts/run_hitl.py --text-pack docs/hitl_text_pack.yaml --out results.csv

# Фото + тексты
python scripts/run_hitl.py \
    --photos-dir tests/fixtures/photos \
    --text-pack docs/hitl_text_pack.yaml \
    --out hitl_results.csv

# Только фото
python scripts/run_hitl.py --photos-dir tests/fixtures/photos
```

### Формат text-pack

YAML:
```yaml
queries:
  - text: "Домский собор"
  - text: "чёрные головы"
  - text: "Domskij sobor"
```

### CSV-вывод

| input | input_type | place_id | status | latency_ms | recognized_confidence |
|-------|-----------|----------|--------|-----------|----------------------|
| dome.jpg | photo | dome-cathedral | ok | 12340 | 0.95 |
| Домский собор | text | dome-cathedral | ok | 3200 | |

### Предусловия

- `src.rag.singleton` должен быть готов (создаёт Claude)
- `.env` должен содержать `GEMINI_API_KEY` и `TAVILY_API_KEY`
- Docker-контейнер должен быть доступен (или локальная среда)
