"""Trusted on-call notification side effect (R5). Does not classify emergencies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.clock import reference_now
from app.config import get_settings
from app.models import Lead


def notify_on_call(
    lead: Lead,
    *,
    log_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Append one JSON line to the notifications log.

    The caller decides that Appendix E emergency policy applies.
    This function only performs the trusted notify side effect.
    """
    path = Path(log_path) if log_path is not None else Path(get_settings().notifications_log_path)
    payload: dict[str, Any] = {
        "lead_id": lead.lead_id,
        "phone": lead.phone,
        "name": lead.name,
        "postcode": lead.postcode,
        "notified_at": reference_now().isoformat(),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return payload
