from pathlib import Path


INGESTION_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = INGESTION_ROOT / "output"
LEGACY_SEARCHES_ROOT = OUTPUT_ROOT / "searches"
LEGACY_DOCUMENTS_ROOT = OUTPUT_ROOT / "documents"
LEGACY_PARSED_ROOT = OUTPUT_ROOT / "parsed"


def source_output_root(source_name: str) -> Path:
    return OUTPUT_ROOT / source_name


def searches_root(source_name: str) -> Path:
    return source_output_root(source_name) / "searches"


def documents_root(source_name: str) -> Path:
    return source_output_root(source_name) / "documents"


def parsed_root(source_name: str) -> Path:
    return source_output_root(source_name) / "parsed"


def search_output_path(source_name: str, run_name: str) -> Path:
    return searches_root(source_name) / f"{run_name}.json"


def document_output_path(source_name: str, document_id: str) -> Path:
    return documents_root(source_name) / f"{document_id}.json"


def parsed_output_path(source_name: str, document_id: str) -> Path:
    return parsed_root(source_name) / f"{document_id}.json"


def locate_search_output(run_name: str, source_name: str = "") -> Path:
    candidates: list[Path] = []

    if source_name:
        candidates.append(search_output_path(source_name, run_name))
    else:
        candidates.extend(sorted(OUTPUT_ROOT.glob(f"*/searches/{run_name}.json")))
        candidates.append(LEGACY_SEARCHES_ROOT / f"{run_name}.json")

    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise FileNotFoundError(f"Arama cikti dosyasi bulunamadi: {run_name}")
    if len(existing) > 1:
        joined = ", ".join(str(path) for path in existing)
        raise RuntimeError(f"Birden fazla arama cikti dosyasi bulundu, --source-name verin: {joined}")
    return existing[0]
