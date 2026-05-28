from __future__ import annotations

import re


DEFAULT_EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"
DEFAULT_EMBEDDING_DIM = 768

WHITESPACE_RE = re.compile(r"\s+")


def normalize_embedding_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def prepare_passage_text(text: str) -> str:
    normalized = normalize_embedding_text(text)
    return f"passage: {normalized}" if normalized else ""


def prepare_query_text(text: str) -> str:
    normalized = normalize_embedding_text(text)
    return f"query: {normalized}" if normalized else ""
