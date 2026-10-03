# RafterFlow

Bounded AI lead-intake backend for the fictional Summit Roofing Co. (Ideaboat Solutions LLP technical assessment: AI Lead Intake Agent).

**Engineering principle:** LLM interprets language. Deterministic code owns business commitments.

## Current status

**Phase 4 — Booking Concurrency, Security & Logging** is complete. Inspection booking uses an atomic `UPDATE ... WHERE status='free'` transition, admin `GET /leads` is protected by `X-API-Key`, and each enquiry writes one R10 JSONL audit line. The eval runner remains Phase 5.

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

Admin (requires `X-API-Key: <ADMIN_API_KEY>`):

- `GET /leads`
- `GET /leads/{lead_id}`
- optional `?status=`

Tests:

```bash
pytest
```

Destructive Appendix baseline reset (tests/evals later): `python scripts/seed.py --reset`

## Assumptions

- **One lead per phone:** For this assessment, `phone` uniquely identifies one continuing lead because R7 requires later messages from the same number to continue that lead. A production CRM might model multiple jobs per customer differently.
- **Nearest free slots:** When a requested inspection slot is unavailable, alternatives consider only existing free Appendix D slots that are not Sunday and not before `REFERENCE_NOW`. They are sorted by absolute temporal distance from the requested datetime; ties prefer the later slot; at most three are returned.
- **Tool boundary:** Deterministic tools own postcodes, prices, slots, policy facts, booking mutation, and notify/audit side effects. The LLM decides when to call tools; finalisation never silently executes principal business tools. Final customer replies are composed in code.
- **Atomic booking:** Concurrent bookers race with a conditional SQL update (`status='free'` → `booked`). Exactly one waiter wins; losers get an unavailable business outcome with alternatives.
- **Logs:** `notifications.log` is only for R5 on-call notify lines. `AUDIT_LOG_PATH` / `enquiry_audit.jsonl` is the separate R10 enquiry audit trail.

## LLM configuration

Set in `.env` (see `.env.example`):

- `LLM_PROVIDER` — label only (optional)
- `LLM_BASE_URL` — OpenAI-compatible base URL (Groq/Ollama/etc.)
- `LLM_API_KEY`
- `LLM_MODEL`
- `ADMIN_API_KEY`
- `NOTIFICATIONS_LOG_PATH`
- `AUDIT_LOG_PATH`

Automated tests inject a scripted LLM and never call the network.

Manual smoke (optional, requires your own key):

```bash
python scripts/seed.py
uvicorn app.main:app --reload
# POST /enquiries with a real configured model
```

## Business rules

All service area, pricing, availability, and policy facts come only from the assessment appendices (transcribed into `data/business_rules.json`). Do not invent business data.
