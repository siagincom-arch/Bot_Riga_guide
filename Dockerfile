# === Stage 1: Dependencies ===
FROM python:3.12-slim AS deps

WORKDIR /app

# Системные зависимости для chromadb (SQLite, build tools)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[ingest]"

# === Stage 2: Application ===
FROM python:3.12-slim AS app

WORKDIR /app

# Копируем установленные пакеты из stage 1
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Копируем исходный код
COPY src/ ./src/
COPY ingest/ ./ingest/
COPY scripts/ ./scripts/

# Создаём директории для данных (маунтятся как volumes)
RUN mkdir -p /app/data /app/logs /app/backups

# Непривилегированный пользователь
RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

# PYTHONPATH чтобы импорты `from src.config import ...` работали
# src/ — полноценный пакет с __init__.py
ENV PYTHONPATH=/app

# По умолчанию запускаем бота
CMD ["python", "-m", "src.bot"]
