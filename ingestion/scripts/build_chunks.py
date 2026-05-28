from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
INGESTION_ROOT = CURRENT_FILE.parents[1]
SRC_ROOT = INGESTION_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ragitay.chunking import build_decision_chunks
from ragitay.database import build_postgres_conninfo


SELECT_DECISIONS_WITHOUT_CHUNKS_SQL = """
SELECT
  d.id,
  d.source_name,
  d.external_id,
  d.title,
  d.full_text,
  d.sections
FROM decisions d
LEFT JOIN decision_chunks dc ON dc.decision_id = d.id
WHERE dc.id IS NULL
"""

SELECT_ALL_DECISIONS_SQL = """
SELECT
  d.id,
  d.source_name,
  d.external_id,
  d.title,
  d.full_text,
  d.sections
FROM decisions d
"""

INSERT_CHUNK_SQL = """
INSERT INTO decision_chunks (
  decision_id,
  chunk_index,
  section_name,
  chunk_text,
  chunk_chars
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (decision_id, chunk_index) DO UPDATE SET
  section_name = EXCLUDED.section_name,
  chunk_text = EXCLUDED.chunk_text,
  chunk_chars = EXCLUDED.chunk_chars,
  embedding = CASE
    WHEN decision_chunks.section_name IS DISTINCT FROM EXCLUDED.section_name
      OR decision_chunks.chunk_text IS DISTINCT FROM EXCLUDED.chunk_text
      OR decision_chunks.chunk_chars IS DISTINCT FROM EXCLUDED.chunk_chars
    THEN NULL
    ELSE decision_chunks.embedding
  END
"""

DELETE_CHUNKS_SQL = "DELETE FROM decision_chunks WHERE decision_id = %s"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decisions tablosundaki metinleri decision_chunks tablosuna boler.")
    parser.add_argument(
        "--source-name",
        action="append",
        default=[],
        help="Sadece belirli kaynagi isler. Birden fazla kez verilebilir.",
    )
    parser.add_argument("--limit", type=int, default=0, help="En fazla N karar isle.")
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap-chars", type=int, default=200)
    parser.add_argument("--min-chars", type=int, default=300)
    parser.add_argument("--rebuild", action="store_true", help="Var olan chunklari silip yeniden uret.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def maybe_jsonb_to_dict(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(text) for key, text in value.items()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {str(key): str(text) for key, text in parsed.items()}
    return {}


def import_chunks(args: argparse.Namespace) -> int:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "psycopg kurulu degil. `pip install -r ingestion/requirements.txt` calistirin."
        ) from exc

    selected_sources = [value.strip() for value in args.source_name if value.strip()]
    base_sql = SELECT_ALL_DECISIONS_SQL if args.rebuild else SELECT_DECISIONS_WITHOUT_CHUNKS_SQL
    where_clauses: list[str] = []
    params: list[object] = []

    if selected_sources:
        where_clauses.append("d.source_name = ANY(%s)")
        params.append(selected_sources)

    if where_clauses:
        if "WHERE" in base_sql:
            base_sql += " AND " + " AND ".join(where_clauses)
        else:
            base_sql += " WHERE " + " AND ".join(where_clauses)

    base_sql += " ORDER BY d.karar_tarihi DESC NULLS LAST, d.id DESC"
    if args.limit > 0:
        base_sql += " LIMIT %s"
        params.append(args.limit)

    conninfo = build_postgres_conninfo()
    decisions_seen = 0
    decisions_chunked = 0
    decisions_skipped = 0
    chunks_written = 0
    failed = 0

    with psycopg.connect(conninfo, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()

        print(f"Chunklenecek karar sayisi: {len(rows)}")
        if selected_sources:
            print(f"Kaynak filtresi: {', '.join(selected_sources)}")

        with conn.cursor() as cur:
            for index, row in enumerate(rows, start=1):
                decisions_seen += 1
                decision_id = int(row["id"])
                title = str(row.get("title") or "")
                full_text = str(row.get("full_text") or "")
                sections = maybe_jsonb_to_dict(row.get("sections"))

                chunks = build_decision_chunks(
                    title=title,
                    full_text=full_text,
                    sections=sections,
                    max_chars=args.max_chars,
                    overlap_chars=args.overlap_chars,
                    min_chunk_chars=args.min_chars,
                )

                if not chunks:
                    decisions_skipped += 1
                    if args.verbose:
                        print(f"[{index}/{len(rows)}] decision_id={decision_id} -> chunk yok, atlandi")
                    continue

                try:
                    with conn.transaction():
                        if args.rebuild:
                            cur.execute(DELETE_CHUNKS_SQL, (decision_id,))
                        for chunk in chunks:
                            cur.execute(
                                INSERT_CHUNK_SQL,
                                (
                                    decision_id,
                                    int(chunk["chunk_index"]),
                                    str(chunk["section_name"]),
                                    str(chunk["chunk_text"]),
                                    int(chunk["chunk_chars"]),
                                ),
                            )
                except Exception as exc:
                    failed += 1
                    print(f"Hata: decision_id={decision_id} -> {exc}")
                    continue

                decisions_chunked += 1
                chunks_written += len(chunks)
                if args.verbose:
                    print(
                        f"[{index}/{len(rows)}] decision_id={decision_id}"
                        f" source={row.get('source_name','')}"
                        f" external_id={row.get('external_id','')}"
                        f" -> {len(chunks)} chunk"
                    )

    summary = {
        "decisions_seen": decisions_seen,
        "decisions_chunked": decisions_chunked,
        "decisions_skipped": decisions_skipped,
        "chunks_written": chunks_written,
        "failed": failed,
        "selected_sources": selected_sources,
        "rebuild": bool(args.rebuild),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("CHUNK_SUMMARY::" + json.dumps(summary, ensure_ascii=False))
    return 0 if failed == 0 else 1


def main() -> None:
    args = parse_args()
    raise SystemExit(import_chunks(args))


if __name__ == "__main__":
    main()
