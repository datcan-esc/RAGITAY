## Database

Local PostgreSQL runs with Docker Compose and includes `pgvector`.

Start:

```bash
docker compose up -d postgres
```

Stop:

```bash
docker compose stop postgres
```

Reset all database data:

```bash
docker compose down -v
```

Default connection values:

- host: `localhost`
- port: `5433`
- database: `ragitay`
- user: `ragitay`
- password: `ragitay`

If needed, copy `.env.example` to `.env` and change values.
