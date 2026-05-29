from __future__ import annotations

from functools import lru_cache

from backend.app.repositories.search_repository import SearchRepository
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.search_service import SearchService


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_search_repository() -> SearchRepository:
    return SearchRepository()


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    return SearchService(
        embedding_service=get_embedding_service(),
        repository=get_search_repository(),
    )
