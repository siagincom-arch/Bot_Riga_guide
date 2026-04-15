# ARCHITECTURE — Riga Guide Bot

> **Date:** 2026-04-15
> **Phase:** Architecture (Molyanov pipeline, step 4 of 8)
> **Status:** Draft v1 — ready for owner review
> **Based on:** `CLAUDE_BRIEF.md`, `docs/USER_SPEC.md`, `docs/TECH_SPEC.md`
> **Next step:** Implementation (step 5)

---

## 1. Architecture Goals

- **Simple to operate:** one container, one owner. Cold-start in < 30 s, restart in < 5 s.
- **Cheap to run:** Gemini Flash + Tavily free tier + self-hosted VPS. Target: < 5 € / month at expected volume.
- **Isolated failures:** LLM or Tavily outage must not crash the bot process; it should degrade gracefully.
- **Deterministic ingest:** re-running `ingest` on the same sources must yield a stable KB (idempotent chunks).
- **Readable code:** single-repo Python, one process, minimal magic. Future-me must be able to modify it 6 months later.

---

## 2. High-Level View

```
┌──────────────┐           ┌─────────────────────────────────────────┐
│   Telegram   │◀─────────▶│            Bot Container                 │
│    Users     │  webhook  │                                          │
└──────────────┘  or long  │  ┌────────────┐    ┌─────────────────┐  │
                  polling  │  │  Gateway   │───▶│  RAG Engine     │  │
                           │  │ (handlers) │◀───│  (LangGraph)    │  │
                           │  └─────┬──────┘    └──────┬──────────┘  │
                           │        │                  │             │
                           │        ▼                  ▼             │
                           │  ┌────────────┐    ┌─────────────────┐  │
                           │  │  Session   │    │    Chroma       │  │
                           │  │  (SQLite)  │    │  (persistent)   │  │
                           │  └────────────┘    └─────────────────┘  │
                           │        ▲                  ▲             │
                           └────────┼──────────────────┼─────────────┘
                                    │                  │
                            ┌───────┴──────┐    ┌──────┴──────────┐
                            │   data/      │    │   Ingest CLI    │
                            │  bot.db      │    │  (one-shot)     │
                            │  chroma/     │◀───│                 │
                            └──────────────┘    └─────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  backups/    │  nightly rsync
                            │  YYYY-MM-DD/ │
                            └──────────────┘

External calls: Gemini API, Tavily API  (all via HTTPS, no inbound)
```

---

## 3. Deployment View

### 3.1 Single-host topology (MVP)

- **Host:** owner's VPS (Linux).
- **Runtime:** Docker Compose with 2 services:
  - `bot` — long-running Python process, restart=`unless-stopped`.
  - `ingest` — on-demand, `docker compose run --rm ingest ...`. Not started with `up`.
- **Shared volumes:**
  - `./data` → `/app/data` (Chroma + SQLite) — writable by both services.
  - `./logs` → `/app/logs` (JSONL) — bot-only.
  - `./backups` → `/app/backups` — written by host cron, not container.
- **Telegram transport:** **long polling** (simpler — no public TLS endpoint needed on owner's VPS). Webhook migration is a future option (see §11).
- **Network:** only outbound HTTPS (Telegram, Gemini, Tavily). No inbound ports exposed.

### 3.2 docker-compose (logical, not final code)

```
services:
  bot:
    build: .
    env_file: .env
    volumes: [./data:/app/data, ./logs:/app/logs]
    restart: unless-stopped
    command: python -m bot

  ingest:
    build: .
    env_file: .env
    volumes: [./data:/app/data]
    profiles: ["manual"]        # not started by default
    command: python -m ingest
```

### 3.3 Host cron

Single entry on the VPS (not in container):
```
0 3 * * *  cd /opt/riga-guide && ./scripts/backup.sh
```
`backup.sh` does `rsync data/ backups/$(date +\%F)/` and prunes anything older than 7 days.

---

## 4. Project Structure (proposed)

```
Riga_guide/
├── CLAUDE_BRIEF.md
├── PROTOCOL.md
├── docs/
│   ├── USER_SPEC.md
│   ├── TECH_SPEC.md
│   └── ARCHITECTURE.md           ← this file
├── src/
│   ├── bot/
│   │   ├── __main__.py           # entry point: python -m bot
│   │   ├── gateway.py            # handlers: on_start, on_photo, on_location, on_text, callbacks
│   │   ├── ui.py                 # inline keyboards, text formatting for Telegram
│   │   └── i18n_ru.py            # all user-facing strings (single source of truth)
│   ├── rag/
│   │   ├── graph.py              # LangGraph assembly
│   │   ├── nodes/
│   │   │   ├── vision.py
│   │   │   ├── geo.py
│   │   │   ├── text_search.py
│   │   │   ├── retrieve.py
│   │   │   ├── grade.py
│   │   │   ├── web_search.py
│   │   │   ├── generate.py
│   │   │   └── halluck_check.py
│   │   └── prompts/              # .j2 templates (RU)
│   │       ├── generator.j2
│   │       ├── halluck.j2
│   │       └── vision.j2
│   ├── kb/
│   │   ├── store.py              # Chroma wrapper
│   │   └── models.py             # Pydantic: Place, Passage
│   ├── session/
│   │   ├── store.py              # SQLite wrapper
│   │   └── models.py             # Session, Msg
│   ├── llm/
│   │   ├── gemini.py             # thin client: generate, embed, vision
│   │   └── tavily.py
│   ├── telemetry/
│   │   └── log.py                # structured JSON logger
│   └── config.py                 # env loading (pydantic-settings)
├── ingest/
│   ├── __main__.py               # python -m ingest
│   ├── scrapers/
│   │   ├── wikipedia.py
│   │   ├── firecrawl.py
│   │   └── rundale.py
│   ├── chunker.py
│   ├── tagger.py                 # LLM classifier: history/legend/...
│   └── pipeline.py               # orchestration
├── scripts/
│   ├── backup.sh                 # called by host cron
│   └── daily_rollup.py           # computes M2-M5 metrics from logs
├── tests/
│   ├── unit/
│   ├── integration/              # real Chroma, real SQLite, mocked LLM
│   └── fixtures/
├── data/                         # .gitignored, created at runtime
├── logs/                         # .gitignored
├── backups/                      # .gitignored
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

Rationale: clean separation between **bot transport** (`src/bot/`), **intelligence** (`src/rag/`), **state** (`src/kb/`, `src/session/`), and **offline tooling** (`ingest/`). Each subpackage has one reason to change.

---

## 5. Key Runtime Sequences

### 5.1 Photo flow (Golden Path — User Spec §5 Story 1)

```
User          Gateway          Vision      Interim      RAG Graph      LLM        Telegram
 │  photo       │                │            │             │            │            │
 │─────────────▶│                │            │             │            │            │
 │              │  identify      │            │             │            │            │
 │              │───────────────▶│            │             │            │            │
 │              │                │ Gemini Vis.│             │            │            │
 │              │◀───name,conf───│            │             │            │            │
 │              │                │            │             │            │            │
 │              │──"Вижу X, собираю историю…"────────────────────────────────────────▶│
 │              │                                                                     │
 │              │  run(place_id)                          │                           │
 │              │────────────────────────────────────────▶│                           │
 │              │                                          │ retrieve, grade,         │
 │              │                                          │ maybe web, generate,     │
 │              │                                          │ halluck check            │
 │              │◀───summary + story───────────────────────│                           │
 │              │                                                                     │
 │              │──formatted response + inline buttons───────────────────────────────▶│
 │              │  (edit interim message OR send new)                                 │
 │              │                                                                     │
 │              │  session.update(last_place_id, history)                             │
```

Notes:
- Interim ack is sent as a **new message** (not an edit) so the user gets a notification. Final answer is also a new message. This keeps the chat chronological.
- Session update is fire-and-forget after response; failure to persist session is logged but not shown to user.

### 5.2 Geo flow

```
User sends location → Gateway → geo_nearby (SQLite Haversine on place_coords)
                                 └─ returns top-3 within 300 m
                    → Gateway sends message with 3 inline buttons [tell:<id>]
                    → User taps button → on_tell_cb → RAG generate → full answer
```

### 5.3 Text flow

```
User types "домский собор"
  → text_search (Chroma semantic + rapidfuzz fallback on aliases)
  → single match (score ≥ 0.7) → RAG generate
  → multiple matches within 0.05 of each other → clarifier with 2-3 inline buttons
  → no match (score < 0.5) → fallback: generic search via Tavily wrapped in formatted response
```

### 5.4 Follow-up «Ещё легенда»

```
Callback more_legend:<place_id> → Gateway loads session.history + place passages
  → generate with prompt variant that EXCLUDES already-told facts
    (passes last 4 session messages as "already said" hint)
  → new story block only (no summary duplication)
```

### 5.5 Ingest flow (offline)

```
operator:  docker compose run --rm ingest --source wikipedia --city riga

ingest/__main__.py
  │
  ├── scrapers/wikipedia.fetch(city) → list[RawDoc]
  ├── chunker.split(RawDoc) → list[TextChunk]   (100-400 words)
  ├── tagger.classify(TextChunk) → Passage       (topic label via Gemini)
  ├── llm.gemini.embed_batch(passages)
  ├── kb.store.upsert(place, passages)           (Chroma + place_coords table)
  └── report: N places, M chunks, errors
```

Idempotency: `passage_id = sha256(place_id + source + text[:200])`. Re-running skips unchanged chunks.

---

## 6. Failure Modes & Recovery

| Failure | Immediate behaviour | Recovery | User impact |
|---------|---------------------|----------|-------------|
| Gemini API 5xx during Vision | Interim ack not sent; reply «не могу сейчас рассмотреть фото» | 1 retry with backoff, then give up | Asked to retry |
| Gemini API 5xx during Generate | If interim already sent: reply «подвис, пришли запрос ещё раз» | No auto-retry (cost control) | Interim message orphaned (acceptable) |
| Tavily outage | Silent: skip web fallback, use KB only | — | Slightly less fresh data |
| Chroma corruption | Bot crashes at startup → Docker restarts → fails again | Restore from latest `backups/YYYY-MM-DD/` | Bot unavailable until manual restore |
| SQLite lock | Retry 3 times with jitter | If still locked → log, proceed without session update | No session memory for that turn |
| `.env` missing | Bot fails to start, loud log | Manual fix | Total outage |
| Rate-limit hit (Gemini 15 RPM) | Bot replies «подожди минуту, я перегружен» | Per-chat token bucket (30 req/min) throttles upstream | Throttled response |

**Observation:** no failure mode requires paging. Owner checks `logs/bot.jsonl` and `docker ps` the next morning.

---

## 7. Testing Strategy

### 7.1 Unit tests (`tests/unit/`)
- Pure functions: chunker, Haversine, prompt rendering, i18n string lookup.
- Node-level with mocked clients: `retrieve`, `grade_context`, `halluck_check` logic branches.
- No network, no disk beyond tmp.

### 7.2 Integration tests (`tests/integration/`)
- Real Chroma (in-memory or tmp dir), real SQLite (tmp file), **mocked** Gemini / Tavily.
- End-to-end LangGraph run on a fixture KB of 3 places.
- Golden-file assertions on graph state transitions (not on LLM text, which is non-deterministic).

### 7.3 HITL smoke tests (manual)
- Fixed set of 20 known-good photos of Riga landmarks → check recognition (maps to User Spec M4).
- Fixed set of 10 text queries with typos → check resolution.
- Executed before each deploy and after any change to prompts.

### 7.4 What we intentionally don't test in MVP
- LLM output quality (subjective — handled via M1 owner feedback).
- Load / stress (single-user scale).
- Browser / mobile UI (Telegram client is not ours).

---

## 8. Observability

### 8.1 Sources
- `logs/bot.jsonl` — per-request structured log (fields from Tech Spec §3.4).
- `docker logs bot` — runtime errors (complementary, ephemeral).

### 8.2 Daily rollup
`scripts/daily_rollup.py` (run manually or weekly):
- Reads yesterday's JSONL.
- Prints M2 (success ratio), M3 (p50/p95 latency), M5 (per-chat message counts).
- Outputs a plain text report to stdout.

No dashboards, no alerts in MVP. If the bot goes down, owner notices because guests tell them.

---

## 9. Security Model

- **Trust boundary:** everything inside the Docker container is trusted. Telegram, Gemini, Tavily are external and untrusted; all I/O with them is over HTTPS.
- **Secrets:** `.env` on host, mounted read-only into container via `env_file`. Never logged (logger scrubs `*_API_KEY` and `*_TOKEN` keys).
- **Input handling:** user text is never `eval`ed or used to build shell commands. Photo bytes are passed to Gemini directly, never written to disk.
- **PII:** `chat_id` is stored (needed for session). Telegram `first_name` / `username` are **not** stored. Logs contain `chat_id` + first 100 chars of text query — acceptable for personal-scale bot.
- **Rate-limit:** per-`chat_id` token bucket (30/min), enforced in Gateway before touching LLM.
- **Backups:** contain no user messages (only KB + session table with `chat_id`+history). Stored on same host as bot; not encrypted at rest (acceptable for personal use, documented risk).

---

## 10. Dependency Map (Python)

```
Runtime (bot):
  python-telegram-bot ≥ 21       # transport
  langgraph                       # RAG orchestration
  langchain-core                  # just the types / runnable interface
  google-generativeai             # Gemini client
  chromadb                        # vector store
  sqlalchemy + sqlite             # session + place_coords (thin usage)
  pydantic, pydantic-settings     # config + models
  tavily-python                   # web search
  jinja2                          # prompt templating
  rapidfuzz                       # text matching
  structlog                       # JSON logger

Ingest (adds):
  requests, beautifulsoup4        # fallback scraping
  firecrawl-py                    # primary scraping
  wikipedia                       # API wrapper

Dev:
  pytest, pytest-asyncio
  respx / pytest-httpx            # mock external HTTP
  ruff, mypy
```

No runtime dependency on LangChain heavyweight modules — only the core types used by LangGraph.

---

## 11. Post-MVP Migration Hints (not implemented now)

Documented so future refactors are cheap, not as commitments:

- **Webhook instead of long polling** — needed once the bot is shared publicly.
- **Postgres replaces SQLite** — only if multi-process is needed (unlikely for this scope).
- **Pinecone replaces Chroma** — only if KB grows > 10k chunks.
- **Separate ingest service** — only if scraping becomes scheduled.
- **External log shipping** — only if owner stops checking JSONL manually.

None of these affect the interfaces defined in Tech Spec §2–§5, so migration is local.

---

## 12. Build & Run (operational contract)

### First run
```
cp .env.example .env
# fill in tokens
mkdir -p data logs backups
docker compose build
docker compose run --rm ingest --source wikipedia --cities riga,sigulda,rundale
docker compose up -d bot
```

### Routine update of KB
```
docker compose run --rm ingest --source rundale.net
# bot does not need restart — Chroma is re-read lazily per query
```

### Backup restore
```
docker compose stop bot
rm -rf data/chroma data/bot.db
cp -r backups/2026-04-14/chroma data/
cp    backups/2026-04-14/bot.db data/
docker compose start bot
```

---

## 13. Architecture Decision Log (ADL)

| ADR | Decision | Consequence |
|-----|----------|-------------|
| ADR-1 | Single Python process, single container | Simpler ops; must keep bot non-blocking (async). |
| ADR-2 | Long polling, not webhook | No need for TLS / reverse proxy; lose webhook speed. |
| ADR-3 | SQLite for session state | Fine for single-process; must migrate if we ever scale horizontally. |
| ADR-4 | Ingest as a separate Compose service sharing volumes | Clean separation of concerns; small duplication of image. |
| ADR-5 | Interim ack sent as a new message, not an edit | Guarantees push notification (per Telegram MCP note about edits). |
| ADR-6 | No external log aggregation | Zero ops overhead; owner must manually inspect. |
| ADR-7 | `rapidfuzz` fallback alongside vector search for text | Catches transliterations and typos that embeddings miss. |
| ADR-8 | Passage id = hash(place + source + text[:200]) | Idempotent re-ingest; reduces accidental duplicates. |

---

## 14. Readiness Checklist

- [x] High-level component diagram
- [x] Deployment topology (single VPS, Compose)
- [x] Project structure proposal
- [x] Key sequences drawn (photo, geo, text, follow-up, ingest)
- [x] Failure modes enumerated
- [x] Testing strategy defined
- [x] Observability plan
- [x] Security model
- [x] Dependency map
- [x] Operational contract (run / backup / restore)
- [x] ADR log
- [ ] Owner review ← **blocks Implementation step**

---

*Next step: `docs/IMPLEMENTATION_PLAN.md` — ordered list of PRs / milestones with acceptance criteria, or jump straight to skeleton code if owner prefers.*
