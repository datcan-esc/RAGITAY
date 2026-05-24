from __future__ import annotations

import argparse
import json
import sys
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
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ragitay.parser import slugify
from ragitay.pipeline import collect, discover, fetch_documents, parse_documents
from ragitay.yargitay_client import SearchFilters


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


def add_common_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", required=True, help='Arama ifadesi. Örnek: \'"işe iade"\'')
    parser.add_argument("--page-size", type=int, default=100, help="1-100 arası pageSize değeri")
    parser.add_argument("--decision-year", default="", help="kararYil filtresi")
    parser.add_argument("--start-date", default="", help="baslangicTarihi filtresi (GG.AA.YYYY)")
    parser.add_argument("--end-date", default="", help="bitisTarihi filtresi (GG.AA.YYYY)")
    parser.add_argument("--esas-year", default="", help="esasYil filtresi")
    parser.add_argument("--esas-first-number", default="", help="esasIlkSiraNo filtresi")
    parser.add_argument("--esas-last-number", default="", help="esasSonSiraNo filtresi")
    parser.add_argument("--karar-first-number", default="", help="kararIlkSiraNo filtresi")
    parser.add_argument("--karar-last-number", default="", help="kararSonSiraNo filtresi")
    parser.add_argument("--ceza-chamber", default="", help="birimYrgCezaDaire filtresi")
    parser.add_argument("--hukuk-chamber", default="", help="birimYrgHukukDaire filtresi")
    parser.add_argument("--kurul-chamber", default="", help="birimYrgKurulDaire filtresi")
    parser.add_argument("--yargitay-mah", default="", help="yargitayMah filtresi")
    parser.add_argument("--sort-field", default="1", help="siralama alanı")
    parser.add_argument("--sort-direction", default="desc", choices=["asc", "desc"])
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--run-name", default="", help="İstersen manuel run adı ver")


def ensure_state_dir() -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)


def load_profile(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def filters_from_profile(profile: dict[str, str], query: str) -> SearchFilters:
    page_size = int(profile.get("page_size", 100))
    if page_size > 100:
        raise ValueError("pageSize için güvenli üst sınır 100 olarak belirlendi.")

    return SearchFilters(
        query=query,
        page_size=page_size,
        decision_year=str(profile.get("decision_year", "")),
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


def build_job_id(profile_name: str, query: str) -> str:
    return f"{profile_name}::{query}"


def build_batch_run_name(profile_name: str, query: str) -> str:
    return f"{profile_name}--{slugify(query)}"


def run_discover(args: argparse.Namespace) -> None:
    filters = filters_from_args(args)
    manifest_path = discover(
        filters,
        start_page=args.start_page,
        max_pages=args.max_pages,
        timeout=args.timeout,
        run_name=args.run_name or None,
    )
    print(f"Discovery tamamlandı: {manifest_path}")


def run_fetch(args: argparse.Namespace) -> None:
    report = fetch_documents(
        args.run_name,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
        skip_existing=args.skip_existing,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_parse(args: argparse.Namespace) -> None:
    report = parse_documents(args.run_name, skip_existing=args.skip_existing)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_collect(args: argparse.Namespace) -> None:
    filters = filters_from_args(args)
    result = collect(
        filters,
        start_page=args.start_page,
        max_pages=args.max_pages,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
        skip_existing=args.skip_existing,
        run_name=args.run_name or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_wordlist(args: argparse.Namespace) -> None:
    profile_path = Path(args.profile)
    wordlist_path = Path(args.wordlist)
    profile_name = args.profile_name or profile_path.stem
    profile = load_profile(profile_path)
    done_jobs = read_state_lines(DONE_JOBS_PATH)
    failed_jobs = read_state_lines(FAILED_JOBS_PATH)

    queries = list(iter_wordlist(wordlist_path))
    print(f"Profil: {profile_path}")
    print(f"Kelime listesi: {wordlist_path}")
    print(f"Toplam sorgu: {len(queries)}")

    for query in queries:
        job_id = build_job_id(profile_name, query)
        if job_id in done_jobs:
            print(f"Atlandı: {job_id}")
            continue

        filters = filters_from_profile(profile, query)
        run_name = build_batch_run_name(profile_name, query)
        print(f"Calisiyor: {job_id}")

        try:
            result = collect(
                filters,
                start_page=int(profile.get("start_page", args.start_page)),
                max_pages=int(profile.get("max_pages", args.max_pages)),
                timeout=float(profile.get("timeout", args.timeout)),
                sleep_seconds=float(profile.get("sleep_seconds", args.sleep_seconds)),
                skip_existing=parse_bool(profile.get("skip_existing"), args.skip_existing),
                run_name=run_name,
            )
            append_state_line(DONE_JOBS_PATH, job_id)
            done_jobs.add(job_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as exc:
            if job_id not in failed_jobs:
                append_state_line(FAILED_JOBS_PATH, job_id)
                failed_jobs.add(job_id)
            print(f"Hata: {job_id} -> {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yargıtay veri toplama CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Arama yap ve hit listesi üret")
    add_common_filters(discover_parser)
    discover_parser.add_argument("--start-page", type=int, default=1)
    discover_parser.add_argument("--max-pages", type=int, default=1)
    discover_parser.set_defaults(func=run_discover)

    fetch_parser = subparsers.add_parser("fetch", help="Discovery run içindeki dokümanları indir")
    fetch_parser.add_argument("--run-name", required=True)
    fetch_parser.add_argument("--timeout", type=float, default=30.0)
    fetch_parser.add_argument("--sleep-seconds", type=float, default=0.0)
    fetch_parser.add_argument("--skip-existing", action="store_true")
    fetch_parser.set_defaults(func=run_fetch)

    parse_parser = subparsers.add_parser("parse", help="İndirilen dokümanları normalize et")
    parse_parser.add_argument("--run-name", required=True)
    parse_parser.add_argument("--skip-existing", action="store_true")
    parse_parser.set_defaults(func=run_parse)

    collect_parser = subparsers.add_parser("collect", help="discover + fetch + parse")
    add_common_filters(collect_parser)
    collect_parser.add_argument("--start-page", type=int, default=1)
    collect_parser.add_argument("--max-pages", type=int, default=1)
    collect_parser.add_argument("--sleep-seconds", type=float, default=0.0)
    collect_parser.add_argument("--skip-existing", action="store_true")
    collect_parser.set_defaults(func=run_collect)

    wordlist_parser = subparsers.add_parser("run-wordlist", help="Varsayilan profil ve kelime listesi ile toplu calistir")
    wordlist_parser.add_argument("--profile", default=str(DEFAULT_PROFILE_PATH))
    wordlist_parser.add_argument("--profile-name", default="")
    wordlist_parser.add_argument("--wordlist", default=str(DEFAULT_WORDLIST_PATH))
    wordlist_parser.add_argument("--start-page", type=int, default=1)
    wordlist_parser.add_argument("--max-pages", type=int, default=5)
    wordlist_parser.add_argument("--timeout", type=float, default=30.0)
    wordlist_parser.add_argument("--sleep-seconds", type=float, default=0.2)
    wordlist_parser.add_argument("--skip-existing", action="store_true", default=True)
    wordlist_parser.set_defaults(func=run_wordlist)

    return parser


def main() -> None:
    parser = build_parser()
    argv = sys.argv[1:] if len(sys.argv) > 1 else ["run-wordlist"]
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
