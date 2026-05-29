from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.dependencies import get_search_service
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.search import SearchRequest, SearchResponse
from backend.app.services.search_service import SearchService


router = APIRouter(prefix="/api/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    summary="Hybrid legal decision search",
    description=(
        "Runs hybrid retrieval over indexed legal decision chunks and returns "
        "decision-level results with relevant passages and a short extractive summary."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request or search error."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
    },
)
def search(
    request: SearchRequest,
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return service.search(request)
