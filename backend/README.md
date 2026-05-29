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
