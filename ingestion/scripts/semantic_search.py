from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
INGESTION_ROOT = CURRENT_FILE.parents[1]
SRC_ROOT = INGESTION_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ragitay.database import build_postgres_conninfo
from ragitay.embeddings import DEFAULT_EMBEDDING_MODEL_NAME, prepare_query_text


SECTION_WEIGHTS = {
    "gerekce": 0.10,
    "degerlendirme_ve_gerekce": 0.10,
    "deliller_ve_gerekce": 0.10,
    "delillerin_degerlendirilmesi_ve_gerekce": 0.10,
    "ilk_derece_mahkemesi_karari": 0.09,
    "mahkeme_karari": 0.09,
    "bozma_ve_bozmadan_sonraki_yargilama_sureci": 0.08,
    "karar": 0.03,
    "hukum": 0.04,
    "sonuc": 0.03,
    "istinaf": 0.04,
    "temyiz": 0.04,
    "dava": 0.05,
    "talep": 0.04,
    "cevap": 0.01,
    "full_text": -0.03,
}

SECTION_DISPLAY_NAMES = {
    "gerekce": "Gerekçe",
    "degerlendirme_ve_gerekce": "Gerekçe",
    "deliller_ve_gerekce": "Gerekçe",
    "delillerin_degerlendirilmesi_ve_gerekce": "Gerekçe",
    "karar": "Karar",
    "hukum": "Hüküm",
    "sonuc": "Sonuç",
    "istinaf": "İstinaf",
    "temyiz": "Temyiz",
    "dava": "Dava",
    "talep": "Talep",
    "cevap": "Cevap",
    "full_text": "Metin",
    "ilk_derece_mahkemesi_karari": "İlk Derece Mahkemesi Kararı",
    "mahkeme_karari": "Mahkeme Kararı",
    "bozma_ve_bozmadan_sonraki_yargilama_sureci": "Bozma Süreci",
}

LOW_VALUE_PHRASES = (
    "içtihat metni",
    "uyuşmazlığın giderilmesi istemine dair",
    "uyusmazligin giderilmesi istemine dair",
)
LOW_INFORMATION_PHRASES = (
    "istinaf başvurusunun esastan reddi",
    "istinaf basvurusunun esastan reddi",
    "ilk derece mahkemesi",
    "bölge adliye mahkemesi",
    "bolge adliye mahkemesi",
    "davanın reddini talep etmiştir",
    "davanin reddini talep etmistir",
)
PREFERRED_SUMMARY_SECTIONS = {
    "gerekce",
    "degerlendirme_ve_gerekce",
    "deliller_ve_gerekce",
    "delillerin_degerlendirilmesi_ve_gerekce",
    "dava",
    "talep",
    "hukum",
    "sonuc",
}

TOKEN_RE = re.compile(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{3,}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

SEARCH_SQL = """
WITH semantic_candidates AS (
  SELECT
    dc.id AS chunk_id,
    dc.decision_id,
    1 - (dc.embedding <=> %s) AS semantic_score
  FROM decision_chunks dc
  JOIN decisions d ON d.id = dc.decision_id
  WHERE dc.embedding IS NOT NULL
    AND dc.chunk_text <> ''
    {filters}
  ORDER BY dc.embedding <=> %s ASC, d.karar_tarihi DESC NULLS LAST
  LIMIT %s
),
lexical_candidates AS (
  SELECT
    dc.id AS chunk_id,
    dc.decision_id,
    GREATEST(
      similarity(lower(dc.chunk_text), lower(%s)),
      similarity(lower(d.title), lower(%s)),
      CASE WHEN lower(dc.chunk_text) LIKE %s THEN 1.0 ELSE 0.0 END,
      CASE WHEN lower(d.title) LIKE %s THEN 1.0 ELSE 0.0 END
    ) AS lexical_score
  FROM decision_chunks dc
  JOIN decisions d ON d.id = dc.decision_id
  WHERE dc.chunk_text <> ''
    {filters}
  ORDER BY lexical_score DESC, d.karar_tarihi DESC NULLS LAST
  LIMIT %s
),
candidate_ids AS (
  SELECT chunk_id FROM semantic_candidates
  UNION
  SELECT chunk_id FROM lexical_candidates
)
SELECT
  dc.id AS chunk_id,
  dc.decision_id,
  dc.chunk_index,
  dc.section_name,
  dc.chunk_text,
  d.source_name,
  d.external_id,
  d.title,
  d.daire,
  d.esas_no,
  d.karar_no,
  d.karar_tarihi,
  d.mahkeme,
  d.outcome,
  d.source_url,
  COALESCE(sc.semantic_score, 0.0) AS semantic_score,
  COALESCE(lc.lexical_score, 0.0) AS lexical_score
FROM candidate_ids c
JOIN decision_chunks dc ON dc.id = c.chunk_id
JOIN decisions d ON d.id = dc.decision_id
LEFT JOIN semantic_candidates sc ON sc.chunk_id = dc.id
LEFT JOIN lexical_candidates lc ON lc.chunk_id = dc.id
ORDER BY COALESCE(sc.semantic_score, 0.0) DESC, COALESCE(lc.lexical_score, 0.0) DESC, d.karar_tarihi DESC NULLS LAST
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Semantic ve lexical sinyalleri birlestirerek hybrid search calistirir."
    )
    parser.add_argument("query", help="Dogal dilde arama sorgusu.")
    parser.add_argument("--source-name", action="append", default=[], help="Kaynak filtresi.")
    parser.add_argument("--daire", default="", help="Daire filtresi. Tam eslesme kullanir.")
    parser.add_argument("--year-from", type=int, default=0, help="Baslangic karar yili.")
    parser.add_argument("--year-to", type=int, default=0, help="Bitis karar yili.")
    parser.add_argument("--top-k-chunks", type=int, default=40, help="Semantic aday sayisi.")
    parser.add_argument("--top-k-lexical", type=int, default=40, help="Lexical aday sayisi.")
    parser.add_argument("--top-decisions", type=int, default=5, help="Donulecek karar sayisi.")
    parser.add_argument(
        "--max-passages-per-decision",
        type=int,
        default=2,
        help="Her karar icin en fazla kac ilgili pasaj gosterilsin.",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_EMBEDDING_MODEL_NAME,
        help=f"Sorgu embedding modeli. Varsayilan: {DEFAULT_EMBEDDING_MODEL_NAME}",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Modeli sadece yerel Hugging Face cache'inden yukle.",
    )
    parser.add_argument("--device", default="", help="Opsiyonel device degeri.")
    parser.add_argument("--json", action="store_true", help="Yalniz JSON sonuc bas.")
    return parser.parse_args()


def load_model(model_name: str, device: str, local_files_only: bool):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers kurulu degil. `pip install -r ingestion/requirements.txt` calistirin."
        ) from exc

    kwargs: dict[str, object] = {}
    if device.strip():
        kwargs["device"] = device.strip()
    if local_files_only:
        kwargs["local_files_only"] = True
    return SentenceTransformer(model_name, **kwargs)


def tokenize_query(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def is_low_value_chunk_text(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    alpha_count = sum(1 for char in normalized if char.isalpha())
    if alpha_count < 60:
        return True
    if len(normalized) < 300 and any(phrase in normalized for phrase in LOW_VALUE_PHRASES):
        return True
    return False


def is_low_information_result_chunk(section_name: str, text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if section_name in {"karar", "hukum", "sonuc"}:
        if len(normalized) < 220:
            return True
        if any(phrase in normalized for phrase in LOW_INFORMATION_PHRASES):
            return True
        if normalized.startswith("açıklanan sebeplerle") or normalized.startswith("aciklanan sebeplerle"):
            return True
    if section_name == "cevap":
        if len(normalized) < 420:
            return True
        if any(phrase in normalized for phrase in LOW_INFORMATION_PHRASES):
            return True
    return False


def lexical_overlap_score(query_tokens: list[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for token in query_tokens if token in lowered)
    return hits / len(query_tokens)


def adjusted_similarity(row: dict[str, object], query_tokens: list[str]) -> float:
    semantic_score = float(row["semantic_score"])
    lexical_score = float(row["lexical_score"])
    section_name = str(row.get("section_name") or "")
    section_bonus = SECTION_WEIGHTS.get(section_name, 0.0)
    overlap_value = lexical_overlap_score(query_tokens, str(row.get("chunk_text") or ""))
    overlap_bonus = overlap_value * 0.18
    lexical_penalty = -0.07 if lexical_score <= 0.001 else 0.0
    generic_penalty = -0.08 if section_name == "cevap" and overlap_value <= 0.01 else 0.0
    return (semantic_score * 0.72) + (lexical_score * 0.22) + section_bonus + overlap_bonus + lexical_penalty + generic_penalty


def build_filter_sql(args: argparse.Namespace) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    selected_sources = [value.strip() for value in args.source_name if value.strip()]
    if selected_sources:
        clauses.append("d.source_name = ANY(%s)")
        params.append(selected_sources)

    if args.daire.strip():
        clauses.append("d.daire = %s")
        params.append(args.daire.strip())

    if args.year_from > 0:
        clauses.append("d.karar_tarihi >= make_date(%s, 1, 1)")
        params.append(args.year_from)

    if args.year_to > 0:
        clauses.append("d.karar_tarihi < make_date(%s, 1, 1)")
        params.append(args.year_to + 1)

    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params


def build_search_sql(args: argparse.Namespace) -> tuple[str, list[object]]:
    filter_sql, filter_params = build_filter_sql(args)
    sql = SEARCH_SQL.format(filters=filter_sql)
    like_pattern = f"%{args.query.lower()}%"

    params: list[object] = []
    params.append(None)  # semantic vector placeholder 1
    params.extend(filter_params)
    params.append(None)  # semantic vector placeholder 2
    params.append(args.top_k_chunks)
    params.append(args.query)
    params.append(args.query)
    params.append(like_pattern)
    params.append(like_pattern)
    params.extend(filter_params)
    params.append(args.top_k_lexical)
    return sql, params


def clean_summary_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    cleaned = cleaned.replace("I. DAVA", "").replace("II. CEVAP", "").replace("III. İLK DERECE MAHKEMESİ KARARI", "")
    cleaned = cleaned.replace("IV. İSTİNAF", "").replace("V. TEMYİZ", "").replace("VI. KARAR", "")
    return cleaned.strip(" -:\n")


def group_results(
    rows: list[dict[str, object]],
    query_tokens: list[str],
    max_passages_per_decision: int,
    top_decisions: int,
) -> list[dict[str, object]]:
    decisions: OrderedDict[int, dict[str, object]] = OrderedDict()

    for row in rows:
        chunk_text = str(row["chunk_text"])
        if is_low_value_chunk_text(chunk_text):
            continue
        section_name = str(row.get("section_name") or "")
        if is_low_information_result_chunk(section_name, chunk_text):
            continue

        decision_id = int(row["decision_id"])
        score = adjusted_similarity(row, query_tokens)
        if decision_id not in decisions:
            decisions[decision_id] = {
                "decision_id": decision_id,
                "source_name": row["source_name"],
                "external_id": row["external_id"],
                "title": row["title"],
                "daire": row["daire"],
                "esas_no": row["esas_no"],
                "karar_no": row["karar_no"],
                "karar_tarihi": row["karar_tarihi"].isoformat() if row["karar_tarihi"] else "",
                "mahkeme": row["mahkeme"],
                "outcome": row["outcome"],
                "source_url": row["source_url"],
                "score": score,
                "passages": [],
            }

        decision = decisions[decision_id]
        decision["score"] = max(float(decision["score"]), score)
        passages = decision["passages"]
        passages.append(
            {
                "chunk_id": int(row["chunk_id"]),
                "chunk_index": int(row["chunk_index"]),
                "section_name": section_name,
                "semantic_score": float(row["semantic_score"]),
                "lexical_score": float(row["lexical_score"]),
                "adjusted_score": score,
                "chunk_text": chunk_text,
            }
        )
        passages.sort(
            key=lambda item: (
                item["section_name"] in PREFERRED_SUMMARY_SECTIONS,
                item["lexical_score"],
                item["adjusted_score"],
            ),
            reverse=True,
        )
        del passages[max_passages_per_decision:]

    ranked = sorted(decisions.values(), key=lambda item: item["score"], reverse=True)
    return ranked[:top_decisions]


def summarize_results(query: str, results: list[dict[str, object]]) -> list[dict[str, str]]:
    bullets: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    query_tokens = tokenize_query(query)

    for decision in results:
        best_passages = sorted(
            decision["passages"],
            key=lambda item: (
                item["section_name"] in PREFERRED_SUMMARY_SECTIONS,
                item["lexical_score"],
                item["adjusted_score"],
            ),
            reverse=True,
        )
        for passage in best_passages:
            text = " ".join(str(passage["chunk_text"]).split())
            sentences = [clean_summary_sentence(part) for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
            if not sentences:
                continue

            best_sentence = sentences[0]
            best_score = -1.0
            for sentence in sentences:
                overlap = lexical_overlap_score(query_tokens, sentence)
                sentence_score = overlap + (0.15 if len(sentence) >= 60 else 0.0)
                if sentence_score > best_score:
                    best_sentence = sentence
                    best_score = sentence_score

            reference = f"{decision['daire']} {decision['esas_no']} E. {decision['karar_no']} K."
            if reference in seen_refs:
                continue
            bullets.append(
                {
                    "summary": best_sentence[:320].strip(),
                    "reference": reference,
                }
            )
            seen_refs.add(reference)
            if len(bullets) >= 3:
                return bullets
    return bullets


def render_text(results: list[dict[str, object]], query: str) -> None:
    print(f"Sorgu: {query}")
    print(f"Karar sayisi: {len(results)}")
    summary = summarize_results(query, results)
    if summary:
        print("Ozet:")
        for item in summary:
            print(f"- {item['summary']} [{item['reference']}]")

    for index, decision in enumerate(results, start=1):
        print()
        print(
            f"{index}. score={decision['score']:.4f} | {decision['daire']} | "
            f"{decision['esas_no']} E. | {decision['karar_no']} K. | {decision['karar_tarihi']}"
        )
        if decision["mahkeme"]:
            print(f"   Mahkeme: {decision['mahkeme']}")
        if decision["outcome"]:
            print(f"   Sonuc: {decision['outcome']}")
        if decision["source_url"]:
            print(f"   Kaynak: {decision['source_url']}")
        for passage in decision["passages"]:
            section_name = passage["section_name"] or "metin"
            display_section = SECTION_DISPLAY_NAMES.get(section_name, section_name)
            print(
                f"   - [{display_section}] score={passage['adjusted_score']:.4f} "
                f"{passage['chunk_text'][:400].strip()}"
            )


def run_search(args: argparse.Namespace) -> int:
    try:
        import psycopg
        from pgvector.psycopg import Vector, register_vector
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "Arama bagimliliklari eksik. `pip install -r ingestion/requirements.txt` calistirin."
        ) from exc

    model = load_model(args.model_name, args.device, args.local_files_only)
    query_text = prepare_query_text(args.query)
    if not query_text:
        raise RuntimeError("Bos sorgu gonderilemez.")

    query_embedding = model.encode(
        [query_text],
        batch_size=1,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]

    sql, raw_params = build_search_sql(args)
    params: list[object] = []
    vector_placeholder_count = 0
    for value in raw_params:
        if value is None:
            vector_placeholder_count += 1
            params.append(Vector(query_embedding.tolist()))
        else:
            params.append(value)
    if vector_placeholder_count != 2:
        raise RuntimeError("Beklenmeyen SQL parametre yapisi.")

    conninfo = build_postgres_conninfo()
    with psycopg.connect(conninfo, row_factory=dict_row) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    query_tokens = tokenize_query(args.query)
    results = group_results(rows, query_tokens, args.max_passages_per_decision, args.top_decisions)
    output = {
        "query": args.query,
        "query_model": args.model_name,
        "search_mode": "hybrid",
        "top_k_chunks": args.top_k_chunks,
        "top_k_lexical": args.top_k_lexical,
        "top_decisions": args.top_decisions,
        "summary": summarize_results(args.query, results),
        "results": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        render_text(results, args.query)
        print()
        print("SEARCH_RESULT::" + json.dumps(output, ensure_ascii=False))
    return 0


def main() -> None:
    args = parse_args()
    raise SystemExit(run_search(args))


if __name__ == "__main__":
    main()
