# AGENTS.md — RafterFlow operating contract

## Source of truth

- The Ideaboat assessment PDF appendices are the single source of truth for business facts.
- Seeded / reference data (`data/business_rules.json` and later DB seeds derived from it) are the only places business knowledge may live in code.
- Do not invent services, prices, postcodes, availability, warranty terms, emergency definitions, lead fields, statuses, or policies.

## Determinism

- LLM interprets language. Deterministic Python owns business commitments (pricing, area check, slot validation, booking, status transitions).
- Missing customer fields stay `null`. Never guess.
- Business arithmetic and booking concurrency live in code, never in the model.
- Use `REFERENCE_NOW` for all business time. Do not use the host system clock for agent decisions.

## Scope discipline

- Implement only the requested phase. Stop when that phase’s acceptance criteria are met.
- No frontend. No speculative infrastructure (LangChain/LangGraph, vector DBs, Redis, Celery, Kafka, K8s, JWT/OAuth, microservices) unless a later phase proves necessity.
- Every abstraction needs a concrete assessment purpose.
- Preserve existing working behaviour. Prefer tests with defect fixes. No unrelated refactors.

## Communication

- Customer-facing replies: Australian English.
- Secrets stay in `.env` (never commit). Use `.env.example` for variable names only.
- When finishing work: list created/modified files and tests run.
