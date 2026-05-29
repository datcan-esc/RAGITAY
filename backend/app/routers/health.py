from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Healthcheck",
    description="Simple liveness endpoint for local and container health checks.",
)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")
