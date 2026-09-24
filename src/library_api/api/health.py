"""Liveness and readiness probes."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from library_api.api.deps import SessionDep

router = APIRouter(prefix="/health", tags=["Health"])


class HealthStatus(BaseModel):
    """Probe result."""

    status: Literal["ok", "unavailable"] = Field(
        description="``ok`` when healthy, ``unavailable`` otherwise."
    )


@router.get(
    "/live",
    response_model=HealthStatus,
    summary="Liveness probe",
    response_description="The process is running.",
)
def live() -> HealthStatus:
    """Report that the process is running (no dependencies are checked)."""
    return HealthStatus(status="ok")


@router.get(
    "/ready",
    response_model=HealthStatus,
    summary="Readiness probe",
    response_description="The service can reach its database.",
    responses={503: {"model": HealthStatus, "description": "Database unreachable."}},
)
def ready(session: SessionDep, response: Response) -> HealthStatus:
    """Report whether the service can reach its database."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = 503
        return HealthStatus(status="unavailable")
    return HealthStatus(status="ok")
