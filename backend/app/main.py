from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.exceptions import AppError
from backend.app.routers.health import router as health_router
from backend.app.routers.search import router as search_router


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    summary="Semantic and hybrid legal decision search backend.",
    description=(
        "Provides health and search endpoints for the RAGITAY legal decision search system. "
        "Search responses include decision metadata, relevant passages, and short extractive summaries."
    ),
    contact={"name": "RAGITAY"},
    openapi_tags=[
        {"name": "health", "description": "Service health and liveness endpoints."},
        {"name": "search", "description": "Hybrid semantic and lexical legal decision search endpoints."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "code": "validation_error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Unexpected server error.",
            "code": "internal_server_error",
        },
    )

app.include_router(health_router)
app.include_router(search_router)
