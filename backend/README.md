## Backend

FastAPI backend for the semantic/hybrid legal search API.

Suggested setup:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

Useful endpoints:

- `GET /health`
- `POST /api/search`
- `POST /api/search/summary`
- `GET /api/search/decisions/{decision_id}`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "iş yeri whatsapp kuralları",
    "source_names": ["yargitay"],
    "top_decisions": 5
  }'
```

Summary provider setup:

```bash
SUMMARY_PROVIDER=gemini
SUMMARY_MODEL_NAME=gemini-2.5-flash
GEMINI_API_KEY=your_key
```

Supported providers:

- `gemini`
- `openai`
- `fallback`
