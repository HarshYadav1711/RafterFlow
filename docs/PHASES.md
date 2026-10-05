# PHASES — RafterFlow implementation plan

## Phase 0 — Context Lock & Foundation

**Status:** COMPLETE

Lock assessment context, project skeleton, configuration, `data/business_rules.json` transcription (Appendices B–E), agent operating docs, and a minimal `GET /health` surface.

## Phase 1 — Persistence & API Contracts

**Status:** COMPLETE

SQLite/SQLAlchemy models, seed script from appendix data, Pydantic request/response/lead schemas, and typed contracts preparing for enquiry/admin routes (routes themselves deferred).

## Phase 2 — Deterministic Business Tools

**Status:** COMPLETE

Pure Python tools for service-area check, pricing (Appendix C worked example), and read-only availability/policy helpers. Booking mutation remains Phase 4; agent orchestration remains Phase 3.

## Phase 3 — Agent Orchestration & Conversation Memory

**Status:** COMPLETE

LLM-backed intake loop that calls tools, extracts only stated fields, continues leads by phone, and returns reply + lead + tool_calls. Booking mutation remains Phase 4.

## Phase 4 — Booking Concurrency, Security & Logging

**Status:** COMPLETE

Atomic inspection booking (`UPDATE ... WHERE status='free'`), admin `X-API-Key` protection for `GET /leads`, and R10 enquiry JSONL audit logging with monotonic latency.

## Phase 5 — Evaluation Runner & Adversarial Hardening

**Status:** COMPLETE

Black-box `python run_eval.py` sends Appendix F messages in order to `POST /enquiries` and writes `eval.md`. Adversarial tests cover tool authority, authoritative input binding, stale quotes, isolation, and booking/admin boundaries; runtime changed only where tests proved defects.

## Phase 6 — Reproducibility, Documentation & Submission

**Status:** COMPLETE for machine deliverables — TIME_LOG hours still require candidate confirmation

Docker Compose packaging, final README, offline verification, live-eval defect fixes, and a real-provider Appendix F `eval.md` from a single clean run are in place. The generated `eval.md` must be kept as produced (including any honest failed-check notes for LLM variance).

## Phase 7 — Loom & Live-Extension Preparation

**Status:** HUMAN ACTION REQUIRED

Short walkthrough video (≤7 min) and readiness for the 40-minute screen-share extension session. Cursor cannot record the Loom.
