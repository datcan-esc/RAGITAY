from __future__ import annotations

import re
from functools import cached_property

from sentence_transformers import SentenceTransformer

from backend.app.config import get_settings
from backend.app.exceptions import SearchError


TOKEN_RE = re.compile(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{3,}")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def prepare_query_text(text: str) -> str:
    normalized = normalize_text(text)
    return f"query: {normalized}" if normalized else ""


def tokenize_query(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @cached_property
    def model(self) -> SentenceTransformer:
        kwargs: dict[str, object] = {}
        if self.settings.embedding_device:
            kwargs["device"] = self.settings.embedding_device
        if self.settings.embedding_local_files_only:
            kwargs["local_files_only"] = True
        return SentenceTransformer(self.settings.embedding_model_name, **kwargs)

    def embed_query(self, query: str) -> list[float]:
        prepared = prepare_query_text(query)
        if not prepared:
            raise SearchError(message="Query cannot be empty.", code="empty_query", status_code=400)

        vector = self.model.encode(
            [prepared],
            batch_size=1,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]
        return vector.tolist()
