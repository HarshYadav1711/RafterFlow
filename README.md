# RafterFlow

Bounded AI lead-intake backend for the fictional Summit Roofing Co. (Ideaboat Solutions LLP technical assessment: AI Lead Intake Agent).

**Engineering principle:** LLM interprets language. Deterministic code owns business commitments.

## Current status

**Phase 2 — Deterministic Business Tools** is complete. Seeded SQLAlchemy data backs pure Python tools for service-area checks, Appendix C pricing, read-only availability helpers, policy lookup, and `notify_on_call`. Enquiry routes, LLM orchestration, and booking mutation are not implemented yet.

## Development setup (provisional)

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
python scripts/seed.py
uvicorn app.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

Tests:

```bash
pytest
```

Destructive Appendix baseline reset (tests/evals later): `python scripts/seed.py --reset`

## Assumptions

- **One lead per phone:** For this assessment, `phone` uniquely identifies one continuing lead because R7 requires later messages from the same number to continue that lead. A production CRM might model multiple jobs per customer differently.
- **Nearest free slots:** When a requested inspection slot is unavailable, alternatives consider only existing free Appendix D slots that are not Sunday and not before `REFERENCE_NOW`. They are sorted by absolute temporal distance from the requested datetime; ties prefer the later slot; at most three are returned.
- **Tool boundary:** Deterministic tools own postcodes, prices, slot facts, policy facts, and the on-call notify side effect. They do not interpret natural language, classify emergencies/out-of-scope services, compose customer replies, or book slots.

## Business rules

All service area, pricing, availability, and policy facts come only from the assessment appendices (transcribed into `data/business_rules.json`). Do not invent business data.
