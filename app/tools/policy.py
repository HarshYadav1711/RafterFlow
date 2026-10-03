"""Exact Appendix E policy retrieval. No RAG, embeddings, or rewriting."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import PolicyRecord

KNOWN_TOPICS = (
    "business",
    "office_hours",
    "emergency",
    "services_offered",
    "services_not_offered",
    "quote_policy",
    "warranty_policy",
    "insurance_policy",
)


class PolicyNotFoundError(LookupError):
    pass


def get_policy(session: Session, topic: str) -> Any:
    """Return the JSON-decoded policy fragment for an exact topic key."""
    row = session.get(PolicyRecord, topic)
    if row is None:
        raise PolicyNotFoundError(topic)
    return json.loads(row.content_json)


def get_policies(session: Session) -> dict[str, Any]:
    """Return all known Appendix E topics present in the database."""
    result: dict[str, Any] = {}
    for topic in KNOWN_TOPICS:
        row = session.get(PolicyRecord, topic)
        if row is not None:
            result[topic] = json.loads(row.content_json)
    return result
