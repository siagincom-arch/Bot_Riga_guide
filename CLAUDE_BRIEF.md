# Riga Guide Bot — Project Brief for Claude

> **Date:** 2026-04-15
> **Status:** Research phase complete. Ready for User Spec / Tech Spec.
> **Methodology:** Molyanov (spec-driven pipeline)
> **Next step:** Create User Spec → Tech Spec → Architecture → Implementation

---

## 1. Project Overview

**What:** AI-powered Telegram bot that acts as a tour guide for Latvia.
**How it works:** User sends a photo of a landmark, geolocation, or text query → bot identifies the place → responds with a short encyclopedic summary (2-3 sentences) followed by a vivid storyteller-style narrative (7-8 sentences) with history, legends, and interesting facts.

**Target cities (MVP):** Riga, Sigulda, Rundāle (expandable to all Latvia).
**Target coverage:** 150-300 places in MVP.

---

## 2. Decisions Made

| # | Question | Decision |
|---|----------|----------|
| 1 | Bot language | **Russian only** |
| 2 | Input methods | **Photo + Geolocation + Text query** (all three) |
| 3 | Response style | **Hybrid:** 2-3 sentences encyclopedic summary, then 7-8 sentences vivid storyteller narrative |
| 4 | TTS / Audio | **Deferred** (not in MVP) |
| 5 | Deployment | **Self-hosted VPS** (owner's server) |
| 6 | LLM provider | **Google Gemini** |
| 7 | MVP scope | **150-300 places** across Riga, Sigulda, Rundāle |

---

## 3. Recommended Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Bot framework** | python-telegram-bot | Mature async library, well-documented |
| **Vision (photo recognition)** | Google Gemini 2.5 Flash/Pro | Best price/quality for landmark recognition |
| **RAG framework** | LangChain / LangGraph | Adaptive RAG pattern from reference project |
| **Vector store** | Chroma (MVP) → Pinecone (prod) | Chroma for local dev, Pinecone for scale |
| **LLM (text generation)** | Gemini 2.5 Flash | Fast, cheap, multilingual |
| **Web search (fallback)** | Tavily API | For real-time data (hours, prices, events) |
| **Database** | SQLite (MVP) → PostgreSQL (prod) | User data, cache, analytics |
| **Deployment** | Docker on owner's VPS | Self-hosted, full control |

---

## 4. Architecture

```
User (Telegram)
  │
  ├── Photo ──→ Vision Agent (Gemini Vision) ──→ Landmark ID
  ├── Geolocation ──→ Geo Resolver (reverse geocoding) ──→ Landmark ID
  └── Text query ──→ Text Search (vector similarity) ──→ Landmark ID
                                                            │
                                                            ▼
                                                     RAG Engine
                                                    ┌──────────────┐
                                                    │ Router        │
                                                    │  ↓            │
                                                    │ Retriever     │ ←── Knowledge Base (Chroma)
                                                    │  ↓            │
                                                    │ Web Search    │ ←── Tavily (fallback)
                                                    │  ↓            │
                                                    │ Context Grader│
                                                    │  ↓            │
                                                    │ Generator     │ ←── Gemini Flash
                                                    │  ↓            │
                                                    │ Hallucination │
                                                    │   Check       │
                                                    └──────┬───────┘
                                                           │
                                                           ▼
                                                    Response to User
                                                    ┌──────────────┐
                                                    │ 📖 Summary:   │
                                                    │ 2-3 sentences │
                                                    │ (encyclopedic)│
                                                    │               │
                                                    │ 🎭 Story:     │
                                                    │ 7-8 sentences │
                                                    │ (storyteller) │
                                                    └──────────────┘
```

---

## 5. Response Format Specification

Each bot response should follow this structure:

```
🏛️ [Landmark Name]

[2-3 sentences: factual, encyclopedic summary — what it is, when built, by whom, architectural style]

[7-8 sentences: vivid storyteller narrative — legends, historical anecdotes, little-known facts, 
atmosphere, what makes this place special. Written as if a passionate local guide is telling you 
the story in person.]

📍 [Address if available]
```

**Language:** Russian only.
**Tone:** The encyclopedic part is neutral and informative. The storyteller part is warm, engaging, literary — like a knowledgeable friend sharing secrets of the city.

---

## 6. Content Strategy — "3-Level Funnel"

### Level 1: Automated Scraping (for bulk data)

| Source | Language | Method |
|--------|----------|--------|
| latvia.travel | EN/RU/LV | Firecrawl → markdown |
| riga.lv/en/rigas-vesture | EN/LV | Firecrawl → markdown |
| UNESCO: Historic Centre of Riga | EN | API / scrape |
| rundale.net (history + legends) | EN/LV | Scrape + manual curation |
| Britannica: Riga | EN | API |
| Wikipedia (Riga + related) | Multi | Wikipedia API |
| Eupedia: Riga Travel Guide | EN | Scrape |

### Level 2: Curated Content (best for legends & stories)

| Source | Language | Value |
|--------|----------|-------|
| VoiceMap: Latvian Legends & History | EN | Living legends, ideal narrative tone |
| LiveJournal blogs (kot-bayun, kolllak) | RU | Literary style, photos, stories |
| ABHT (abht.lv) | RU/EN | Professional guide content |
| travellgide.ru/riga | RU | Structured info |
| Sputnik8 | RU | Professional guide descriptions |

### Level 3: Academic & Archival

| Source | Language | Value |
|--------|----------|-------|
| digitalabiblioteka.lv | LV/EN | Digitized historical texts |
| dom.lndb.lv (National Library) | LV | Academic publications |
| Peek: Riga Old Town Legends | EN | Paganism, Reformation, folklore |

> **Legal note:** Commercial source content should be used as INSPIRATION only for LLM-generated original texts, never copied directly.

---

## 7. Reference Projects (Top 3)

### 7.1 telegram-smartguide-bot (Closest analog)
- **What:** Telegram bot for Saint Petersburg
- **Stack:** Node.js, GPT-4o, Yandex Geosuggest
- **Pattern:** User sends geolocation → finds nearby places → GPT generates narrative
- **GitHub:** https://github.com/maslowivan/telegram-smartguide-bot

### 7.2 Discovery — aiagentsirl-hackathon (UX reference)
- **What:** 1st place hackathon project — point camera at landmark → AI describes + audio
- **Stack:** Flask, Gemma 3, Gemini 2.5, ElevenLabs, React Native
- **Pattern:** Vision Agent → Description Agent → Audio Agent pipeline
- **GitHub:** https://github.com/manfredi31/aiagentsirl-hackathon

### 7.3 travel-guide-adaptive-rag (Architecture reference)
- **What:** Adaptive RAG travel guide for Istanbul
- **Stack:** LangGraph, OpenAI, Chroma, Tavily, Gradio
- **Pattern:** Router → Retriever/Web Search → Grader → Generator → Hallucination Check
- **GitHub:** https://github.com/enesbesinci/travel-guide-adaptive-rag

---

## 8. Key Insight

> **Zero competition:** None of the 15 analyzed projects cover Latvia. This bot will be the first AI tour guide for Riga and Latvian landmarks.

---

## 9. Project Rules & Conventions

- **Communication language:** Russian (user-facing docs, README, PROTOCOL)
- **Code comments:** Russian
- **Tech docs (architecture, specs):** English
- **Code (variables, functions, classes):** English
- **Security:** No hardcoded secrets. Use `.env` files. Always `.gitignore` sensitive files.
- **Protocol:** Update `PROTOCOL.md` after each completed task (date, tasks, results, sources, insights).
- **Methodology:** Follow Molyanov pipeline — User Spec → Tech Spec → Architecture → Implementation → Testing → Deploy.

---

## 10. File Structure (Current)

```
Riga_guide/
├── PROTOCOL.md          # Session journal (active)
├── CLAUDE_BRIEF.md      # This file — project handoff brief
└── (next: docs/, src/, etc. — to be created during implementation)
```

---

## 11. Next Steps (Pipeline)

1. ✅ **Research** — Complete
2. ⏳ **User Spec** — Write detailed user specification (user stories, scenarios, UI/UX flows)
3. 🔲 **Tech Spec** — Detailed technical specification (API contracts, data models, integrations)
4. 🔲 **Architecture** — System design, component diagram, deployment diagram
5. 🔲 **Implementation** — Build MVP
6. 🔲 **Content Pipeline** — Scrape and curate 150-300 places
7. 🔲 **Testing** — Unit tests, integration tests, HITL testing
8. 🔲 **Deploy** — Docker on VPS

---

*This brief contains all context needed to continue development from any point.*
