from pathlib import Path


INGESTION_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = INGESTION_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
DISCOVERY_ROOT = RAW_ROOT / "discovery"
DOCUMENTS_ROOT = RAW_ROOT / "documents"
PROCESSED_ROOT = DATA_ROOT / "processed"
DECISIONS_ROOT = PROCESSED_ROOT / "decisions"
