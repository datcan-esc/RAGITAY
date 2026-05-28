from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
INGESTION_ROOT = CURRENT_FILE.parents[1]
SRC_ROOT = INGESTION_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ragitay.database import build_postgres_conninfo
from ragitay.paths import OUTPUT_ROOT


UPSERT_DECISION_SQL = """
INSERT INTO decisions (
  source_name,
  external_id,
  daire,
  esas_no,
  karar_no,
  karar_tarihi,
  aranan_kelime,
  durum,
  title,
  mahkeme,
  outcome,
  source_url,
  run_name,
  sections,
  full_text,
  document_metadata,
  raw_document_path,
  parsed_at
)
VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
  %s::jsonb, %s, %s::jsonb, %s, %s
)
ON CONFLICT (source_name, external_id) DO UPDATE SET
  daire = EXCLUDED.daire,
  esas_no = EXCLUDED.esas_no,
  karar_no = EXCLUDED.karar_no,
  karar_tarihi = EXCLUDED.karar_tarihi,
  aranan_kelime = EXCLUDED.aranan_kelime,
  durum = EXCLUDED.durum,
  title = EXCLUDED.title,
  mahkeme = EXCLUDED.mahkeme,
  outcome = EXCLUDED.outcome,
  source_url = EXCLUDED.source_url,
  run_name = EXCLUDED.run_name,
  sections = EXCLUDED.sections,
  full_text = EXCLUDED.full_text,
  document_metadata = EXCLUDED.document_metadata,
  raw_document_path = EXCLUDED.raw_document_path,
  parsed_at = EXCLUDED.parsed_at,
  updated_at = NOW()
RETURNING id
"""

BACKFILL_EMPTY_SOURCE_NAME_SQL = """
UPDATE decisions
SET source_name = %s,
    updated_at = NOW()
WHERE source_name = ''
  AND external_id = %s
  AND source_url = %s
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parsed karar JSON dosyalarini PostgreSQL decisions tablosuna aktarir.")
    parser.add_argument(
        "--source-name",
        action="append",
        default=[],
        help="Sadece belirli kaynagi aktar. Birden fazla kez verilebilir. Ornek: yargitay, uyap_emsal",
    )
    parser.add_argument("--limit", type=int, default=0, help="En fazla N dosya isle.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def normalized_date(value: str) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def normalized_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)


def iter_parsed_files(selected_sources: set[str]) -> list[Path]:
    files: list[Path] = []
    if not OUTPUT_ROOT.exists():
        return files

    for source_dir in sorted(path for path in OUTPUT_ROOT.iterdir() if path.is_dir()):
        if selected_sources and source_dir.name not in selected_sources:
            continue
        parsed_dir = source_dir / "parsed"
        if not parsed_dir.exists():
            continue
        files.extend(sorted(parsed_dir.glob("*.json")))
    return files


def load_record(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_source_name(record: dict[str, object]) -> str:
    explicit = str(record.get("source_name", "")).strip()
    if explicit:
        return explicit

    source_url = str(record.get("source_url", "")).strip().lower()
    source = str(record.get("source", "")).strip().lower()
    combined = " ".join(part for part in [source_url, source] if part)

    if "karararama.yargitay.gov.tr" in combined:
        return "yargitay"
    if "emsal.uyap.gov.tr" in combined:
        return "uyap_emsal"
    return ""


def build_params(record: dict[str, object]) -> tuple[object, ...]:
    source_name = infer_source_name(record)
    return (
        source_name,
        str(record.get("id", "")),
        str(record.get("daire", "")),
        str(record.get("esas_no", "")),
        str(record.get("karar_no", "")),
        normalized_date(str(record.get("karar_tarihi", ""))),
        str(record.get("aranan_kelime", "")),
        str(record.get("durum", "")),
        str(record.get("title", "")),
        str(record.get("mahkeme", "")),
        str(record.get("outcome", "")),
        str(record.get("source_url", "")),
        str(record.get("run_name", "")),
        json.dumps(record.get("sections", {}), ensure_ascii=False),
        str(record.get("full_text", "")),
        json.dumps(record.get("document_metadata", {}), ensure_ascii=False),
        str(record.get("raw_document_path", "")),
        normalized_timestamp(str(record.get("parsed_at", ""))),
    )


def import_records(args: argparse.Namespace) -> int:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg kurulu degil. `pip install -r ingestion/requirements.txt` calistirin."
        ) from exc

    selected_sources = {value.strip() for value in args.source_name if value.strip()}
    parsed_files = iter_parsed_files(selected_sources)
    if args.limit > 0:
        parsed_files = parsed_files[: args.limit]

    print(f"Bulunan parsed dosya sayisi: {len(parsed_files)}")
    if selected_sources:
        print(f"Kaynak filtresi: {', '.join(sorted(selected_sources))}")

    conninfo = build_postgres_conninfo()
    inserted = 0
    updated = 0
    failed = 0

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            for index, path in enumerate(parsed_files, start=1):
                record = load_record(path)
                source_name = infer_source_name(record)
                external_id = str(record.get("id", ""))

                try:
                    with conn.transaction():
                        if source_name:
                            cur.execute(
                                BACKFILL_EMPTY_SOURCE_NAME_SQL,
                                (source_name, external_id, str(record.get("source_url", ""))),
                            )
                        cur.execute(
                            "SELECT 1 FROM decisions WHERE source_name = %s AND external_id = %s",
                            (source_name, external_id),
                        )
                        exists = cur.fetchone() is not None
                        cur.execute(UPSERT_DECISION_SQL, build_params(record))
                except Exception as exc:
                    failed += 1
                    print(f"Hata: {path.name} -> {exc}")
                    continue

                if exists:
                    updated += 1
                else:
                    inserted += 1

                if args.verbose:
                    action = "updated" if exists else "inserted"
                    print(f"[{index}/{len(parsed_files)}] {path.name} -> {action}")

    print(
        json.dumps(
            {
                "files_seen": len(parsed_files),
                "inserted": inserted,
                "updated": updated,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(
        "IMPORT_SUMMARY::"
        + json.dumps(
            {
                "files_seen": len(parsed_files),
                "inserted": inserted,
                "updated": updated,
                "failed": failed,
                "selected_sources": sorted(selected_sources),
            },
            ensure_ascii=False,
        )
    )
    return 0 if failed == 0 else 1


def main() -> None:
    args = parse_args()
    raise SystemExit(import_records(args))


if __name__ == "__main__":
    main()
