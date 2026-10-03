# RafterFlow

Bounded AI lead-intake backend for the fictional Summit Roofing Co. (Ideaboat Solutions LLP technical assessment: AI Lead Intake Agent).

**Engineering principle:** LLM interprets language. Deterministic code owns business commitments.

## Current status

**Phase 3 — Agent Orchestration & Conversation Memory** is complete. `POST /enquiries` runs a bounded tool-calling loop with a configurable OpenAI-compatible LLM, then applies deterministic status rules and Australian-English replies. Booking mutation and admin routes remain Phase 4.

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
- **Tool boundary:** Deterministic tools own postcodes, prices, slot facts, policy facts, and the on-call notify side effect. The LLM decides when to call those tools; finalisation never silently executes `check_service_area` / `estimate_price`. If the model stops early, one bounded recovery nudge asks it to call the unresolved tool; if it still refuses, the turn fails safe with no invented quote. Final customer replies are composed in code. Booking mutation is not implemented yet.

## LLM configuration

Set in `.env` (see `.env.example`):

- `LLM_PROVIDER` — label only (optional)
- `LLM_BASE_URL` — OpenAI-compatible base URL (Groq/Ollama/etc.)
- `LLM_API_KEY`
- `LLM_MODEL`

Automated tests inject a scripted LLM and never call the network.

Manual smoke (optional, requires your own key):

```bash
python scripts/seed.py
uvicorn app.main:app --reload
# POST /enquiries with a real configured model
```

## Business rules

All service area, pricing, availability, and policy facts come only from the assessment appendices (transcribed into `data/business_rules.json`). Do not invent business data.
