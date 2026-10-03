# PHASES — RafterFlow implementation plan

## Phase 0 — Context Lock & Foundation

**Status:** IN PROGRESS

Lock assessment context, project skeleton, configuration, `data/business_rules.json` transcription (Appendices B–E), agent operating docs, and a minimal `GET /health` surface.

## Phase 1 — Persistence & API Contracts

SQLite/SQLAlchemy models, seed script from appendix data, Pydantic request/response/lead schemas, and stub enquiry/admin route contracts without full agent behaviour.

## Phase 2 — Deterministic Business Tools

Pure Python tools for service-area check, pricing (Appendix C worked example), and availability/booking validation against seeded slots.

## Phase 3 — Agent Orchestration & Conversation Memory

LLM-backed intake loop that calls tools, extracts only stated fields, continues leads by phone, and returns reply + lead + tool_calls.

## Phase 4 — Booking Concurrency, Security & Logging

Double-booking safety, admin `X-API-Key` protection, emergency notify mock, JSONL enquiry logging, and guardrail enforcement.

## Phase 5 — Evaluation Runner & Adversarial Hardening

Appendix F runner → `eval.md`; harden honesty/guardrails against out-of-scope, warranty, and injection cases.

## Phase 6 — Reproducibility, Documentation & Submission

Final README, setup commands, time log, known limitations, and submission packaging.

## Phase 7 — Loom & Live-Extension Preparation

Short walkthrough video and readiness for the 40-minute screen-share extension session.
