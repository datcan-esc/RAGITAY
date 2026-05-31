from __future__ import annotations

import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from openai import OpenAI

from backend.app.config import get_settings
from backend.app.exceptions import AppError
from backend.app.schemas.summary import (
    DecisionMiniSummary,
    SummaryDecisionInput,
    SummaryRequest,
    SummaryResponse,
)

class SummaryError(AppError):
    def __init__(self, message: str, code: str = "summary_error", status_code: int = 400) -> None:
        super().__init__(message=message, code=code, status_code=status_code)


class SummaryService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.openai_client: Optional[OpenAI] = None
        if self.settings.openai_api_key:
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

    def _openai_summary(
        self,
        query: str,
        results: list[SummaryDecisionInput],
    ) -> SummaryResponse:
        compact_results = []
        for result in results:
            compact_results.append(
                {
                    "decision_id": result.decision_id,
                    "reference": self._reference(result),
                    "title": result.title,
                    "outcome": result.outcome,
                    "passages": [
                        {
                            "section_name": passage.section_name,
                            "chunk_text": passage.chunk_text[: self.settings.summary_max_passage_chars],
                        }
                        for passage in result.passages[:2]
                    ],
                }
            )

        system_prompt = (
            "You are a legal retrieval summarizer for Turkish court decisions. "
            "Only use the provided decisions and passages. Do not invent facts, legal rules, or references. "
            "Return strict JSON with keys: general_summary, key_points, decision_summaries. "
            "general_summary must be 2-3 sentences in Turkish. "
            "key_points must contain 2-4 concise bullet-style strings in Turkish. "
            "decision_summaries must be an array where each item has decision_id, reference, short_summary, why_relevant. "
            "short_summary should be 1 short paragraph in Turkish. "
            "why_relevant should explain in one sentence why that decision is relevant to the user's query."
        )

        user_prompt = json.dumps(
            {
                "query": query,
                "results": compact_results,
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

        parsed = self._parse_summary_json(response.output_text)
        return self._build_summary_response(
            query=query,
            parsed=parsed,
            provider="openai",
            model=self.settings.summary_model_name,
            fallback_used=False,
        )

    def _gemini_summary(
        self,
        query: str,
        results: list[SummaryDecisionInput],
    ) -> SummaryResponse:
        compact_results = []
        for result in results:
            compact_results.append(
                {
                    "decision_id": result.decision_id,
                    "reference": self._reference(result),
                    "title": result.title,
                    "outcome": result.outcome,
                    "passages": [
                        {
                            "section_name": passage.section_name,
                            "chunk_text": passage.chunk_text[: self.settings.summary_max_passage_chars],
                        }
                        for passage in result.passages[:2]
                    ],
                }
            )

        prompt = (
            "Yalnızca verilen kararlar ve pasajlar üzerinden özet üret. "
            "Hiçbir bilgi uydurma. Çıktıyı strict JSON olarak ver. "
            "Anahtarlar: general_summary, key_points, decision_summaries. "
            "general_summary: Türkçe 2-3 cümle. "
            "key_points: 2-4 kısa Türkçe madde. "
            "decision_summaries: her karar için decision_id, reference, short_summary, why_relevant. "
            "short_summary kısa bir paragraf olsun. why_relevant tek cümle olsun.\n\n"
            f"Query: {query}\n"
            f"Results: {json.dumps(compact_results, ensure_ascii=False)}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
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

        response_json = json.loads(raw)
        text = self._extract_gemini_text(response_json)
        parsed = self._parse_summary_json(text)
        return self._build_summary_response(
            query=query,
            parsed=parsed,
            provider="gemini",
            model=self.settings.summary_model_name,
            fallback_used=False,
        )

    def _fallback_summary(
        self,
        query: str,
        results: list[SummaryDecisionInput],
    ) -> SummaryResponse:
        decision_summaries: list[DecisionMiniSummary] = []
        key_points: list[str] = []

        for result in results:
            first_passage = result.passages[0].chunk_text if result.passages else ""
            short_summary = self._shorten(first_passage, 260)
            if not short_summary:
                short_summary = result.title

            why_relevant = self._why_relevant(query, result)
            decision_summaries.append(
                DecisionMiniSummary(
                    decision_id=result.decision_id,
                    reference=self._reference(result),
                    short_summary=short_summary,
                    why_relevant=why_relevant,
                )
            )
            if short_summary:
                key_points.append(short_summary)

        general_summary = " ".join(item.short_summary for item in decision_summaries[:2]).strip()
        if not general_summary:
            general_summary = "Bulunan kararlar sorguyla ilişkili benzer uyuşmazlıkları ve ilgili hukuki değerlendirmeleri göstermektedir."

        return SummaryResponse(
            query=query,
            general_summary=general_summary,
            key_points=[self._shorten(point, 180) for point in key_points[:3]],
            decision_summaries=decision_summaries,
            provider="fallback",
            model="extractive-summary",
            fallback_used=True,
        )

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
    def _parse_summary_json(raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        return json.loads(cleaned)

    @staticmethod
    def _build_summary_response(
        *,
        query: str,
        parsed: dict[str, Any],
        provider: str,
        model: str,
        fallback_used: bool,
    ) -> SummaryResponse:
        decision_summaries = [
            DecisionMiniSummary(**item) for item in parsed.get("decision_summaries", [])
        ]
        return SummaryResponse(
            query=query,
            general_summary=str(parsed.get("general_summary", "")).strip(),
            key_points=[str(item).strip() for item in parsed.get("key_points", []) if str(item).strip()],
            decision_summaries=decision_summaries,
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
