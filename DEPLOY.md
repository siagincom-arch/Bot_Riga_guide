# DEPLOY — Riga Guide Bot

Пошаговая инструкция по деплою бота на VPS.

---

## 1. Предусловия на VPS

- **ОС:** Linux (Ubuntu 22.04+ / Debian 12+)
- **Docker:** ≥ 24.0
- **Docker Compose:** v2 (плагин, не standalone)

### Установка Docker (если нет)

```bash
# Обновляем пакеты
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com | sh

# Добавляем текущего пользователя в группу docker
sudo usermod -aG docker $USER

# Перелогиниваемся
exit
# (войти снова через SSH)

# Проверяем
docker --version
docker compose version
```

---

## 2. Переменные окружения

Все секреты хранятся в `.env` (никогда не коммитится в git).

Шаблон: [`.env.example`](.env.example)

| Переменная | Обязательная | Описание |
|-----------|:----------:|---------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен от @BotFather |
| `GEMINI_API_KEY` | ✅ | Google AI Studio → API key |
| `TAVILY_API_KEY` | ✅ | tavily.com → API key |
| `FIRECRAWL_API_KEY` | ❌ | firecrawl.dev → API key (только для ingest) |
| `CHROMA_PATH` | — | По умолчанию `./data/chroma` |
| `SQLITE_PATH` | — | По умолчанию `./data/bot.db` |
| `LOG_PATH` | — | По умолчанию `./logs/bot.jsonl` |
| `LOG_LEVEL` | — | По умолчанию `INFO` |
| `RAG_TOP_K` | — | По умолчанию `6` |
| `RAG_GRADE_THRESHOLD` | — | По умолчанию `0.6` |
| `VISION_CONFIDENCE_THRESHOLD` | — | По умолчанию `0.5` |
| `SESSION_WINDOW` | — | По умолчанию `10` |
| `SESSION_TTL_HOURS` | — | По умолчанию `24` |
| `NEARBY_RADIUS_M` | — | По умолчанию `300` |

---

## 3. Пошаговый деплой

### 3.1 Клонируем проект

```bash
cd /opt
git clone <REPO_URL> riga-guide
cd riga-guide
```

### 3.2 Создаём .env

```bash
cp .env.example .env
nano .env
# Заполняем TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, TAVILY_API_KEY
```

### 3.3 Создаём директории

```bash
mkdir -p data logs backups
```

### 3.4 Собираем Docker-образ

```bash
docker compose build
```

### 3.5 Первичный ingest (наполнение KB)

```bash
docker compose run --rm ingest --source wikipedia --cities riga,sigulda,rundale
```

> ℹ️ Ingest может занять 5-10 минут. Следите за логами.

### 3.6 Запускаем бота

```bash
docker compose up -d bot
```

### 3.7 Проверяем статус

```bash
docker ps
# Должен быть container "bot" в состоянии UP

docker logs -f bot --tail=50
# Должно быть "Application started" или аналогичное
```

---

## 4. Настройка cron для backup

```bash
crontab -e
```

Добавить строку:
```
0 3 * * *  cd /opt/riga-guide && ./scripts/backup.sh >> logs/backup.log 2>&1
```

Бэкапы хранятся в `backups/YYYY-MM-DD/`, удаляются автоматически через 7 дней.

---

## 5. Smoke-тест после деплоя

### Чек-лист

- [ ] `/start` — бот отвечает приветствием на русском
- [ ] Отправить фото здания в Риге — бот отвечает (хотя бы interim ack)
- [ ] Отправить геолокацию рядом со Старой Ригой — бот показывает список мест
- [ ] Написать «Домский собор» — бот находит и рассказывает историю
- [ ] `/help` — отвечает справкой
- [ ] `/about` — отвечает информацией о боте
- [ ] `docker ps` — контейнер `bot` в состоянии UP
- [ ] `ls logs/bot.jsonl` — файл логов существует и растёт
- [ ] `cat logs/bot.jsonl | tail -3` — записи содержат `status`, `latency_ms`

### Если что-то не работает

```bash
# Логи бота
docker logs bot --tail=100

# Логи JSONL
cat logs/bot.jsonl | python -m json.tool | tail -20

# Перезапуск
docker compose restart bot

# Полная пересборка
docker compose down
docker compose build --no-cache
docker compose up -d bot
```

---

## 6. Обновление

```bash
cd /opt/riga-guide

# Останавливаем бота
docker compose stop bot

# Обновляем код
git pull

# Пересобираем
docker compose build

# Запускаем
docker compose up -d bot
```

### Обновление Knowledge Base

```bash
# Бот не нужно останавливать — Chroma перечитывается при запросе
docker compose run --rm ingest --source wikipedia --cities riga
```

---

## 7. Восстановление из бэкапа

```bash
docker compose stop bot
rm -rf data/chroma data/bot.db
cp -r backups/2026-04-15/chroma data/
cp    backups/2026-04-15/bot.db data/
docker compose start bot
```

---

## 8. Мониторинг

```bash
# Ежедневный отчёт по метрикам
python scripts/daily_rollup.py

# HITL тест (нужен .env с ключами)
python scripts/run_hitl.py --text-pack docs/hitl_text_pack.yaml
```
