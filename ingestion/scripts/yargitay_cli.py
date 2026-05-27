from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable


CURRENT_FILE = Path(__file__).resolve()
INGESTION_ROOT = CURRENT_FILE.parents[1]
SRC_ROOT = INGESTION_ROOT / "src"
CONFIG_ROOT = INGESTION_ROOT / "config"
PROFILES_ROOT = CONFIG_ROOT / "profiles"
WORDLISTS_ROOT = CONFIG_ROOT / "wordlists"
STATE_ROOT = INGESTION_ROOT / "state"
DEFAULT_PROFILE_PATH = PROFILES_ROOT / "default.json"
DEFAULT_WORDLIST_PATH = WORDLISTS_ROOT / "example_queries.txt"
DONE_JOBS_PATH = STATE_ROOT / "done_jobs.txt"
FAILED_JOBS_PATH = STATE_ROOT / "failed_jobs.txt"
PROFILE_ALIASES = {
    "default": "default.json",
    "yargitay": "default.json",
    "uyap": "uyap_emsal.json",
    "uyap_emsal": "uyap_emsal.json",
}
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ragitay.parser import slugify
from ragitay.pipeline import collect, discover, fetch_documents, parse_documents
from ragitay.yargitay_client import SearchFilters, SourceConfig


def ensure_state_dir() -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)


def load_profile(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_profile_path(profile_value: str) -> Path:
    candidate = Path(profile_value)
    if candidate.exists():
        return candidate

    normalized = PROFILE_ALIASES.get(profile_value, profile_value)
    profile_path = PROFILES_ROOT / normalized
    if profile_path.suffix != ".json":
        profile_path = profile_path.with_suffix(".json")
    if profile_path.exists():
        return profile_path

    raise FileNotFoundError(f"Profil bulunamadi: {profile_value}")


def resolve_wordlist_path(wordlist_value: str, profile: dict[str, object]) -> Path:
    if wordlist_value:
        candidate = Path(wordlist_value)
        if candidate.exists():
            return candidate
        profile_relative = CONFIG_ROOT / wordlist_value
        if profile_relative.exists():
            return profile_relative
        raise FileNotFoundError(f"Kelime listesi bulunamadi: {wordlist_value}")

    configured = str(profile.get("wordlist", "")).strip()
    if configured:
        candidate = Path(configured)
        if candidate.exists():
            return candidate
        profile_relative = CONFIG_ROOT / configured
        if profile_relative.exists():
            return profile_relative
        raise FileNotFoundError(f"Profil icindeki kelime listesi bulunamadi: {configured}")

    return DEFAULT_WORDLIST_PATH


def iter_wordlist(path: Path) -> Iterable[str]:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        yield line


def read_state_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def append_state_line(path: Path, value: str) -> None:
    ensure_state_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(value + "\n")


def write_state_lines(path: Path, values: set[str]) -> None:
    ensure_state_dir()
    ordered = sorted(value for value in values if value)
    path.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")


def parse_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def filters_from_args(args: argparse.Namespace) -> SearchFilters:
    if args.page_size > 100:
        raise ValueError("pageSize için güvenli üst sınır 100 olarak belirlendi.")

    yargitay_mah = args.yargitay_mah or args.kurul_chamber
    return SearchFilters(
        query=args.query,
        page_size=args.page_size,
        decision_year=args.decision_year,
        start_date=args.start_date,
        end_date=args.end_date,
        esas_year=args.esas_year,
        esas_first_number=args.esas_first_number,
        esas_last_number=args.esas_last_number,
        karar_first_number=args.karar_first_number,
        karar_last_number=args.karar_last_number,
        ceza_chamber=args.ceza_chamber,
        hukuk_chamber=args.hukuk_chamber,
        kurul_chamber=args.kurul_chamber,
        yargitay_mah=yargitay_mah,
        sort_field=args.sort_field,
        sort_direction=args.sort_direction,
    )


def source_config_from_args(args: argparse.Namespace) -> SourceConfig:
    return SourceConfig(
        name=args.source_name,
        base_url=args.base_url,
        search_path=args.search_path,
        document_path=args.document_path,
        document_id_param=args.document_id_param,
    )


def filters_from_profile(profile: dict[str, object], query: str, decision_year: str) -> SearchFilters:
    page_size = int(profile.get("page_size", 100))
    if page_size > 100:
        raise ValueError("pageSize için güvenli üst sınır 100 olarak belirlendi.")

    return SearchFilters(
        query=query,
        page_size=page_size,
        decision_year=decision_year,
        start_date=str(profile.get("start_date", "")),
        end_date=str(profile.get("end_date", "")),
        esas_year=str(profile.get("esas_year", "")),
        esas_first_number=str(profile.get("esas_first_number", "")),
        esas_last_number=str(profile.get("esas_last_number", "")),
        karar_first_number=str(profile.get("karar_first_number", "")),
        karar_last_number=str(profile.get("karar_last_number", "")),
        ceza_chamber=str(profile.get("ceza_chamber", "")),
        hukuk_chamber=str(profile.get("hukuk_chamber", "")),
        kurul_chamber=str(profile.get("kurul_chamber", "")),
        yargitay_mah=str(profile.get("yargitay_mah", profile.get("kurul_chamber", ""))),
        sort_field=str(profile.get("sort_field", "3")),
        sort_direction=str(profile.get("sort_direction", "desc")),
    )


def source_config_from_profile(profile: dict[str, object]) -> SourceConfig:
    return SourceConfig(
        name=str(profile.get("source_name", "yargitay")),
        base_url=str(profile.get("base_url", "https://karararama.yargitay.gov.tr")),
        search_path=str(profile.get("search_path", "/aramadetaylist")),
        document_path=str(profile.get("document_path", "/getDokuman")),
        document_id_param=str(profile.get("document_id_param", "id")),
    )


def build_job_id(profile_name: str, year: str, query: str) -> str:
    return f"{profile_name}::{year}::{query}"


def build_run_name(profile_name: str, year: str, query: str) -> str:
    return f"{profile_name}--{year}--{slugify(query)}"


def iter_years(profile: dict[str, object]) -> list[str]:
    current_year = datetime.utcnow().year
    years = profile.get("decision_years")
    if isinstance(years, list) and years:
        return [str(year) for year in years]

    years_from = int(profile.get("years_from", current_year))
    return [str(year) for year in range(current_year, years_from - 1, -1)]


def add_common_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-name", default="yargitay")
    parser.add_argument("--base-url", default="https://karararama.yargitay.gov.tr")
    parser.add_argument("--search-path", default="/aramadetaylist")
    parser.add_argument("--document-path", default="/getDokuman")
    parser.add_argument("--document-id-param", default="id")
    parser.add_argument("--query", required=True)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--decision-year", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--esas-year", default="")
    parser.add_argument("--esas-first-number", default="")
    parser.add_argument("--esas-last-number", default="")
    parser.add_argument("--karar-first-number", default="")
    parser.add_argument("--karar-last-number", default="")
    parser.add_argument("--ceza-chamber", default="")
    parser.add_argument("--hukuk-chamber", default="")
    parser.add_argument("--kurul-chamber", default="")
    parser.add_argument("--yargitay-mah", default="")
    parser.add_argument("--sort-field", default="1")
    parser.add_argument("--sort-direction", default="desc", choices=["asc", "desc"])
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--run-name", default="")


def run_discover(args: argparse.Namespace) -> None:
    filters = filters_from_args(args)
    source_config = source_config_from_args(args)
    output_path = discover(
        filters,
        source_config=source_config,
        start_page=args.start_page,
        max_pages=args.max_pages,
        timeout=args.timeout,
        run_name=args.run_name or None,
    )
    print(f"Arama kaydedildi: {output_path}")


def run_fetch(args: argparse.Namespace) -> None:
    report = fetch_documents(
        args.run_name,
        source_name=args.source_name,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
        skip_existing=args.skip_existing,
        max_documents=args.max_documents,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_parse(args: argparse.Namespace) -> None:
    report = parse_documents(args.run_name, source_name=args.source_name, skip_existing=args.skip_existing)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_collect(args: argparse.Namespace) -> None:
    filters = filters_from_args(args)
    source_config = source_config_from_args(args)
    result = collect(
        filters,
        source_config=source_config,
        start_page=args.start_page,
        max_pages=args.max_pages,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
        skip_existing=args.skip_existing,
        max_documents=args.max_documents,
        run_name=args.run_name or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_wordlist(args: argparse.Namespace) -> None:
    profile_path = resolve_profile_path(args.profile)
    profile = load_profile(profile_path)
    wordlist_path = resolve_wordlist_path(args.wordlist, profile)
    profile_name = args.profile_name or str(profile.get("profile_name", profile_path.stem))
    source_config = source_config_from_profile(profile)
    done_jobs = read_state_lines(DONE_JOBS_PATH)
    failed_jobs = read_state_lines(FAILED_JOBS_PATH)
    years = iter_years(profile)
    queries = list(iter_wordlist(wordlist_path))

    print(f"Profil: {profile_path}")
    print(f"Kelime listesi: {wordlist_path}")
    print(f"Kaynak: {source_config.name} ({source_config.base_url})")
    print(f"Yillar: {', '.join(years)}")
    print(f"Toplam sorgu: {len(queries)}")

    for year in years:
        for query in queries:
            job_id = build_job_id(profile_name, year, query)
            if job_id in done_jobs:
                print(f"Atlandı: {job_id}")
                continue

            filters = filters_from_profile(profile, query, year)
            run_name = build_run_name(profile_name, year, query)
            print(f"Calisiyor: {job_id}")

            try:
                result = collect(
                    filters,
                    source_config=source_config,
                    start_page=int(profile.get("start_page", args.start_page)),
                    max_pages=int(profile.get("max_pages", args.max_pages)),
                    timeout=float(profile.get("timeout", args.timeout)),
                    sleep_seconds=float(profile.get("sleep_seconds", args.sleep_seconds)),
                    skip_existing=parse_bool(profile.get("skip_existing"), args.skip_existing),
                    max_documents=int(profile.get("max_documents_per_run", args.max_documents)),
                    run_name=run_name,
                )

                fetch_report = result["fetch_report"]
                requested = fetch_report["documents_requested"]
                remaining = fetch_report["documents_remaining"]

                if requested == 0:
                    print(f"Sonuc yok: {job_id}")
                    continue

                if fetch_report["rate_limited"]:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    print("Rate limit nedeniyle batch durduruldu. Bir süre sonra aynı komutu tekrar çalıştır.")
                    return

                if remaining > 0:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    print("Bu job kısmi işlendi. Kaldığı yerden devam etmek için aynı komutu tekrar çalıştır.")
                    return

                append_state_line(DONE_JOBS_PATH, job_id)
                done_jobs.add(job_id)
                if job_id in failed_jobs:
                    failed_jobs.remove(job_id)
                    write_state_lines(FAILED_JOBS_PATH, failed_jobs)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except Exception as exc:
                if job_id not in failed_jobs:
                    append_state_line(FAILED_JOBS_PATH, job_id)
                    failed_jobs.add(job_id)
                print(f"Hata: {job_id} -> {exc}")

            job_sleep_seconds = float(profile.get("job_sleep_seconds", 1.5))
            if job_sleep_seconds > 0:
                time.sleep(job_sleep_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yargıtay veri toplama CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    add_common_filters(discover_parser)
    discover_parser.add_argument("--start-page", type=int, default=1)
    discover_parser.add_argument("--max-pages", type=int, default=1)
    discover_parser.set_defaults(func=run_discover)

    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--run-name", required=True)
    fetch_parser.add_argument("--source-name", default="")
    fetch_parser.add_argument("--timeout", type=float, default=30.0)
    fetch_parser.add_argument("--sleep-seconds", type=float, default=0.0)
    fetch_parser.add_argument("--skip-existing", action="store_true")
    fetch_parser.add_argument("--max-documents", type=int, default=None)
    fetch_parser.set_defaults(func=run_fetch)

    parse_parser = subparsers.add_parser("parse")
    parse_parser.add_argument("--run-name", required=True)
    parse_parser.add_argument("--source-name", default="")
    parse_parser.add_argument("--skip-existing", action="store_true")
    parse_parser.set_defaults(func=run_parse)

    collect_parser = subparsers.add_parser("collect")
    add_common_filters(collect_parser)
    collect_parser.add_argument("--start-page", type=int, default=1)
    collect_parser.add_argument("--max-pages", type=int, default=1)
    collect_parser.add_argument("--sleep-seconds", type=float, default=0.0)
    collect_parser.add_argument("--skip-existing", action="store_true")
    collect_parser.add_argument("--max-documents", type=int, default=None)
    collect_parser.set_defaults(func=run_collect)

    wordlist_parser = subparsers.add_parser("run-wordlist")
    wordlist_parser.add_argument("--profile", default="default")
    wordlist_parser.add_argument("--profile-name", default="")
    wordlist_parser.add_argument("--wordlist", default="")
    wordlist_parser.add_argument("--start-page", type=int, default=1)
    wordlist_parser.add_argument("--max-pages", type=int, default=5)
    wordlist_parser.add_argument("--timeout", type=float, default=30.0)
    wordlist_parser.add_argument("--sleep-seconds", type=float, default=0.2)
    wordlist_parser.add_argument("--skip-existing", action="store_true", default=True)
    wordlist_parser.add_argument("--max-documents", type=int, default=50)
    wordlist_parser.set_defaults(func=run_wordlist)

    return parser


def main() -> None:
    parser = build_parser()
    argv = sys.argv[1:]
    known_commands = {"discover", "fetch", "parse", "collect", "run-wordlist"}
    if not argv:
        argv = ["run-wordlist"]
    elif argv[0].startswith("-"):
        argv = ["run-wordlist", *argv]
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
