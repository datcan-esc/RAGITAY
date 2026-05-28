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
from ragitay.paths import (
    document_output_path,
    locate_search_output,
    parsed_output_path,
    search_output_path,
)
from ragitay.yargitay_client import RateLimitError, SearchFilters, SourceConfig, YargitayClient


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
        "durum": hit.get("durum", ""),
        "index": hit.get("index"),
        "sira_no": hit.get("siraNo"),
        "source_page": page_number,
    }


def discover(
    filters: SearchFilters,
    *,
    source_config: SourceConfig | None = None,
    start_page: int = 1,
    max_pages: int = 1,
    timeout: float = 30.0,
    run_name: str | None = None,
) -> Path:
    if filters.page_size > 100:
        raise ValueError("pageSize için güvenli üst sınır 100 olarak belirlendi.")

    run_name = run_name or build_run_name(filters)
    source_config = source_config or SourceConfig()
    client = YargitayClient(source_config=source_config, timeout=timeout)
    merged_hits: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    records_total: int | None = None
    pages_saved = 0

    try:
        for page_number in range(start_page, max_pages + 1):
            payload = client.search(filters, page_number)
            pages_saved += 1

            page_hits = payload.get("data", {}).get("data", [])
            if records_total is None:
                records_total = payload.get("data", {}).get("recordsTotal", 0)

            if not page_hits:
                break

            for hit in page_hits:
                normalized = normalize_hit(hit, page_number)
                if normalized["id"] in seen_ids:
                    continue
                seen_ids.add(normalized["id"])
                merged_hits.append(normalized)

            if len(seen_ids) >= (records_total or 0):
                break
    finally:
        del client

    result = {
        "source_name": source_config.name,
        "base_url": source_config.base_url,
        "search_path": source_config.search_path,
        "document_path": source_config.document_path,
        "document_id_param": source_config.document_id_param,
        "run_name": run_name,
        "query": filters.query,
        "filters": filters.to_payload(start_page)["data"],
        "start_page": start_page,
        "max_pages": max_pages,
        "page_size": filters.page_size,
        "pages_checked": pages_saved,
        "records_total": records_total or 0,
        "document_count": len(merged_hits),
        "hits": merged_hits,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    output_path = search_output_path(source_config.name, run_name)
    write_json(output_path, result)
    return output_path


def fetch_documents(
    run_name: str,
    *,
    source_name: str = "",
    timeout: float = 30.0,
    sleep_seconds: float = 0.0,
    skip_existing: bool = False,
    max_documents: int | None = None,
) -> dict[str, Any]:
    search_data = read_json(locate_search_output(run_name, source_name))
    resolved_source_name = str(search_data.get("source_name", source_name or "yargitay"))
    source_config = SourceConfig(
        name=resolved_source_name,
        base_url=str(search_data.get("base_url", SourceConfig().base_url)),
        search_path=str(search_data.get("search_path", SourceConfig().search_path)),
        document_path=str(search_data.get("document_path", SourceConfig().document_path)),
        document_id_param=str(search_data.get("document_id_param", SourceConfig().document_id_param)),
    )
    client = YargitayClient(source_config=source_config, timeout=timeout)
    fetched = 0
    skipped = 0
    newly_processed = 0
    rate_limited = False
    stopped_document_id = ""
    retry_after_seconds: float | None = None
    pending_hits = search_data.get("hits", [])

    try:
        for hit in pending_hits:
            if max_documents is not None and newly_processed >= max_documents:
                break

            document_id = hit["id"]
            output_path = document_output_path(resolved_source_name, document_id)

            if skip_existing and output_path.exists():
                skipped += 1
                continue

            try:
                payload = client.get_document(document_id)
            except RateLimitError as exc:
                rate_limited = True
                stopped_document_id = document_id
                retry_after_seconds = exc.retry_after_seconds
                break

            write_json(output_path, payload)
            fetched += 1
            newly_processed += 1

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    finally:
        del client

    remaining = 0
    for hit in pending_hits:
        document_id = hit["id"]
        output_path = document_output_path(resolved_source_name, document_id)
        if not output_path.exists():
            remaining += 1

    return {
        "total_hits": len(pending_hits),
        "newly_fetched": fetched,
        "already_downloaded": skipped,
        "fetched_this_run": newly_processed,
        "still_missing": remaining,
        "rate_limited": rate_limited,
        "stopped_document_id": stopped_document_id,
        "retry_after_seconds": retry_after_seconds,
    }


def build_normalized_record(
    hit: dict[str, Any],
    document_payload: dict[str, Any],
    run_name: str,
    source_config: SourceConfig,
) -> dict[str, Any]:
    html = document_payload.get("data", "")
    full_text = html_to_text(html)
    sections = extract_sections(full_text)
    outcome_text = sections.get("sonuc", "") or sections.get("hukum", "") or sections.get("karar", "") or full_text

    return {
        "id": hit["id"],
        "source": source_config.base_url,
        "source_name": source_config.name,
        "source_url": source_config.build_document_url(hit["id"]),
        "run_name": run_name,
        "daire": hit.get("daire", ""),
        "esas_no": hit.get("esas_no", ""),
        "karar_no": hit.get("karar_no", ""),
        "karar_tarihi": hit.get("karar_tarihi", ""),
        "aranan_kelime": hit.get("aranan_kelime", ""),
        "durum": hit.get("durum", ""),
        "title": extract_title(full_text),
        "mahkeme": extract_trial_court(full_text),
        "outcome": extract_outcome(outcome_text),
        "sections": sections,
        "full_text": full_text,
        "document_metadata": document_payload.get("metadata", {}),
        "raw_document_path": str(document_output_path(source_config.name, hit["id"])),
        "parsed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def parse_documents(run_name: str, *, source_name: str = "", skip_existing: bool = False) -> dict[str, int]:
    search_data = read_json(locate_search_output(run_name, source_name))
    resolved_source_name = str(search_data.get("source_name", source_name or "yargitay"))
    source_config = SourceConfig(
        name=resolved_source_name,
        base_url=str(search_data.get("base_url", SourceConfig().base_url)),
        search_path=str(search_data.get("search_path", SourceConfig().search_path)),
        document_path=str(search_data.get("document_path", SourceConfig().document_path)),
        document_id_param=str(search_data.get("document_id_param", SourceConfig().document_id_param)),
    )
    parsed = 0
    skipped = 0
    missing = 0

    for hit in search_data.get("hits", []):
        document_id = hit["id"]
        raw_path = document_output_path(resolved_source_name, document_id)
        output_path = parsed_output_path(resolved_source_name, document_id)

        if skip_existing and output_path.exists():
            skipped += 1
            continue

        if not raw_path.exists():
            missing += 1
            continue

        payload = read_json(raw_path)
        normalized = build_normalized_record(hit, payload, run_name, source_config)
        write_json(output_path, normalized)
        parsed += 1

    return {
        "total_hits": len(search_data.get("hits", [])),
        "newly_parsed": parsed,
        "already_parsed": skipped,
        "missing_raw": missing,
    }


def collect(
    filters: SearchFilters,
    *,
    source_config: SourceConfig | None = None,
    start_page: int,
    max_pages: int,
    timeout: float,
    sleep_seconds: float,
    skip_existing: bool,
    max_documents: int | None = None,
    run_name: str | None = None,
) -> dict[str, Any]:
    search_path = discover(
        filters,
        source_config=source_config,
        start_page=start_page,
        max_pages=max_pages,
        timeout=timeout,
        run_name=run_name,
    )
    run_name = read_json(search_path)["run_name"]
    fetch_report = fetch_documents(
        run_name,
        source_name=str(read_json(search_path).get("source_name", "")),
        timeout=timeout,
        sleep_seconds=sleep_seconds,
        skip_existing=skip_existing,
        max_documents=max_documents,
    )
    parse_report = parse_documents(
        run_name,
        source_name=str(read_json(search_path).get("source_name", "")),
        skip_existing=skip_existing,
    )
    return {
        "run_name": run_name,
        "search_output": str(search_path),
        "fetch_report": fetch_report,
        "parse_report": parse_report,
    }
