"""FastAPI application entry point for the Ola AI Data Agent API."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.agent import router as agent_router
from app.api.etl import router as etl_router
from app.api.sql import router as sql_router
from app.api.runs import router as runs_router
from app.core.config import live_agents_enabled
from app.models.agent import HealthResponse, MetadataResponse

app = FastAPI(
    title="Ola AI Data Agent API",
    description="A mock-first API with explicitly gated live agent execution.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(agent_router)
app.include_router(etl_router)
app.include_router(sql_router)
app.include_router(runs_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a controlled validation error without echoing request data."""
    del request, exc
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request payload."},
    )


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Report that the API process is available without checking services."""
    return HealthResponse(
        status="ok",
        service="ola-ai-data-agent-api",
        mode="mock",
    )


@app.get("/api/metadata", response_model=MetadataResponse, tags=["system"])
def metadata() -> MetadataResponse:
    """Describe the API capabilities currently available in this phase."""
    return MetadataResponse(
        service="ola-ai-data-agent-api",
        version=app.version,
        agent_execution_enabled=live_agents_enabled(),
        available_endpoints=[
            "GET /api/health",
            "GET /api/metadata",
            "POST /api/agent/run",
            "POST /api/sql/run",
            "GET /api/runs",
            "GET /api/runs/{run_id}",
            "POST /api/etl/extract",
            "POST /api/etl/transform",
            "GET /api/files",
            "GET /api/files/{file_id}/preview",
            "GET /api/files/{file_id}/download",
        ],
    )
