"""FastAPI entrypoint."""

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.agent.orchestrator import handle_enquiry
from app.deps import get_db, get_llm
from app.llm import LLMClient
from app.schemas import EnquiryRequest, EnquiryResponse

app = FastAPI(title="RafterFlow", version="0.3.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rafterflow"}


@app.post("/enquiries", response_model=EnquiryResponse)
def create_enquiry(
    request: EnquiryRequest,
    session: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> EnquiryResponse:
    return handle_enquiry(session, request, llm)
