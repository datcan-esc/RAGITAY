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
from backend.app.schemas.decision_chat import DecisionChatResponse
from backend.app.services.embedding_service import tokenize_query


class DecisionChatError(AppError):
    def __init__(
        self,
        message: str,
        code: str = "decision_chat_error",
        status_code: int = 400,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code)


class DecisionChatService:
    def __init__(self, repository: Optional[SearchRepository] = None) -> None:
        self.settings = get_settings()
        self.repository = repository or SearchRepository()
        self.openai_client: Optional[Any] = None
        if self.settings.openai_api_key and OpenAI is not None:
            client_kwargs: dict[str, Any] = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                client_kwargs["base_url"] = self.settings.openai_base_url
            self.openai_client = OpenAI(**client_kwargs)

    def answer(self, decision_id: int, question: str) -> DecisionChatResponse:
        detail = self.repository.get_decision_detail(decision_id)
        if not detail:
            raise DecisionChatError(
                "Requested decision could not be found.",
                code="decision_not_found",
                status_code=404,
            )

        cleaned_question = " ".join(question.split())
        reference = self._reference(detail)
        provider = self.settings.summary_provider

        try:
            if provider == "openai" and self.openai_client:
                return self._openai_answer(detail, cleaned_question, reference)
            if provider == "gemini" and self.settings.gemini_api_key:
                return self._gemini_answer(detail, cleaned_question, reference)
        except Exception:
            return self._fallback_answer(detail, cleaned_question, reference)

        return self._fallback_answer(detail, cleaned_question, reference)

    def _openai_answer(
        self,
        detail: dict[str, object],
        question: str,
        reference: str,
    ) -> DecisionChatResponse:
        system_prompt = (
            "You are a Turkish legal decision assistant. "
            "Answer only from the provided decision text and sections. "
            "Do not invent facts. Return strict JSON with keys: answer, key_points. "
            "answer must be in Turkish and concise. key_points must contain 2-4 short Turkish strings."
        )
        payload = json.dumps(
            {
                "reference": reference,
                "question": question,
                "context": self._build_context(detail, question),
            },
            ensure_ascii=False,
        )

        response = self.openai_client.responses.create(
            model=self.settings.summary_model_name,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": payload}]},
            ],
        )
        parsed = self._parse_json(response.output_text)
        return DecisionChatResponse(
            decision_id=int(detail["decision_id"]),
            reference=reference,
            answer=str(parsed.get("answer", "")).strip(),
            key_points=[str(item).strip() for item in parsed.get("key_points", []) if str(item).strip()],
            provider="openai",
            model=self.settings.summary_model_name,
            fallback_used=False,
        )

    def _gemini_answer(
        self,
        detail: dict[str, object],
        question: str,
        reference: str,
    ) -> DecisionChatResponse:
        prompt = (
            "Sadece verilen karar metnine ve bölümlerine dayanarak cevap ver. "
            "Bilgi uydurma. Çıktıyı strict JSON ver. "
            "Anahtarlar: answer, key_points. "
            "answer kısa ve Türkçe olsun. "
            "key_points 2-4 kısa Türkçe madde olsun.\n\n"
            f"Reference: {reference}\n"
            f"Question: {question}\n"
            f"Context: {json.dumps(self._build_context(detail, question), ensure_ascii=False)}"
        )
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
            raise DecisionChatError(
                "Gemini decision answer request failed.",
                code="gemini_decision_chat_failed",
                status_code=502,
            ) from exc

        payload_json = json.loads(raw)
        text = self._extract_gemini_text(payload_json)
        parsed = self._parse_json(text)
        return DecisionChatResponse(
            decision_id=int(detail["decision_id"]),
            reference=reference,
            answer=str(parsed.get("answer", "")).strip(),
            key_points=[str(item).strip() for item in parsed.get("key_points", []) if str(item).strip()],
            provider="gemini",
            model=self.settings.summary_model_name,
            fallback_used=False,
        )

    def _fallback_answer(
        self,
        detail: dict[str, object],
        question: str,
        reference: str,
    ) -> DecisionChatResponse:
        context = self._build_context(detail, question)
        text_blocks = [item["text"] for item in context if item.get("text")]
        answer = text_blocks[0] if text_blocks else str(detail.get("title", "")).strip()
        key_points = text_blocks[:3]
        return DecisionChatResponse(
            decision_id=int(detail["decision_id"]),
            reference=reference,
            answer=self._shorten(answer, 700),
            key_points=[self._shorten(item, 220) for item in key_points if item],
            provider="fallback",
            model="extractive-decision-chat",
            fallback_used=True,
        )

    def _build_context(self, detail: dict[str, object], question: str) -> list[dict[str, str]]:
        sections = detail.get("sections")
        question_tokens = tokenize_query(question)
        ranked_sections: list[tuple[float, str, str]] = []

        if isinstance(sections, dict):
            for section_name, section_text in sections.items():
                if not isinstance(section_text, str) or not section_text.strip():
                    continue
                overlap = self._overlap_score(question_tokens, section_text)
                ranked_sections.append((overlap, str(section_name), self._shorten(section_text, 2200)))

        ranked_sections.sort(key=lambda item: item[0], reverse=True)
        selected = ranked_sections[:4]
        if selected:
            return [{"section_name": name, "text": text} for _, name, text in selected]

        full_text = str(detail.get("full_text", "")).strip()
        if not full_text:
            return []
        return [{"section_name": "full_text", "text": self._shorten(full_text, 5000)}]

    @staticmethod
    def _overlap_score(tokens: list[str], text: str) -> float:
        normalized = text.lower()
        score = 0.0
        for token in tokens:
            if token and token in normalized:
                score += 1.0
        return score

    @staticmethod
    def _reference(detail: dict[str, object]) -> str:
        daire = str(detail.get("daire", "")).strip()
        esas = str(detail.get("esas_no", "")).strip()
        karar = str(detail.get("karar_no", "")).strip()
        return f"{daire} {esas} E. {karar} K.".strip()

    @staticmethod
    def _extract_gemini_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            raise DecisionChatError(
                "Gemini returned no candidates.",
                code="gemini_empty_response",
                status_code=502,
            )
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [str(part.get("text", "")) for part in parts if str(part.get("text", "")).strip()]
        if not texts:
            raise DecisionChatError(
                "Gemini returned no text content.",
                code="gemini_empty_text",
                status_code=502,
            )
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
    def _shorten(text: str, max_length: int) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_length:
            return cleaned
        return cleaned[: max_length - 1].rstrip() + "…"
