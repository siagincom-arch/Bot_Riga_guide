# TECH SPEC — Riga Guide Bot

> **Date:** 2026-04-15
> **Phase:** Technical Specification (Molyanov pipeline, step 3 of 8)
> **Status:** Draft v1 — ready for owner review
> **Based on:** `CLAUDE_BRIEF.md`, `docs/USER_SPEC.md`
> **Next step:** Architecture document (`docs/ARCHITECTURE.md`)

---

## 1. Scope

This document defines the technical contract of the MVP: module boundaries, data models, APIs, external integrations, prompt schemas, and non-functional requirements. It does **not** describe deployment topology or code-level details — those live in Architecture and Implementation.

### 1.1 In scope
- Telegram bot handlers (photo / geo / text)
- RAG pipeline: router → retriever → web search fallback → grader → generator → hallucination check
- Knowledge base ingestion and schema
- Session memory (per-chat, short window)
- Logging, error handling, secrets management

### 1.2 Out of scope (MVP)
- Multi-language (EN/LV) — see User Spec §9
- TTS / audio generation
- User-contributed content / admin UI
- Route planning, morning digest
- Offline mode, caching on client

---

## 2. System Components

| # | Component | Responsibility | Tech |
|---|-----------|----------------|------|
| C1 | **Bot Gateway** | Receive Telegram updates, route by message type, return responses | python-telegram-bot (async) |
| C2 | **Vision Agent** | Identify landmark from a photo → return `(name, confidence, bbox?)` | Gemini 2.5 Flash (multimodal) |
| C3 | **Geo Resolver** | Given `(lat, lon)` → find nearby known landmarks within 300 m | Local SQLite index + Haversine |
| C4 | **Text Search** | Fuzzy match free-text query → landmark_id (handles translit, typos) | Chroma vector similarity + rapidfuzz |
| C5 | **RAG Engine** | Orchestrate router → retrieve → grade → generate → verify | LangGraph |
| C6 | **Knowledge Base** | Vector store with embedded passages about places | Chroma (local, persistent) |
| C7 | **Web Search Fallback** | Fetch fresh info when KB has low coverage | Tavily API |
| C8 | **Session Store** | Keep last N messages per `chat_id` for continuity | SQLite (MVP) |
| C9 | **LLM Generator** | Produce Russian two-part response (summary + story) | Gemini 2.5 Flash |
| C10 | **Hallucination Check** | Verify generated claims against retrieved context | Gemini 2.5 Flash (secondary call) |
| C11 | **Logger / Telemetry** | Structured logs, metric counters (M2–M5 from User Spec) | stdlib logging + JSON to file |

---

## 3. Data Model

### 3.1 `place` (canonical entry in Knowledge Base)

```
place_id:        str   # slug, e.g. "dome-cathedral-riga"
name_ru:         str   # "Домский собор"
name_original:   str   # "Rīgas Doms"
aliases:         list[str]   # ["Домский", "Dome Cathedral", "Рижский собор"]
city:            enum  # "riga" | "sigulda" | "rundale"
coords:          {lat: float, lon: float}
address:         str | null
categories:      list[str]   # ["church", "medieval", "unesco"]
passages:        list[Passage]  # embedded chunks (see 3.2)
summary_ru:      str | null    # optional pre-written encyclopedic 2-3 sentences
last_updated:    date
sources:         list[str]     # URLs used for content
```

### 3.2 `passage` (chunk stored in Chroma)

```
passage_id:   str
place_id:     str        # FK
text_ru:      str        # 100-400 words, Russian
topic:        enum       # "history" | "legend" | "architecture" | "fact" | "anecdote"
source:       str        # URL
embedding:    vector[768]   # Gemini text-embedding-004
```

### 3.3 `session` (per chat)

```
chat_id:        int         # Telegram chat id (PK)
last_place_id:  str | null  # for "еще легенда" / "что рядом" follow-ups
last_coords:    {lat, lon} | null
history:        list[Msg]   # rolling window, max 10 messages
updated_at:     datetime
```

Retention: sessions auto-evict after **24h inactivity**. Rationale: typical guest trip is 2–3 days; 24h window is enough for same-day continuity without unbounded growth.

### 3.4 `request_log` (telemetry)

```
ts:           datetime
chat_id:      int
input_type:   "photo" | "geo" | "text" | "callback"
landmark_id:  str | null
latency_ms:   int
status:       "ok" | "not_recognized" | "no_kb" | "llm_error" | "timeout"
recognized_confidence: float | null
```

---

## 4. Telegram API Contracts

### 4.1 Commands

| Command | Handler | Response |
|---------|---------|----------|
| `/start` | `on_start` | Greeting + 3 usage hints + inline examples |
| `/help` | `on_help` | Same content as `/start`, short |
| `/about` | `on_about` | One-liner: «пет-проект, ответы сгенерированы ИИ» |

### 4.2 Message handlers

| Trigger | Handler | Flow |
|---------|---------|------|
| `Message.photo` | `on_photo` | Vision → two-stage reply (Story 1, §5 User Spec) |
| `Message.location` | `on_location` | Geo resolver → list of ≤3 candidates with inline buttons |
| `Message.text` (not command) | `on_text` | Text search → if disambiguous, ask clarifier; else full answer |
| `CallbackQuery` `tell:<place_id>` | `on_tell_cb` | Generate full response for that place |
| `CallbackQuery` `more_legend:<place_id>` | `on_more_legend_cb` | Generate one extra legend/fact |
| `CallbackQuery` `nearby:<place_id>` | `on_nearby_cb` | Prompt for location |

### 4.3 Inline buttons under main answer

```
[🎭 Ещё легенда]   [📍 Что рядом]
```

---

## 5. RAG Pipeline

### 5.1 Graph (LangGraph)

```
[input] → route_by_type
           ├── photo  → vision_identify → interim_ack → retrieve
           ├── geo    → geo_nearby       → (list UI) ─╮
           └── text   → text_search       → retrieve ─┤
                                                      ▼
                                                  retrieve (Chroma top-k=6)
                                                      ▼
                                                 grade_context
                                            ┌─── sufficient? ───┐
                                           no                   yes
                                            ▼                    ▼
                                     web_search (Tavily)    generate_answer
                                            ▼                    ▼
                                     merge_context ──────→ hallucination_check
                                                                 ▼
                                                 pass? ──yes──→ send_to_user
                                                   │
                                                   no → regenerate (max 1 retry)
                                                            ▼
                                                         send with «возможно, неточно» marker
```

### 5.2 Node contracts

| Node | Input | Output | Timeout |
|------|-------|--------|---------|
| `vision_identify` | `{image_bytes}` | `{name, confidence, place_id?}` | 8 s |
| `geo_nearby` | `{lat, lon}` | `list[place_id]` (≤3, sorted by distance) | 1 s |
| `text_search` | `{query}` | `{place_id, candidates?}` | 2 s |
| `retrieve` | `{place_id}` | `list[Passage]` (top-6 by similarity) | 1 s |
| `grade_context` | `{passages}` | `{sufficient: bool, score: float}` | 2 s |
| `web_search` | `{place_name}` | `list[str]` (merged snippets) | 5 s |
| `generate_answer` | `{place, passages, session.history}` | `{summary_ru, story_ru}` | 10 s |
| `hallucination_check` | `{answer, passages}` | `{pass: bool, issues?: list}` | 5 s |

Total budget: p50 ≤ 20 s (matches M3 in User Spec).

### 5.3 Confidence thresholds

- `vision.confidence < 0.5` → treat as not recognized (E1, User Spec §7)
- `grade_context.score < 0.6` → trigger `web_search`
- `hallucination_check.pass == false` → 1 retry, then mark as uncertain

---

## 6. Prompts

All prompts are in Russian. Stored as Jinja-style templates in `src/prompts/*.j2`.

### 6.1 Generator prompt (skeleton)

```
Ты — рижанин, влюблённый в свой город. Отвечай только по-русски.

Место: {{ place.name_ru }}
Контекст (проверенные факты):
{% for p in passages %}— {{ p.text_ru }}
{% endfor %}

Недавний диалог с пользователем (для связности):
{{ session.history[-4:] | format }}

Сформируй ответ строго в двух блоках:
1) «Справка» — 2-3 предложения, нейтрально, энциклопедически.
2) «История» — 7-8 предложений, тепло, с легендами/анекдотами/атмосферой.

Запрещено: выдумывать даты, имена, адреса, которых нет в контексте.
Если контекста мало — говори честно, не фантазируй.
```

### 6.2 Hallucination check prompt

```
Ниже — список фактов из проверенного контекста и сгенерированный ответ.
Проверь, все ли утверждения ответа подкреплены контекстом.
Верни JSON: {"pass": bool, "issues": ["...", "..."]}
```

### 6.3 Vision prompt

```
На фото — здание или памятник в Латвии (скорее всего в Риге, Сигулде или Рундале).
Определи название на русском и на латышском. Верни JSON:
{"name_ru": "...", "name_lv": "...", "confidence": 0.0-1.0,
 "why": "короткое обоснование"}
Если не уверен (confidence < 0.5) — всё равно верни лучшую догадку.
```

---

## 7. Knowledge Base Pipeline

### 7.1 Ingestion steps

1. **Collect:** Firecrawl / Wikipedia API / manual Markdown for each source (see User Spec §9 non-goals — no user contributions).
2. **Normalize:** strip HTML, dedupe, split into 100–400-word chunks.
3. **Enrich:** tag each chunk with `topic` (history / legend / architecture / fact / anecdote) via LLM classifier.
4. **Embed:** Gemini `text-embedding-004` → Chroma collection `places_ru`.
5. **Index geospatial:** SQLite table `place_coords` with `(place_id, lat, lon)` for Haversine queries.

### 7.2 Content budget (MVP)

- Places: 150–300 (per decision D7)
- Chunks per place: 3–8
- Expected total chunks: ~1 200
- Storage: Chroma ≤ 200 MB

### 7.3 Re-ingestion

Manual trigger via CLI `python -m ingest --source rundale.net`. No automatic re-crawl in MVP.

---

## 8. External Integrations

| Service | Purpose | Auth | Rate limit concern |
|---------|---------|------|--------------------|
| Telegram Bot API | Transport | `TELEGRAM_BOT_TOKEN` | 30 msg/s per bot (plenty) |
| Gemini API | Vision + Text + Embeddings + Checker | `GEMINI_API_KEY` | Free tier: 15 RPM Flash — sufficient for personal use; monitor |
| Tavily API | Web search fallback | `TAVILY_API_KEY` | 1000 req/month free |
| Chroma | Local vector store | n/a (embedded) | — |

No other third-party calls in MVP.

---

## 9. Session Memory (Q5 from User Spec §11)

- **Storage:** SQLite table `sessions`.
- **Scope:** per `chat_id`.
- **Window:** last **10 messages** (≈ 5 user + 5 bot exchanges).
- **Used by:** `generate_answer` (last 4 messages) and follow-up handlers (`more_legend`, `nearby` rely on `last_place_id`).
- **Reset:** `/start` clears session; auto-evict after 24 h idle.

---

## 10. Configuration

All config via environment variables (loaded from `.env`, never committed). Brief §9 rule.

```
TELEGRAM_BOT_TOKEN=
GEMINI_API_KEY=
TAVILY_API_KEY=

CHROMA_PATH=./data/chroma
SQLITE_PATH=./data/bot.db
LOG_PATH=./logs/bot.jsonl
LOG_LEVEL=INFO

RAG_TOP_K=6
RAG_GRADE_THRESHOLD=0.6
VISION_CONFIDENCE_THRESHOLD=0.5
SESSION_WINDOW=10
SESSION_TTL_HOURS=24
NEARBY_RADIUS_M=300
```

---

## 11. Error Handling

| Error | User-facing behaviour | Internal |
|-------|-----------------------|----------|
| Vision API 5xx / timeout | «Не могу сейчас рассмотреть фото, попробуй ещё раз» | Log + retry once |
| LLM API 5xx / timeout | «Подвис на секунду, пришли запрос ещё раз» | Log, no retry |
| Tavily failure | Silent fallback: skip web search, use KB only | Log warning |
| Chroma empty for place | Use `place.summary_ru` if present; else «у меня пока нет глубокой истории» | Log info |
| Unknown Telegram update type | Ignore | Log debug |

All user-facing strings centralised in `src/i18n/ru.py` — single source of truth.

---

## 12. Logging & Telemetry

Structured JSON logs, one record per request. Fields: see `request_log` (§3.4).

Daily rollup script computes:
- M2: `ok / total` ratio
- M3: p50 / p95 latency per `input_type`
- M4: recognition success on a fixed set of 20 known photos (manual test)
- M5: messages per `chat_id` over trailing 3 days

Dashboard: not in MVP (grep + tiny Python script).

---

## 13. Security

- Secrets only via `.env`; `.gitignore` covers `.env`, `data/`, `logs/`.
- No PII stored beyond Telegram `chat_id` and message text. First-name not stored.
- Rate-limit per `chat_id`: ≤ 30 requests / minute (prevents runaway LLM cost).
- No admin commands in MVP (Q3 decided: no user-contributed content).

---

## 14. Performance Budgets

| Scenario | p50 | p95 |
|----------|-----|-----|
| `/start` | 0.3 s | 1 s |
| Text query (known place, KB hit) | 3 s | 7 s |
| Photo (Vision + RAG) | 12 s | 25 s |
| Geo nearby | 1 s | 3 s |
| «Ещё легенда» | 4 s | 9 s |

Matches User Spec M3.

---

## 15. Decisions for Architecture step (confirmed 2026-04-15)

| # | Question | Decision |
|---|----------|----------|
| 1 | Deployment unit | **Single Python process, single Docker container.** Bot + RAG + session store co-located; ingest runs as a separate one-shot CLI container sharing volumes. |
| 2 | Ingest automation | **Manual one-shot CLI** (`python -m ingest ...`). No cron in MVP. |
| 3 | Backup | **Nightly rsync** of `data/chroma` and `data/bot.db` to `backups/YYYY-MM-DD/`, 7-day rolling retention. |
| 4 | Logs shipping | **Local only** (`logs/bot.jsonl`). No external log aggregation in MVP. |

---

## 16. Readiness Checklist

- [x] Components enumerated
- [x] Data model defined
- [x] Telegram contracts specified
- [x] RAG graph and node contracts written
- [x] Prompts skeletoned (Russian)
- [x] KB ingestion path defined
- [x] External integrations listed
- [x] Session memory spec closed (Q5)
- [x] Config, logging, security covered
- [x] Performance budgets aligned with User Spec M3
- [ ] Owner review ← **blocks Architecture step**
