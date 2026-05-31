from __future__ import annotations

import re
from collections import OrderedDict
from typing import Optional

from backend.app.config import get_settings
from backend.app.exceptions import SearchError
from backend.app.repositories.search_repository import SearchRepository
from backend.app.schemas.search import SearchRequest, SearchResponse, SummaryItem
from backend.app.services.embedding_service import EmbeddingService, tokenize_query


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
    "ilk_derece_mahkemesi_karari",
    "mahkeme_karari",
}
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class SearchService:
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        repository: Optional[SearchRepository] = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.repository = repository or SearchRepository()
        self.settings = get_settings()

    def search(self, request: SearchRequest) -> SearchResponse:
        query_embedding = self.embedding_service.embed_query(request.query)
        rows = self.repository.search_chunks(
            query_embedding=query_embedding,
            query_text=request.query,
            source_names=request.source_names,
            daire=request.daire,
            year_from=request.year_from,
            year_to=request.year_to,
            top_k_chunks=request.top_k_chunks,
            top_k_lexical=request.top_k_lexical,
        )

        query_tokens = tokenize_query(request.query)
        results = self._group_results(
            rows=rows,
            query_tokens=query_tokens,
            max_passages_per_decision=request.max_passages_per_decision,
            top_decisions=request.top_decisions,
        )
        summary = self._summarize_results(request.query, results)

        if not results:
            raise SearchError(
                message="No relevant decisions were found for the given query.",
                code="no_results",
                status_code=404,
            )

        return SearchResponse(
            query=request.query,
            query_model=self.settings.embedding_model_name,
            search_mode="hybrid",
            top_k_chunks=request.top_k_chunks,
            top_k_lexical=request.top_k_lexical,
            top_decisions=request.top_decisions,
            summary=[SummaryItem(**item) for item in summary],
            results=results,
        )

    def get_decision_detail(self, decision_id: int) -> dict[str, object]:
        detail = self.repository.get_decision_detail(decision_id)
        if not detail:
            raise SearchError(
                message="Requested decision could not be found.",
                code="decision_not_found",
                status_code=404,
            )

        sections = detail.get("sections")
        if not isinstance(sections, dict):
            detail["sections"] = {}
        return detail

    def _group_results(
        self,
        *,
        rows: list[dict[str, object]],
        query_tokens: list[str],
        max_passages_per_decision: int,
        top_decisions: int,
    ) -> list[dict[str, object]]:
        decisions: OrderedDict[int, dict[str, object]] = OrderedDict()

        for row in rows:
            chunk_text = str(row["chunk_text"])
            section_name = str(row.get("section_name") or "")
            if self._is_low_value_chunk_text(chunk_text):
                continue
            if self._is_low_information_result_chunk(section_name, chunk_text):
                continue

            decision_id = int(row["decision_id"])
            score = self._adjusted_similarity(row, query_tokens)
            if decision_id not in decisions:
                decisions[decision_id] = {
                    "decision_id": decision_id,
                    "source_name": row["source_name"],
                    "external_id": row["external_id"],
                    "title": row["title"],
                    "daire": row["daire"],
                    "esas_no": row["esas_no"],
                    "karar_no": row["karar_no"],
                    "karar_tarihi": row["karar_tarihi"],
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

    def _summarize_results(self, query: str, results: list[dict[str, object]]) -> list[dict[str, str]]:
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
                sentences = [self._clean_summary_sentence(part) for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
                if not sentences:
                    continue

                best_sentence = sentences[0]
                best_score = -1.0
                for sentence in sentences:
                    overlap = self._lexical_overlap_score(query_tokens, sentence)
                    sentence_score = overlap + (0.15 if len(sentence) >= 60 else 0.0)
                    if sentence_score > best_score:
                        best_sentence = sentence
                        best_score = sentence_score

                reference = f"{decision['daire']} {decision['esas_no']} E. {decision['karar_no']} K."
                if reference in seen_refs:
                    continue
                bullets.append({"summary": best_sentence[:320].strip(), "reference": reference})
                seen_refs.add(reference)
                if len(bullets) >= 3:
                    return bullets
        return bullets

    @staticmethod
    def _clean_summary_sentence(text: str) -> str:
        cleaned = " ".join(text.split())
        cleaned = cleaned.replace("I. DAVA", "").replace("II. CEVAP", "").replace("III. İLK DERECE MAHKEMESİ KARARI", "")
        cleaned = cleaned.replace("IV. İSTİNAF", "").replace("V. TEMYİZ", "").replace("VI. KARAR", "")
        return cleaned.strip(" -:\n")

    @staticmethod
    def _is_low_value_chunk_text(text: str) -> bool:
        normalized = " ".join(text.lower().split())
        alpha_count = sum(1 for char in normalized if char.isalpha())
        if alpha_count < 60:
            return True
        if len(normalized) < 300 and any(phrase in normalized for phrase in LOW_VALUE_PHRASES):
            return True
        return False

    @staticmethod
    def _is_low_information_result_chunk(section_name: str, text: str) -> bool:
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

    @staticmethod
    def _lexical_overlap_score(query_tokens: list[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        lowered = text.lower()
        hits = sum(1 for token in query_tokens if token in lowered)
        return hits / len(query_tokens)

    def _adjusted_similarity(self, row: dict[str, object], query_tokens: list[str]) -> float:
        semantic_score = float(row["semantic_score"])
        lexical_score = float(row["lexical_score"])
        section_name = str(row.get("section_name") or "")
        section_bonus = SECTION_WEIGHTS.get(section_name, 0.0)
        overlap_value = self._lexical_overlap_score(query_tokens, str(row.get("chunk_text") or ""))
        overlap_bonus = overlap_value * 0.18
        lexical_penalty = -0.07 if lexical_score <= 0.001 else 0.0
        generic_penalty = -0.08 if section_name == "cevap" and overlap_value <= 0.01 else 0.0
        return (semantic_score * 0.72) + (lexical_score * 0.22) + section_bonus + overlap_bonus + lexical_penalty + generic_penalty
