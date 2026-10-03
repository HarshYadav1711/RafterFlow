# Adversarial review (Phase 5)

Evidence-driven attack notes against RafterFlow’s assessment boundaries.
Not a generic OWASP checklist.

## Method

1. Write a focused failing/passing test for each hypothesis.
2. Change runtime only when a test proves a real defect.
3. Keep the regression test.

## Boundaries

### 1. Unknown / unapproved tools

- **Hypothesis:** Model-emitted tool names outside the whitelist could execute.
- **Test:** `test_unknown_tool_rejected`
- **Outcome:** Rejected with `unknown_or_forbidden_tool`; no execution.
- **Runtime change:** None (already enforced).
- **Residual:** A live model may still *ask* for forbidden tools; code refuses them.

### 2. Skip required area/pricing tools

- **Hypothesis:** Early model stop invents a quote without tools.
- **Test:** `test_skip_pricing_fails_closed_no_invented_quote` (+ Phase 3 finalize tests)
- **Outcome:** Fail-closed after one recovery; no invented quote.
- **Runtime change:** None.

### 3. Pricing / booking after emergency, out_of_area, out_of_scope

- **Hypothesis:** Prior-turn terminal statuses were only enforced via `TurnState` flags, so a later turn could still price or book.
- **Test:** `test_pricing_blocked_after_emergency`, `test_pricing_blocked_after_out_of_area_status`, `test_booking_blocked_after_emergency_status`, `test_booking_blocked_after_out_of_area_and_out_of_scope`
- **Outcome:** Initially failing for lead-status-only paths.
- **Runtime change:** Block `estimate_price` / `book_inspection` (and emergency area) when `lead.status` is terminal, not only when the current turn flag is set.
- **Residual:** Status is the durable gate; there is no separate policy engine.

### 4. Authoritative postcode / price binding

- **Hypothesis:** `check_service_area` trusted model `postcode` args over the persisted lead, allowing an out-of-area customer to be treated as in-area.
- **Test:** `test_service_area_uses_lead_postcode_not_spoofed_args`, `test_pricing_uses_lead_facts_not_model_args`
- **Outcome:** Postcode spoof was a real defect; pricing already used lead fields.
- **Runtime change:** Area checks use only `lead.postcode`. Model tool-call postcode args never decide area; missing lead postcode leaves the decision unresolved. Pricing result records authoritative `inputs` from the lead.
- **Residual:** None for postcode spoofing via tool args — capture must populate the lead first.

### 5. Protected lead fields

- **Hypothesis:** `capture_lead_details` could set status/quotes/urgency/booking/ids.
- **Test:** `test_capture_cannot_set_protected_fields`
- **Outcome:** Pass — only `CAPTURE_FIELDS` are applied.
- **Runtime change:** None (capture arg recording filtered to allowlisted keys only).

### 6. Customer isolation / prompt injection

- **Hypothesis:** Injection or “list_leads” prose could surface other customers or admin secrets.
- **Test:** `test_prompt_variants_gain_no_admin_capability`, existing Phase 3/4 isolation tests
- **Outcome:** No admin tools exposed; no other-customer data in reply/prompt/audit for scripted paths.
- **Runtime change:** None.
- **Residual:** A misbehaving live model could still invent names in prose; structured tools cannot list leads.

### 7. Stale quotes after fact change

- **Hypothesis:** Changing postcode/size after a quote left the old quote authoritative.
- **Test:** `test_postcode_change_invalidates_stale_quote`, `test_size_change_invalidates_stale_quote_until_repriced`
- **Outcome:** Real defect — quotes persisted across material fact changes.
- **Runtime change:** Quote-sensitive capture fields clear `quote_low`/`quote_high` and demote `quoted` → `awaiting_info` (and clear stale `out_of_area` when postcode changes).
- **Residual:** No full CRM versioning; invalidation is field-based, not event-sourced.

### 8. Booking attacks

- **Hypothesis:** Invented slot ids create availability; Sunday/past/booked bypass validation.
- **Test:** `test_invented_slot_id_does_not_create_availability`, `test_past_and_sunday_and_booked_slots_remain_rejected`, Phase 4 concurrency test
- **Outcome:** Pass — no new slots; atomic free→booked unchanged.
- **Runtime change:** None.

### 9. Admin / audit secrets

- **Hypothesis:** Admin API key leaks into enquiry replies, tool traces, or audit JSONL.
- **Test:** `test_admin_key_absent_from_enquiry_surfaces`, Phase 4 admin auth tests
- **Outcome:** Pass for scripted enquiry path; admin routes still require `X-API-Key`.
- **Runtime change:** None.

### 10. Audit failure vs DB commit

- **Hypothesis:** Audit write failure must not leave a committed enquiry.
- **Test:** `test_audit_write_failure_rolls_back_enquiry` (Phase 4)
- **Outcome:** HTTP 500 + session rollback.
- **Runtime change:** None in Phase 5.
- **Residual limitation (honest):** The JSONL filesystem append and the SQLite commit are not one atomic distributed transaction. A catastrophic DB commit failure *after* a successful audit append could leave an audit line for a rolled-back enquiry. No transactional outbox was added at assessment scale.

## Summary of Phase 5 runtime fixes

| Defect | Fix |
|--------|-----|
| Spoofed area postcode args | Area check uses only `lead.postcode`; unresolved if missing |
| Terminal status not durable across turns | Gate price/book on `lead.status` |
| Stale quote after fact edits | Invalidate quotes on quote-sensitive capture changes |
| Opaque pricing authority | Record lead `inputs` on `estimate_price` results |
