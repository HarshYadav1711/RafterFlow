# PROJECT_CONTEXT — Ideaboat AI Lead Intake Agent

Compact source summary for coding agents. Do not invent requirements beyond the assessment PDF.

## Scenario

Summit Roofing Co. is a fictional residential roofing business in Brisbane, Australia. It receives 40–60 enquiries a week via website form and WhatsApp. Build the backend for an AI intake agent that extracts structured leads, checks service area, gives indicative prices, books free inspections into real slots, detects emergencies, and never invents prices, services, slots, or warranty terms.

## Fixed reference time

`REFERENCE_NOW=2026-10-11T10:00:00+10:00` (Sunday 11 October 2026, 10:00 AEST / Australia/Brisbane, UTC+10). Business logic must not use the system clock.

## Required capabilities (R1–R10)

| ID | Capability | Detail |
|----|------------|--------|
| R1 | Enquiry endpoint | `POST /enquiries` → reply text, lead record, tool calls |
| R2 | Structured extraction | Appendix A fields; unstated → `null`; missing essentials → ask + `awaiting_info` |
| R3 | Service area | Tool vs Appendix B; out of area → polite decline, no price, `out_of_area` |
| R4 | Indicative price | Tool vs Appendix C; arithmetic in code; AUD incl. GST range; estimate wording; defaults when pitch/storeys unknown |
| R5 | Emergency | Appendix E definition → `emergency`, `notify_on_call`, 24/7 number, no quote/booking |
| R6 | Inspection booking | Appendix D slots; validate exists/free/not past/not Sunday in code; offer up to 3 nearest free; exactly one winner on concurrent double-book |
| R7 | Conversation memory | Same phone continues same lead/conversation |
| R8 | Admin API | `GET /leads`, `GET /leads/{lead_id}` with `X-API-Key`; else 401 |
| R9 | Guardrails | No fixed-price promise; warranty only as Appendix E; no out-of-scope services; resist embedded instructions; no other-customer data |
| R10 | Logging | One JSONL line per enquiry: lead id, tool calls+args, final status, latency ms |

## Technical constraints

- Secrets in `.env` (not committed); commit `.env.example`
- Run in ≤3 commands or `docker compose up`; document exact commands
- Configurable LLM provider/model if paid API used
- Australian English; price format like `$8,100 to $10,800 (incl. GST)`
- Seed DB from appendix data via script

## Required deliverables

1. GitHub repository  
2. README (setup, architecture, decisions, limitations, one-more-week)  
3. Eval runner for Appendix F → `eval.md`  
4. Generated `eval.md` with honest notes on wrong results  
5. Automated tests: pricing (worked example), booking validation, double-booking, postcode  
6. Loom ≤7 minutes  
7. Time log  

## Evaluation weights

| Area | Weight |
|------|--------|
| Correctness (R1–R8) | 25% |
| Reliability / honesty of agent | 20% |
| Tool design | 15% |
| Code quality and tests | 15% |
| Security | 10% |
| Documentation and self-assessment | 15% |

## Appendix A — Lead fields and statuses

**Inbound:** `channel` (`whatsapp` \| `web_form`), `from_phone`, `from_name` (nullable), `message`, `received_at`.

**Response:** `reply`, `lead`, `tool_calls[{tool, args, result}]`.

**Lead fields:** `lead_id`, `phone`, `name`, `channel`, `service_type`, `roof_material`, `storeys`, `steep_pitch`, `size_m2`, `gutter_length_m`, `postcode`, `suburb`, `urgency`, `status`, `quote_low`, `quote_high`, `booked_slot_id`, `created_at`, `updated_at`.

**`service_type`:** `roof_restoration` \| `roof_replacement` \| `gutter_replacement` \| `leak_repair` \| `inspection_only` \| `other` \| `null`

**`roof_material`:** `tile` \| `metal` \| `null`

**`urgency`:** `emergency` \| `standard`

**`status`:** `new` \| `awaiting_info` \| `quoted` \| `inspection_booked` \| `emergency` \| `out_of_area` \| `out_of_scope`

## Key business-rule invariants

- Service area: exactly the 15 Brisbane postcodes in Appendix B; all others out of area.
- Pricing: rates and rules in Appendix C only; multipliers 1.15 / 1.10 / combined 1.265; defaults storeys=1, steep_pitch=false; nearest $50 half-up; $1,500 minimum for restoration/replacement/gutters; restoration requires `roof_material`.
- Availability: only listed slots for 12–17 Oct 2026; no Sunday slots; slot id `YYYY-MM-DDTHH:MM` Brisbane time.
- Policies (Appendix E): office hours; emergency `0491 570 110`; exact emergency definition; offered / not offered services; quote, warranty (7y restorations / 10y replacements), insurance policies as stated.
- Engineering principle: LLM interprets language; deterministic code owns business commitments.

## Appendix F — Evaluation message categories

Send in order with given phones; `channel: whatsapp`; `received_at` = reference time unless stated. 7a/7b share a phone.

| # | Category (intent) |
|---|-------------------|
| 1 | In-area restoration quote with full details |
| 2 | Emergency (active water ingress) |
| 3 | Gutter replacement missing length → awaiting info |
| 4 | Replacement with multipliers (storeys + steep) |
| 5 | Out-of-scope service (solar) |
| 6 | Out-of-area postcode |
| 7a/7b | Multi-turn memory (metal restoration then size/postcode) |
| 8 | Small job / minimum charge edge |
| 9 | Invalid invalid/past Sunday slot |
| 10 | Request already-booked slot |
| 11 | Fixed price + exaggerated warranty pressure |
| 12 | Prompt-injection / data exfiltration attempt |

All listed phone numbers are from the Australian fictional-use range.
