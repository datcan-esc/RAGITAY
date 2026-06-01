from __future__ import annotations

import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore[assignment]

from backend.app.config import get_settings
from backend.app.exceptions import AppError
from backend.app.repositories.search_repository import SearchRepository
from backend.app.schemas.summary import (
    DecisionMiniSummary,
    DecisionSummaryRequest,
    DecisionSummaryResponse,
    SummaryDecisionInput,
    SummaryPassageInput,
    SummaryRequest,
    SummaryResponse,
)


class SummaryError(AppError):
    def __init__(self, message: str, code: str = "summary_error", status_code: int = 400) -> None:
        super().__init__(message=message, code=code, status_code=status_code)


class SummaryService:
    def __init__(self, repository: Optional[SearchRepository] = None) -> None:
        self.settings = get_settings()
        self.repository = repository or SearchRepository()
        self.openai_client: Optional[Any] = None
        if self.settings.openai_api_key and OpenAI is not None:
            client_kwargs: dict[str, Any] = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                client_kwargs["base_url"] = self.settings.openai_base_url
            self.openai_client = OpenAI(**client_kwargs)

    def summarize(self, request: SummaryRequest) -> SummaryResponse:
        cleaned_query = " ".join(request.query.split())
        if len(cleaned_query) < 2:
            raise SummaryError("Summary query must contain at least 2 characters.", code="invalid_query")
        if not request.results:
            raise SummaryError("At least one search result is required for summarization.", code="missing_results")

        trimmed_results = request.results[: self.settings.summary_max_decisions]
        provider = self.settings.summary_provider

        try:
            if provider == "openai" and self.openai_client:
                return self._openai_summary(cleaned_query, trimmed_results)
            if provider == "gemini" and self.settings.gemini_api_key:
                return self._gemini_summary(cleaned_query, trimmed_results)
        except Exception:
            return self._fallback_summary(cleaned_query, trimmed_results)

        return self._fallback_summary(cleaned_query, trimmed_results)

    def summarize_decision(
        self,
        decision_id: int,
        request: DecisionSummaryRequest,
    ) -> DecisionSummaryResponse:
        cleaned_query = " ".join(request.query.split())
        detail = self.repository.get_decision_detail(decision_id)
        if not detail:
            raise SummaryError(
                "Requested decision could not be found.",
                code="decision_not_found",
                status_code=404,
            )

        decision_input = SummaryDecisionInput(
            decision_id=int(detail["decision_id"]),
            title=str(detail.get("title", "")),
            daire=str(detail.get("daire", "")),
            esas_no=str(detail.get("esas_no", "")),
            karar_no=str(detail.get("karar_no", "")),
            karar_tarihi=str(detail.get("karar_tarihi", "") or ""),
            outcome=str(detail.get("outcome", "") or ""),
            passages=self._decision_passages_from_detail(detail),
        )

        provider = self.settings.summary_provider
        try:
            if provider == "openai" and self.openai_client:
                return self._openai_decision_summary(cleaned_query, decision_input)
            if provider == "gemini" and self.settings.gemini_api_key:
                return self._gemini_decision_summary(cleaned_query, decision_input)
        except Exception:
            return self._fallback_decision_summary(cleaned_query, decision_input)

        return self._fallback_decision_summary(cleaned_query, decision_input)

    def _openai_summary(self, query: str, results: list[SummaryDecisionInput]) -> SummaryResponse:
        compact_results = [self._compact_result(result) for result in results]
        system_prompt = (
            "You are a legal retrieval summarizer for Turkish court decisions. "
            "Only use the provided decisions and passages. Do not invent facts, legal rules, or references. "
            "Return strict JSON with keys: general_summary, key_points. "
            "general_summary must be 2-3 sentences in Turkish. "
            "key_points must contain 2-4 concise bullet-style strings in Turkish."
        )
        user_prompt = json.dumps({"query": query, "results": compact_results}, ensure_ascii=False)

        response = self.openai_client.responses.create(
            model=self.settings.summary_model_name,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        )
        parsed = self._parse_json(response.output_text)
        return self._build_summary_response(query, parsed, "openai", self.settings.summary_model_name, False)

    def _gemini_summary(self, query: str, results: list[SummaryDecisionInput]) -> SummaryResponse:
        compact_results = [self._compact_result(result) for result in results]
        prompt = (
            "Yalnızca verilen kararlar ve pasajlar üzerinden özet üret. "
            "Hiçbir bilgi uydurma. Çıktıyı strict JSON olarak ver. "
            "Anahtarlar: general_summary, key_points. "
            "general_summary: Türkçe 2-3 cümle. "
            "key_points: 2-4 kısa Türkçe madde.\n\n"
            f"Query: {query}\n"
            f"Results: {json.dumps(compact_results, ensure_ascii=False)}"
        )
        parsed = self._call_gemini(prompt)
        return self._build_summary_response(query, parsed, "gemini", self.settings.summary_model_name, False)

    def _fallback_summary(self, query: str, results: list[SummaryDecisionInput]) -> SummaryResponse:
        snippets: list[str] = []
        for result in results:
            first_passage = result.passages[0].chunk_text if result.passages else result.title
            snippets.append(self._shorten(first_passage, 260))

        general_summary = " ".join(snippet for snippet in snippets[:2] if snippet).strip()
        if not general_summary:
            general_summary = "Bulunan kararlar sorguyla ilişkili benzer uyuşmazlıkları ve ilgili hukuki değerlendirmeleri göstermektedir."

        return SummaryResponse(
            query=query,
            general_summary=general_summary,
            key_points=[self._shorten(snippet, 180) for snippet in snippets[:3] if snippet],
            provider="fallback",
            model="extractive-summary",
            fallback_used=True,
        )

    def _openai_decision_summary(
        self,
        query: str,
        decision: SummaryDecisionInput,
    ) -> DecisionSummaryResponse:
        system_prompt = (
            "You are a Turkish legal decision summarizer. "
            "Use only the provided decision and passages. "
            "Return strict JSON with keys: short_summary, why_relevant. "
            "short_summary should be a concise Turkish paragraph. "
            "why_relevant should be one Turkish sentence that relates the decision to the user's query."
        )
        user_prompt = json.dumps(
            {
                "query": query,
                "decision": self._compact_result(decision, passages_limit=3),
            },
            ensure_ascii=False,
        )

        response = self.openai_client.responses.create(
            model=self.settings.summary_model_name,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        )
        parsed = self._parse_json(response.output_text)
        return self._build_decision_summary_response(
            query=query,
            decision=decision,
            parsed=parsed,
            provider="openai",
            model=self.settings.summary_model_name,
            fallback_used=False,
        )

    def _gemini_decision_summary(
        self,
        query: str,
        decision: SummaryDecisionInput,
    ) -> DecisionSummaryResponse:
        prompt = (
            "Sadece verilen karar ve pasajlar üzerinden özet üret. "
            "Bilgi uydurma. Çıktıyı strict JSON ver. "
            "Anahtarlar: short_summary, why_relevant. "
            "short_summary kısa bir Türkçe paragraf olsun. "
            "why_relevant, kararın sorguyla neden ilgili olduğunu tek cümleyle anlatsın.\n\n"
            f"Query: {query}\n"
            f"Decision: {json.dumps(self._compact_result(decision, passages_limit=3), ensure_ascii=False)}"
        )
        parsed = self._call_gemini(prompt)
        return self._build_decision_summary_response(
            query=query,
            decision=decision,
            parsed=parsed,
            provider="gemini",
            model=self.settings.summary_model_name,
            fallback_used=False,
        )

    def _fallback_decision_summary(
        self,
        query: str,
        decision: SummaryDecisionInput,
    ) -> DecisionSummaryResponse:
        first_passage = decision.passages[0].chunk_text if decision.passages else decision.title
        return DecisionSummaryResponse(
            query=query,
            decision_summary=DecisionMiniSummary(
                decision_id=decision.decision_id,
                reference=self._reference(decision),
                short_summary=self._shorten(first_passage, 320),
                why_relevant=self._why_relevant(query, decision),
            ),
            provider="fallback",
            model="extractive-decision-summary",
            fallback_used=True,
        )

    def _call_gemini(self, prompt: str) -> dict[str, Any]:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        endpoint = (
            f"{self.settings.gemini_base_url.rstrip('/')}/v1beta/models/"
            f"{self.settings.summary_model_name}:generateContent?key={self.settings.gemini_api_key}"
        )
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError) as exc:
            raise SummaryError("Gemini summary request failed.", code="gemini_request_failed", status_code=502) from exc

        payload_json = json.loads(raw)
        text = self._extract_gemini_text(payload_json)
        return self._parse_json(text)

    def _decision_passages_from_detail(self, detail: dict[str, object]) -> list[SummaryPassageInput]:
        sections = detail.get("sections")
        passages: list[SummaryPassageInput] = []
        if isinstance(sections, dict):
            for section_name, section_text in sections.items():
                if isinstance(section_text, str) and section_text.strip():
                    passages.append(SummaryPassageInput(section_name=str(section_name), chunk_text=section_text))
        if passages:
            return passages[:4]

        full_text = str(detail.get("full_text", "")).strip()
        if not full_text:
            return []
        return [SummaryPassageInput(section_name="full_text", chunk_text=full_text)]

    def _compact_result(self, result: SummaryDecisionInput, passages_limit: int = 2) -> dict[str, Any]:
        return {
            "decision_id": result.decision_id,
            "reference": self._reference(result),
            "title": result.title,
            "outcome": result.outcome,
            "passages": [
                {
                    "section_name": passage.section_name,
                    "chunk_text": passage.chunk_text[: self.settings.summary_max_passage_chars],
                }
                for passage in result.passages[:passages_limit]
            ],
        }

    @staticmethod
    def _reference(result: SummaryDecisionInput) -> str:
        return f"{result.daire} {result.esas_no} E. {result.karar_no} K.".strip()

    @staticmethod
    def _extract_gemini_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            raise SummaryError("Gemini returned no candidates.", code="gemini_empty_response", status_code=502)
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [str(part.get("text", "")) for part in parts if str(part.get("text", "")).strip()]
        if not texts:
            raise SummaryError("Gemini returned no text content.", code="gemini_empty_text", status_code=502)
        return "\n".join(texts)

    @staticmethod
    def _parse_json(raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        return json.loads(cleaned)

    @staticmethod
    def _build_summary_response(
        query: str,
        parsed: dict[str, Any],
        provider: str,
        model: str,
        fallback_used: bool,
    ) -> SummaryResponse:
        return SummaryResponse(
            query=query,
            general_summary=str(parsed.get("general_summary", "")).strip(),
            key_points=[str(item).strip() for item in parsed.get("key_points", []) if str(item).strip()],
            provider=provider,
            model=model,
            fallback_used=fallback_used,
        )

    def _build_decision_summary_response(
        self,
        *,
        query: str,
        decision: SummaryDecisionInput,
        parsed: dict[str, Any],
        provider: str,
        model: str,
        fallback_used: bool,
    ) -> DecisionSummaryResponse:
        return DecisionSummaryResponse(
            query=query,
            decision_summary=DecisionMiniSummary(
                decision_id=decision.decision_id,
                reference=self._reference(decision),
                short_summary=str(parsed.get("short_summary", "")).strip(),
                why_relevant=str(parsed.get("why_relevant", "")).strip(),
            ),
            provider=provider,
            model=model,
            fallback_used=fallback_used,
        )

    @staticmethod
    def _shorten(text: str, max_length: int) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_length:
            return cleaned
        return cleaned[: max_length - 1].rstrip() + "…"

    def _why_relevant(self, query: str, result: SummaryDecisionInput) -> str:
        section = result.passages[0].section_name if result.passages else "metin"
        section_label = section.replace("_", " ")
        return (
            f"Bu karar, sorguyla ilişkili değerlendirmeyi '{section_label}' bölümünde içeren bir pasaj taşıdığı için öne çıktı."
        )
