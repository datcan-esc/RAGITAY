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

from ragitay.database import build_postgres_conninfo
from ragitay.embeddings import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL_NAME,
    prepare_passage_text,
)


SELECT_CHUNKS_WITHOUT_EMBEDDING_SQL = """
SELECT
  dc.id,
  dc.decision_id,
  dc.chunk_index,
  dc.section_name,
  dc.chunk_text,
  d.source_name,
  d.external_id
FROM decision_chunks dc
JOIN decisions d ON d.id = dc.decision_id
WHERE dc.embedding IS NULL
  AND dc.chunk_text <> ''
"""

SELECT_ALL_CHUNKS_SQL = """
SELECT
  dc.id,
  dc.decision_id,
  dc.chunk_index,
  dc.section_name,
  dc.chunk_text,
  d.source_name,
  d.external_id
FROM decision_chunks dc
JOIN decisions d ON d.id = dc.decision_id
WHERE dc.chunk_text <> ''
"""

UPDATE_EMBEDDING_SQL = """
UPDATE decision_chunks
SET embedding = %s
WHERE id = %s
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="decision_chunks tablosundaki embedding bosluklarini doldurur."
    )
    parser.add_argument(
        "--source-name",
        action="append",
        default=[],
        help="Sadece belirli kaynagi isler. Birden fazla kez verilebilir.",
    )
    parser.add_argument("--limit", type=int, default=0, help="En fazla N chunk isle.")
    parser.add_argument("--batch-size", type=int, default=32, help="Model encode batch boyutu.")
    parser.add_argument(
        "--model-name",
        default=DEFAULT_EMBEDDING_MODEL_NAME,
        help=f"SentenceTransformer model adi. Varsayilan: {DEFAULT_EMBEDDING_MODEL_NAME}",
    )
    parser.add_argument(
        "--device",
        default="",
        help="Opsiyonel device. Bos birakilirsa model kendi secimini yapar.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Mevcut embeddingleri yok sayip secilen chunklar icin yeniden uret.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_model(model_name: str, device: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers kurulu degil. `pip install -r ingestion/requirements.txt` calistirin."
        ) from exc

    kwargs: dict[str, object] = {}
    if device.strip():
        kwargs["device"] = device.strip()
    return SentenceTransformer(model_name, **kwargs)


def build_select_sql(args: argparse.Namespace) -> tuple[str, list[object]]:
    base_sql = SELECT_ALL_CHUNKS_SQL if args.rebuild else SELECT_CHUNKS_WITHOUT_EMBEDDING_SQL
    params: list[object] = []
    selected_sources = [value.strip() for value in args.source_name if value.strip()]

    if selected_sources:
        base_sql += " AND d.source_name = ANY(%s)"
        params.append(selected_sources)

    base_sql += " ORDER BY d.karar_tarihi DESC NULLS LAST, dc.id ASC"
    if args.limit > 0:
        base_sql += " LIMIT %s"
        params.append(args.limit)

    return base_sql, params


def build_embeddings(args: argparse.Namespace) -> int:
    try:
        import psycopg
        from pgvector.psycopg import Vector, register_vector
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "Veritabani embedding bagimliliklari eksik. `pip install -r ingestion/requirements.txt` calistirin."
        ) from exc

    select_sql, params = build_select_sql(args)
    conninfo = build_postgres_conninfo()
    selected_sources = [value.strip() for value in args.source_name if value.strip()]

    chunks_seen = 0
    newly_embedded = 0
    already_embedded = 0
    failed = 0

    model = load_model(args.model_name, args.device)

    with psycopg.connect(conninfo, row_factory=dict_row) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(select_sql, params)
            rows = cur.fetchall()

        chunks_seen = len(rows)
        if not args.rebuild:
            count_sql = """
                SELECT COUNT(*) AS count_value
                FROM decision_chunks dc
                JOIN decisions d ON d.id = dc.decision_id
                WHERE dc.embedding IS NOT NULL
            """
            count_params: list[object] = []
            if selected_sources:
                count_sql += " AND d.source_name = ANY(%s)"
                count_params.append(selected_sources)
            with conn.cursor() as cur:
                cur.execute(count_sql, count_params)
                already_embedded = int(cur.fetchone()["count_value"])

        print(f"Embedding uretilecek chunk sayisi: {chunks_seen}")
        if selected_sources:
            print(f"Kaynak filtresi: {', '.join(selected_sources)}")
        print(f"Model: {args.model_name}")

        if not rows:
            summary = {
                "chunks_seen": 0,
                "newly_embedded": 0,
                "already_embedded": already_embedded,
                "failed": 0,
                "model_name": args.model_name,
                "rebuild": bool(args.rebuild),
                "selected_sources": selected_sources,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print("EMBED_SUMMARY::" + json.dumps(summary, ensure_ascii=False))
            return 0

        prepared_texts = [prepare_passage_text(str(row["chunk_text"])) for row in rows]
        if any(not text for text in prepared_texts):
            raise RuntimeError("Bazi chunk_text degerleri embedding icin bos geldi.")

        batch_size = max(1, args.batch_size)

        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start : start + batch_size]
            batch_texts = prepared_texts[start : start + batch_size]
            try:
                vectors = model.encode(
                    batch_texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
            except Exception as exc:
                failed += len(batch_rows)
                print(f"Hata: batch start={start} -> {exc}")
                continue

            if len(vectors.shape) != 2 or vectors.shape[1] != DEFAULT_EMBEDDING_DIM:
                raise RuntimeError(
                    f"Beklenmeyen embedding boyutu: {vectors.shape}. Beklenen ikinci boyut {DEFAULT_EMBEDDING_DIM}."
                )

            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        for row, vector in zip(batch_rows, vectors):
                            cur.execute(
                                UPDATE_EMBEDDING_SQL,
                                (Vector(vector.tolist()), int(row["id"])),
                            )
            except Exception as exc:
                failed += len(batch_rows)
                print(f"Hata: batch yazimi start={start} -> {exc}")
                continue

            newly_embedded += len(batch_rows)
            if args.verbose:
                end = start + len(batch_rows)
                print(f"[{start + 1}-{end}/{len(rows)}] embedding yazildi")

    summary = {
        "chunks_seen": chunks_seen,
        "newly_embedded": newly_embedded,
        "already_embedded": already_embedded,
        "failed": failed,
        "model_name": args.model_name,
        "rebuild": bool(args.rebuild),
        "selected_sources": selected_sources,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("EMBED_SUMMARY::" + json.dumps(summary, ensure_ascii=False))
    return 0 if failed == 0 else 1


def main() -> None:
    args = parse_args()
    raise SystemExit(build_embeddings(args))


if __name__ == "__main__":
    main()
