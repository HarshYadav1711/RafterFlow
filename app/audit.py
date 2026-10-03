"""R10 enquiry JSONL audit logging (separate from notifications.log)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings


class AuditLogError(RuntimeError):
    """Raised when the required R10 audit line cannot be written."""


def write_enquiry_audit(
    *,
    lead_id: str,
    final_status: str,
    tool_calls: list[dict[str, Any]],
    latency_ms: int,
    log_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Append one JSON object for a completed enquiry.

    Policy: business work may already be done; if audit write fails we surface an
    internal error rather than pretending the fully required operation succeeded.
    """
    path = Path(log_path) if log_path is not None else Path(get_settings().audit_log_path)
    record = {
        "lead_id": lead_id,
        "tool_calls": tool_calls,
        "final_status": final_status,
        "latency_ms": latency_ms,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
    except OSError as exc:
        raise AuditLogError(f"Failed to write enquiry audit log: {exc}") from exc
    return record
