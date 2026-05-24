from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ragitay.parser import (
    extract_outcome,
    extract_sections,
    extract_title,
    extract_trial_court,
    html_to_text,
    normalize_date,
    slugify,
)
from ragitay.paths import DECISIONS_ROOT, DISCOVERY_ROOT, DOCUMENTS_ROOT
from ragitay.yargitay_client import DOCUMENT_URL, SearchFilters, YargitayClient


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_run_name(filters: SearchFilters) -> str:
    parts = [
        slugify(filters.query),
        slugify(filters.decision_year) if filters.decision_year else "",
        slugify(filters.hukuk_chamber or filters.ceza_chamber or filters.kurul_chamber),
    ]
    return "-".join(part for part in parts if part) or "run"


def normalize_hit(hit: dict[str, Any], page_number: int) -> dict[str, Any]:
    return {
        "id": str(hit.get("id", "")),
        "daire": hit.get("daire", ""),
        "esas_no": hit.get("esasNo", ""),
        "karar_no": hit.get("kararNo", ""),
        "karar_tarihi": normalize_date(hit.get("kararTarihi", "")),
        "aranan_kelime": hit.get("arananKelime", ""),
        "index": hit.get("index"),
        "sira_no": hit.get("siraNo"),
        "source_page": page_number,
    }


def discovery_run_dir(run_name: str) -> Path:
    return DISCOVERY_ROOT / run_name


def discovery_manifest_path(run_name: str) -> Path:
    return discovery_run_dir(run_name) / "manifest.json"


def discovery_hits_path(run_name: str) -> Path:
    return discovery_run_dir(run_name) / "hits.jsonl"


def discover(
    filters: SearchFilters,
    *,
    start_page: int = 1,
    max_pages: int = 1,
    timeout: float = 30.0,
    run_name: str | None = None,
) -> Path:
    if filters.page_size > 100:
        raise ValueError("pageSize için güvenli üst sınır 100 olarak belirlendi.")

    run_name = run_name or build_run_name(filters)
    run_dir = discovery_run_dir(run_name)
    pages_dir = run_dir / "pages"
    hits_path = discovery_hits_path(run_name)

    ensure_dir(pages_dir)
    ensure_dir(hits_path.parent)
    if hits_path.exists():
        hits_path.unlink()
    hits_path.touch()

    client = YargitayClient(timeout=timeout)
    unique_ids: list[str] = []
    seen_ids: set[str] = set()
    records_total: int | None = None
    pages_saved = 0

    try:
        for page_number in range(start_page, max_pages + 1):
            payload = client.search(filters, page_number)
            write_json(pages_dir / f"page-{page_number:04d}.json", payload)
            pages_saved += 1

            page_hits = payload.get("data", {}).get("data", [])
            if records_total is None:
                records_total = payload.get("data", {}).get("recordsTotal", 0)

            if not page_hits:
                break

            for hit in page_hits:
                normalized = normalize_hit(hit, page_number)
                append_jsonl(hits_path, normalized)
                if normalized["id"] not in seen_ids:
                    seen_ids.add(normalized["id"])
                    unique_ids.append(normalized["id"])

            if len(seen_ids) >= (records_total or 0):
                break
    finally:
        del client

    manifest = {
        "run_name": run_name,
        "query": filters.query,
        "filters": filters.to_payload(start_page)["data"],
        "start_page": start_page,
        "max_pages": max_pages,
        "page_size": filters.page_size,
        "pages_saved": pages_saved,
        "records_total": records_total,
        "unique_document_count": len(unique_ids),
        "document_ids": unique_ids,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    manifest_path = discovery_manifest_path(run_name)
    write_json(manifest_path, manifest)
    return manifest_path


def fetch_documents(
    run_name: str,
    *,
    timeout: float = 30.0,
    sleep_seconds: float = 0.0,
    skip_existing: bool = False,
) -> dict[str, int]:
    manifest = read_json(discovery_manifest_path(run_name))
    client = YargitayClient(timeout=timeout)
    fetched = 0
    skipped = 0

    try:
        for document_id in manifest.get("document_ids", []):
            output_path = DOCUMENTS_ROOT / f"{document_id}.json"
            if skip_existing and output_path.exists():
                skipped += 1
                continue

            payload = client.get_document(document_id)
            write_json(output_path, payload)
            fetched += 1

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    finally:
        del client

    result = {
        "documents_requested": len(manifest.get("document_ids", [])),
        "documents_fetched": fetched,
        "documents_skipped": skipped,
    }
    write_json(discovery_run_dir(run_name) / "fetch-report.json", result)
    return result


def build_normalized_record(
    hit: dict[str, Any],
    document_payload: dict[str, Any],
    run_name: str,
) -> dict[str, Any]:
    html = document_payload.get("data", "")
    full_text = html_to_text(html)
    sections = extract_sections(full_text)

    return {
        "id": hit["id"],
        "source": "karararama.yargitay.gov.tr",
        "source_url": f"{DOCUMENT_URL}?id={hit['id']}",
        "run_name": run_name,
        "daire": hit.get("daire", ""),
        "esas_no": hit.get("esas_no", ""),
        "karar_no": hit.get("karar_no", ""),
        "karar_tarihi": hit.get("karar_tarihi", ""),
        "aranan_kelime": hit.get("aranan_kelime", ""),
        "title": extract_title(full_text),
        "mahkeme": extract_trial_court(full_text),
        "outcome": extract_outcome(sections.get("sonuc", "")),
        "sections": sections,
        "full_text": full_text,
        "document_metadata": document_payload.get("metadata", {}),
        "raw_document_path": str(DOCUMENTS_ROOT / f"{hit['id']}.json"),
        "parsed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def parse_documents(run_name: str, *, skip_existing: bool = False) -> dict[str, int]:
    hits = read_jsonl(discovery_hits_path(run_name))
    by_id = {hit["id"]: hit for hit in hits}
    parsed = 0
    skipped = 0
    missing = 0

    for document_id, hit in by_id.items():
        raw_path = DOCUMENTS_ROOT / f"{document_id}.json"
        output_path = DECISIONS_ROOT / f"{document_id}.json"

        if skip_existing and output_path.exists():
            skipped += 1
            continue

        if not raw_path.exists():
            missing += 1
            continue

        payload = read_json(raw_path)
        normalized = build_normalized_record(hit, payload, run_name)
        write_json(output_path, normalized)
        parsed += 1

    result = {
        "documents_seen": len(by_id),
        "documents_parsed": parsed,
        "documents_skipped": skipped,
        "documents_missing_raw": missing,
    }
    write_json(discovery_run_dir(run_name) / "parse-report.json", result)
    return result


def collect(
    filters: SearchFilters,
    *,
    start_page: int,
    max_pages: int,
    timeout: float,
    sleep_seconds: float,
    skip_existing: bool,
    run_name: str | None = None,
) -> dict[str, Any]:
    manifest_path = discover(
        filters,
        start_page=start_page,
        max_pages=max_pages,
        timeout=timeout,
        run_name=run_name,
    )
    run_name = read_json(manifest_path)["run_name"]
    fetch_report = fetch_documents(
        run_name,
        timeout=timeout,
        sleep_seconds=sleep_seconds,
        skip_existing=skip_existing,
    )
    parse_report = parse_documents(run_name, skip_existing=skip_existing)
    return {
        "run_name": run_name,
        "manifest_path": str(manifest_path),
        "fetch_report": fetch_report,
        "parse_report": parse_report,
    }
