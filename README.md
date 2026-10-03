# RafterFlow

Bounded AI lead-intake backend for the fictional Summit Roofing Co. (Ideaboat Solutions LLP technical assessment: AI Lead Intake Agent).

**Engineering principle:** LLM interprets language. Deterministic code owns business commitments.

## Current status

**Phase 0 — Context Lock & Foundation** is in progress. The repository has project scaffolding, environment configuration, assessment source-of-truth data under `data/business_rules.json`, agent operating docs, and a minimal `GET /health` endpoint. Enquiry handling, persistence, tools, and the LLM agent are not implemented yet.

## Development setup (provisional)

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
uvicorn app.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

Tests:

```bash
pytest
```

## Business rules

All service area, pricing, availability, and policy facts come only from the assessment appendices (transcribed into `data/business_rules.json`). Do not invent business data.
