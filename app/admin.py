"""Admin lead read API — never exposed to the agent tool runtime."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.models import Lead, LeadStatus
from app.schemas import Lead as LeadSchema

router = APIRouter(tags=["admin"])

ALLOWED_STATUS_FILTER = {s.value for s in LeadStatus}


def require_admin_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    settings = get_settings()
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin API key is not configured",
        )
    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@router.get("/leads", response_model=list[LeadSchema], dependencies=[Depends(require_admin_api_key)])
def list_leads(
    session: Session = Depends(get_db),
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[Lead]:
    stmt = select(Lead).order_by(Lead.created_at.asc())
    if status_filter is not None:
        if status_filter not in ALLOWED_STATUS_FILTER:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status filter: {status_filter}",
            )
        stmt = stmt.where(Lead.status == status_filter)
    return list(session.scalars(stmt).all())


@router.get(
    "/leads/{lead_id}",
    response_model=LeadSchema,
    dependencies=[Depends(require_admin_api_key)],
)
def get_lead(lead_id: str, session: Session = Depends(get_db)) -> Lead:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead
