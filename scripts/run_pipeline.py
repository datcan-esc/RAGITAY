from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
DEFAULT_PROFILES = ["yargitay", "uyap"]
RUN_WORDLIST_SUMMARY_PREFIX = "RUN_WORDLIST_SUMMARY::"
IMPORT_SUMMARY_PREFIX = "IMPORT_SUMMARY::"
CHUNK_SUMMARY_PREFIX = "CHUNK_SUMMARY::"
EMBED_SUMMARY_PREFIX = "EMBED_SUMMARY::"


def select_python_interpreter() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Veri cekme ve import islemlerini tek komutta sirasiyla calistirir."
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=DEFAULT_PROFILES,
        help="Calistirilacak veri kaynaklari. Varsayilan: yargitay uyap",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Import adimini calistirma.",
    )
    parser.add_argument(
        "--import-source-name",
        action="append",
        default=[],
        help="Import sirasinda sadece belirli kaynaklari iceri aktar.",
    )
    parser.add_argument(
        "--import-limit",
        type=int,
        default=0,
        help="Import adiminda en fazla N parsed dosya isle.",
    )
    parser.add_argument(
        "--import-verbose",
        action="store_true",
        help="Import adimini verbose calistir.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Bir adim hata verirse devam et.",
    )
    parser.add_argument(
        "--skip-chunks",
        action="store_true",
        help="Chunk olusturma adimini calistirma.",
    )
    parser.add_argument(
        "--chunk-source-name",
        action="append",
        default=[],
        help="Chunk adiminda sadece belirli kaynaklari isle.",
    )
    parser.add_argument(
        "--chunk-limit",
        type=int,
        default=0,
        help="Chunk adiminda en fazla N karar isle.",
    )
    parser.add_argument(
        "--chunk-verbose",
        action="store_true",
        help="Chunk adimini verbose calistir.",
    )
    parser.add_argument(
        "--rebuild-chunks",
        action="store_true",
        help="Mevcut chunklari silip yeniden uret.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calisacak komutlari goster, calistirma.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Embedding olusturma adimini calistirma.",
    )
    parser.add_argument(
        "--embedding-source-name",
        action="append",
        default=[],
        help="Embedding adiminda sadece belirli kaynaklari isle.",
    )
    parser.add_argument(
        "--embedding-limit",
        type=int,
        default=0,
        help="Embedding adiminda en fazla N chunk isle.",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=0,
        help="Embedding adimi encode batch boyutu.",
    )
    parser.add_argument(
        "--embedding-model-name",
        default="",
        help="Varsayilan disinda embedding modeli kullan.",
    )
    parser.add_argument(
        "--embedding-device",
        default="",
        help="Opsiyonel embedding device degeri.",
    )
    parser.add_argument(
        "--embedding-verbose",
        action="store_true",
        help="Embedding adimini verbose calistir.",
    )
    parser.add_argument(
        "--rebuild-embeddings",
        action="store_true",
        help="Mevcut embeddingleri yok sayip yeniden uret.",
    )
    return parser


def run_command(label: str, command: list[str], *, dry_run: bool) -> tuple[int, dict[str, object] | None]:
    rendered = " ".join(command)
    print(f"\n[{label}]")
    print(rendered)

    if dry_run:
        return 0, None

    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    captured_summary: dict[str, object] | None = None

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip("\n")
        print(line)
        if line.startswith(RUN_WORDLIST_SUMMARY_PREFIX):
            captured_summary = json.loads(line[len(RUN_WORDLIST_SUMMARY_PREFIX) :])
        elif line.startswith(IMPORT_SUMMARY_PREFIX):
            captured_summary = json.loads(line[len(IMPORT_SUMMARY_PREFIX) :])
        elif line.startswith(CHUNK_SUMMARY_PREFIX):
            captured_summary = json.loads(line[len(CHUNK_SUMMARY_PREFIX) :])
        elif line.startswith(EMBED_SUMMARY_PREFIX):
            captured_summary = json.loads(line[len(EMBED_SUMMARY_PREFIX) :])

    process.wait()
    return process.returncode, captured_summary


def build_steps(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    python_bin = select_python_interpreter()
    steps: list[tuple[str, list[str]]] = []

    for profile in args.profiles:
        steps.append(
            (
                f"collect:{profile}",
                [
                    python_bin,
                    "ingestion/scripts/yargitay_cli.py",
                    "--profile",
                    profile,
                ],
            )
        )

    if not args.skip_import:
        import_command = [python_bin, "ingestion/scripts/import_decisions.py"]
        for source_name in args.import_source_name:
            import_command.extend(["--source-name", source_name])
        if args.import_limit > 0:
            import_command.extend(["--limit", str(args.import_limit)])
        if args.import_verbose:
            import_command.append("--verbose")
        steps.append(("import", import_command))

    if not args.skip_chunks:
        chunk_command = [python_bin, "ingestion/scripts/build_chunks.py"]
        for source_name in args.chunk_source_name:
            chunk_command.extend(["--source-name", source_name])
        if args.chunk_limit > 0:
            chunk_command.extend(["--limit", str(args.chunk_limit)])
        if args.chunk_verbose:
            chunk_command.append("--verbose")
        if args.rebuild_chunks:
            chunk_command.append("--rebuild")
        steps.append(("chunks", chunk_command))

    if not args.skip_embeddings:
        embedding_command = [python_bin, "ingestion/scripts/build_embeddings.py"]
        for source_name in args.embedding_source_name:
            embedding_command.extend(["--source-name", source_name])
        if args.embedding_limit > 0:
            embedding_command.extend(["--limit", str(args.embedding_limit)])
        if args.embedding_batch_size > 0:
            embedding_command.extend(["--batch-size", str(args.embedding_batch_size)])
        if args.embedding_model_name.strip():
            embedding_command.extend(["--model-name", args.embedding_model_name.strip()])
        if args.embedding_device.strip():
            embedding_command.extend(["--device", args.embedding_device.strip()])
        if args.embedding_verbose:
            embedding_command.append("--verbose")
        if args.rebuild_embeddings:
            embedding_command.append("--rebuild")
        steps.append(("embeddings", embedding_command))

    return steps


def print_pipeline_summary(step_summaries: dict[str, dict[str, object]]) -> None:
    if not step_summaries:
        return

    print("\nGenel Ozet:")
    for label, summary in step_summaries.items():
        if label.startswith("collect:"):
            fetch = summary.get("fetch", {})
            parse = summary.get("parse", {})
            print(
                f"- {label}: tamam={summary.get('jobs_completed', 0)},"
                f" atlandi={summary.get('jobs_skipped_done', 0)},"
                f" kismi={summary.get('jobs_partial', 0)},"
                f" rate_limit={summary.get('jobs_rate_limited', 0)},"
                f" hata={summary.get('jobs_failed', 0)}"
            )
            print(
                f"  fetch yeni={fetch.get('newly_fetched', 0)},"
                f" zaten_var={fetch.get('already_downloaded', 0)},"
                f" eksik={fetch.get('still_missing', 0)}"
            )
            print(
                f"  parse yeni={parse.get('newly_parsed', 0)},"
                f" zaten_var={parse.get('already_parsed', 0)},"
                f" ham_eksik={parse.get('missing_raw', 0)}"
            )
        elif label == "import":
            print(
                f"- import: gorulen={summary.get('files_seen', 0)},"
                f" inserted={summary.get('inserted', 0)},"
                f" updated={summary.get('updated', 0)},"
                f" failed={summary.get('failed', 0)}"
            )
        elif label == "chunks":
            print(
                f"- chunks: gorulen={summary.get('decisions_seen', 0)},"
                f" chunklenen={summary.get('decisions_chunked', 0)},"
                f" atlanan={summary.get('decisions_skipped', 0)},"
                f" chunk_sayisi={summary.get('chunks_written', 0)},"
                f" failed={summary.get('failed', 0)}"
            )
        elif label == "embeddings":
            print(
                f"- embeddings: gorulen={summary.get('chunks_seen', 0)},"
                f" yeni={summary.get('newly_embedded', 0)},"
                f" zaten_var={summary.get('already_embedded', 0)},"
                f" failed={summary.get('failed', 0)}"
            )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    steps = build_steps(args)

    print(f"Python: {select_python_interpreter()}")
    print(f"Proje: {PROJECT_ROOT}")

    failed_labels: list[str] = []
    step_summaries: dict[str, dict[str, object]] = {}
    for label, command in steps:
        code, summary = run_command(label, command, dry_run=args.dry_run)
        if summary is not None:
            step_summaries[label] = summary
        if code != 0:
            failed_labels.append(label)
            print(f"Hata: {label} -> cikis kodu {code}")
            if not args.continue_on_error:
                print_pipeline_summary(step_summaries)
                raise SystemExit(code)

    print_pipeline_summary(step_summaries)
    if failed_labels:
        print("\nBasarisiz adimlar:")
        for label in failed_labels:
            print(f"- {label}")
        raise SystemExit(1)

    print("\nPipeline tamamlandi.")


if __name__ == "__main__":
    main()
