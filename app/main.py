"""FastAPI entrypoint."""

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.admin import router as admin_router
from app.agent.orchestrator import handle_enquiry
from app.audit import AuditLogError
from app.deps import get_db, get_llm
from app.llm import LLMClient
from app.schemas import EnquiryRequest, EnquiryResponse
from fastapi import HTTPException, status

app = FastAPI(title="RafterFlow", version="0.4.0")
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rafterflow"}


@app.post("/enquiries", response_model=EnquiryResponse)
def create_enquiry(
    request: EnquiryRequest,
    session: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> EnquiryResponse:
    try:
        return handle_enquiry(session, request, llm)
    except AuditLogError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
