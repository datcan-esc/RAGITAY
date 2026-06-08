# RAGITAY

RAGITAY is a Turkish legal RAG application for searching, reading, summarizing, and asking questions about judicial decisions. The system combines hybrid retrieval, vector search, structured legal metadata, and an LLM layer so users can work with legal documents through a simpler conversational interface.

The project is designed around one core idea: users should not need to read every full decision before understanding whether a result is relevant. RAGITAY first finds the most relevant decisions and passages, then uses an LLM only on a narrow, reference-backed context.

## What It Does

- Searches legal decisions with natural language queries.
- Combines semantic similarity and lexical matching for retrieval.
- Stores decisions with structured metadata, sectioned text, and full text.
- Splits decisions into searchable chunks and stores vector embeddings.
- Shows relevant passages and similarity scores.
- Produces a general AI summary for the search results.
- Generates an AI summary for a selected decision only when requested.
- Lets the user ask questions about one selected decision.
- Keeps LLM context small to control cost and reduce unsupported answers.

## System Overview

```text
User query
  -> Hybrid search
  -> Relevant decision chunks
  -> Grouped decision results
  -> Optional general LLM summary
  -> Selected decision detail
  -> Optional decision-specific summary / QA
```

The retrieval layer and LLM layer are intentionally separate.

- Retrieval decides which decisions and passages are relevant.
- The LLM explains only the selected or retrieved context.
- Full-document chat is limited to the selected decision, not the entire corpus.

## Architecture

```text
frontend/
  Next.js interface
  Search screen, filters, result list, detail panel, AI helper

backend/
  FastAPI service
  Hybrid search API, decision detail API, summary API, decision QA API

infra/
  PostgreSQL + pgvector schema

ingestion/
  Data normalization, database import, chunking, embedding utilities

docker-compose.yml
  PostgreSQL, backend, frontend services
```

## Data Model

RAGITAY stores legal decisions in two main tables.

### `decisions`

Each row represents one legal decision.

Important fields:

- `source_name`: source identifier, for example `yargitay` or `uyap_emsal`
- `external_id`: original source document id
- `daire`: chamber / court department
- `esas_no`: case number
- `karar_no`: decision number
- `karar_tarihi`: decision date
- `title`: display title
- `mahkeme`: lower court or related court metadata
- `outcome`: result such as `KABULÜNE`, `REDDİNE`, `BOZULMASINA`
- `sections`: extracted document sections as JSONB
- `full_text`: complete normalized decision text
- `document_metadata`: additional normalized metadata as JSONB

The pair `(source_name, external_id)` is unique, so imports are repeatable.

### `decision_chunks`

Each row represents a searchable section or text chunk from a decision.

Important fields:

- `decision_id`: parent decision
- `chunk_index`: chunk order inside the decision
- `section_name`: source section such as `dava`, `gerekce`, `karar`
- `chunk_text`: searchable passage text
- `chunk_chars`: passage length
- `embedding`: `VECTOR(768)` embedding for semantic search

This structure lets the system search small, meaningful passages instead of entire decisions.

## Normalized Decision Format

The system expects decisions to be normalized into a JSON-like structure before database import.

Example shape:

```json
{
  "source_name": "yargitay",
  "external_id": "1207018000",
  "daire": "9. Hukuk Dairesi",
  "esas_no": "2025/10011",
  "karar_no": "2026/1059",
  "karar_tarihi": "2026-02-10",
  "title": "9. Hukuk Dairesi 2025/10011 E. , 2026/1059 K.",
  "mahkeme": "İstanbul Bölge Adliye Mahkemesi 41. Hukuk Dairesi",
  "outcome": "",
  "source_url": "https://...",
  "sections": {
    "dava": "Davacı vekili dava dilekçesinde...",
    "ilk_derece_mahkemesi_karari": "İlk Derece Mahkemesinin...",
    "karar": "Açıklanan sebeplerle..."
  },
  "full_text": "Kararın tam metni..."
}
```

The database import process stores this as a decision record, then the chunking process creates section-aware passages under `decision_chunks`.

## Retrieval Flow

Search uses a hybrid approach:

- Semantic search: query embedding is compared against chunk embeddings with pgvector.
- Lexical search: query text is matched against chunk text and decision title.
- Section weighting: legally useful sections such as `gerekce`, `dava`, and `ilk_derece_mahkemesi_karari` are prioritized.
- Low-information chunks are filtered out.
- Results are grouped by decision and returned with the most relevant passages.

The visible similarity score is clamped to `0-100%` for user clarity.

## LLM Flow

RAGITAY avoids sending large result sets to an LLM.

Current LLM behavior:

- Search summary: produces a short general overview and key points from top results.
- Decision summary: generated only when the user requests it for a selected decision.
- Decision QA: answers only from the selected decision context.

Supported summary providers:

- `gemini`
- `openai`
- `fallback`

If no LLM key is configured, the system continues with fallback summaries.

## Backend API

Default backend URL:

```text
http://localhost:8000
```

Useful endpoints:

- `GET /health`
- `POST /api/search`
- `POST /api/search/summary`
- `GET /api/search/decisions/{decision_id}`
- `POST /api/search/decisions/{decision_id}/summary`
- `POST /api/search/decisions/{decision_id}/ask`

Example search request:

```bash
curl -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "whatsapp mesajlarına cevap vermediğim için işten çıkarıldım",
    "source_names": ["yargitay"],
    "daire": "9. Hukuk Dairesi",
    "year_from": 2020,
    "year_to": 2026,
    "top_decisions": 5
  }'
```

## Frontend

Default frontend URL:

```text
http://localhost:3000
```

The interface includes:

- centered search-first entry screen
- filter modal
- URL-backed query state
- general AI summary
- minimal decision result list
- decision detail panel
- full-text search inside a selected decision
- on-demand decision summary
- selected-decision QA
- light and dark theme support

## Running With Docker

```bash
docker compose up --build
```

Services:

- `postgres`: PostgreSQL with pgvector
- `backend`: FastAPI API server
- `frontend`: Next.js UI

Default ports:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- postgres: `localhost:5433`

## Environment Variables

Common variables:

```bash
POSTGRES_DB=ragitay
POSTGRES_USER=ragitay
POSTGRES_PASSWORD=ragitay
POSTGRES_PORT=5433

SUMMARY_PROVIDER=gemini
SUMMARY_MODEL_NAME=gemini-2.5-flash
GEMINI_API_KEY=your_key

NEXT_PUBLIC_SEARCH_API_BASE_URL=http://localhost:8000
BACKEND_CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

For local development without Docker:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

```bash
cd frontend
pnpm install
pnpm dev
```

## CORS Notes

The frontend runs in the browser, so its public API URL must point to the host-visible backend address.

For the default Docker setup:

```text
NEXT_PUBLIC_SEARCH_API_BASE_URL=http://localhost:8000
BACKEND_CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

If ports or domains change, update both values together.

## Design Principles

- Keep retrieval and generation separate.
- Store decisions in structured, repeatable records.
- Search chunks, not whole documents.
- Send only compact, relevant context to the LLM.
- Keep AI answers grounded in decision references.
- Avoid unnecessary LLM calls for unopened results.
- Preserve access to the full decision text for verification.

## Project Status

RAGITAY currently includes:

- PostgreSQL schema with pgvector
- hybrid legal search backend
- LLM-backed summary and selected-decision QA
- Next.js frontend
- Docker Compose setup
- light/dark theme support

The next major improvements would be search performance indexing, richer decision-level citations, and evaluation datasets for retrieval quality.
