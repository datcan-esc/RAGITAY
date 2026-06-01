from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.dependencies import (
    get_decision_chat_service,
    get_search_service,
    get_summary_service,
)
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.decision_chat import DecisionChatRequest, DecisionChatResponse
from backend.app.schemas.search import (
    DecisionDetailResponse,
    SearchRequest,
    SearchResponse as SearchResultsResponse,
)
from backend.app.schemas.summary import (
    DecisionSummaryRequest,
    DecisionSummaryResponse,
    SummaryRequest,
    SummaryResponse as SummaryApiResponse,
)
from backend.app.services.decision_chat_service import DecisionChatService
from backend.app.services.search_service import SearchService
from backend.app.services.summary_service import SummaryService


router = APIRouter(prefix="/api/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResultsResponse,
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
) -> SearchResultsResponse:
    return service.search(request)


@router.get(
    "/decisions/{decision_id}",
    response_model=DecisionDetailResponse,
    summary="Legal decision detail",
    description="Returns the full text and extracted sections for a single legal decision.",
    responses={
        404: {"model": ErrorResponse, "description": "Decision not found."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
    },
)
def get_decision_detail(
    decision_id: int,
    service: SearchService = Depends(get_search_service),
) -> DecisionDetailResponse:
    return DecisionDetailResponse(**service.get_decision_detail(decision_id))


@router.post(
    "/summary",
    response_model=SummaryApiResponse,
    summary="Summarize retrieved legal decisions",
    description=(
        "Builds a compact, reference-grounded summary from already retrieved legal search results. "
        "If an LLM provider is configured, it produces a natural-language summary; otherwise it falls back to extractive summarization."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid summary request."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
    },
)
def summarize_results(
    request: SummaryRequest,
    service: SummaryService = Depends(get_summary_service),
) -> SummaryApiResponse:
    return service.summarize(request)


@router.post(
    "/decisions/{decision_id}/summary",
    response_model=DecisionSummaryResponse,
    summary="Summarize a selected legal decision",
    description="Produces a compact AI summary only for the selected decision.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid summary request."},
        404: {"model": ErrorResponse, "description": "Decision not found."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
    },
)
def summarize_decision(
    decision_id: int,
    request: DecisionSummaryRequest,
    service: SummaryService = Depends(get_summary_service),
) -> DecisionSummaryResponse:
    return service.summarize_decision(decision_id, request)


@router.post(
    "/decisions/{decision_id}/ask",
    response_model=DecisionChatResponse,
    summary="Ask a question about a selected legal decision",
    description=(
        "Uses only the selected decision as context and produces a concise answer with key points."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid question."},
        404: {"model": ErrorResponse, "description": "Decision not found."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
    },
)
def ask_about_decision(
    decision_id: int,
    request: DecisionChatRequest,
    service: DecisionChatService = Depends(get_decision_chat_service),
) -> DecisionChatResponse:
    return service.answer(decision_id, request.question)
