# Breadth Day 3 (Thu 29 Oct) — Routing, handoff, Arabic, follow-on (L3 at demo depth)

Read first: @docs/DELIVERY-PLAN.md (§A2, §A5) @docs/specs/l3-reliable-intake.md (sections 3.5, 3.6, 3.10, 3.11, 3.13) @prompts/21-routing-handoff.md @prompts/21b-arabic-follow-on-duplicates.md @backend/app/agent/system_prompt.md

## Goal
Messages reach the right handler, a person is always reachable, Arabic users get the same safety nets, and a second mall takes two messages.

## Backend track (Claude's PR — don't build these)
- `CallCentreService.create_case` mock (cases show in the dev inbox); `request_handoff` action; `handoff` card `{phone, email, hours, short_ref}` from `CALL_CENTRE_*` config; note `handoff_created <reason>`.
- `normalise_digits()` for Arabic-Indic and Eastern Arabic-Indic digits, applied before every numeric rule and in `contact_infer`.
- Arabic doubt phrases in `confirm_policy.py`, covering every derived field.
- Follow-on backend: `start_follow_on(mall_id?)` tool (only after submit) resets the session onto a new inquiry with `follow_on_of`, copies company, brand, unit type, sales category and contact as `verified` unconfirmed in one confirm card ("Same details as <ref>"), carries verification within `follow_on_reuse_hours`, and references the two profiles. Note `follow_on_started from=<ref>`.
- **L1/L3 core — form mode (L3 §3.14), backend and UI:** two model failures in a turn (or `FORM_MODE=true`; add `llm` to `MOCK_FAULTS`) switch the session to form mode; the `form_mode` card ("Our assistant isn't available…", **Ask us to call you**); the draft panel's fields editable through `edit_field`; UI actions apply without an agent turn and the phase decides the next card; the next successful model call returns to chat. Audit events `form_mode_entered` / `form_mode_left`. Story S13 (scripted).
- **L3 core — provenance (capability 2, L3 §3.9):** `update_draft` entries with `source: derived` accept `evidence` (≤ 80 chars of the user's words); the confirm card shows "from: '…'"; stored in the `field_written` audit event.
- Playwright `@scripted` stories **S2** (resume from the inbox link in a new browser context) and **S3** (`X-Mock-Faults: submit:timeout:1`: no success claim until the reference arrives).

## Your track (Cursor)
1. **Router.** One function `route_message(text, session) -> Intent`, called in the chat endpoint before the graph (step 16 later moves it into the supervisor):
   - rules first: a `GEO-…` reference, an explicit request for a person, an existing-CR match;
   - otherwise a structured-output classifier (`ROUTER_MODEL`) returning `{intent, confidence}`; below `ROUTER_MIN_CONFIDENCE` or mid-intake → `inquiry_intake`;
   - intents and handling per L3 §3.5. `general_inquiry` and `existing_tenant_new_space` get a short redirect reply from a small prompt with no write tools.
2. **Handoff in the chat:** `HandoffCard` in `CardSlot`; triggers: the `human_help` intent and the guard's second failed retry (others in Sprint 1).
3. **Follow-on in the UI:** a "New inquiry" divider when `follow_on_started` arrives; prompt: after a submission, offer another mall; ask only for the new mall and space.
4. **Guard capture heuristics:** Arabic business words (كشك، متجر، مطعم، مقهى، مول).
5. **Evidence in the prompt:** every derived value is written with `evidence` quoting the user's words (the confirm card shows it; Claude's PR adds the field).
6. `tests/routing/fixtures.jsonl`: at least 30 labelled messages to start (Arabic and mixed included); Sprint 1 grows it to 60.

## Tests
- Routing fixtures with a scripted classifier (≥ 90% for breadth).
- Arabic unit tests from the backend PR; follow-on scripted scenario.
- Stories S1–S3 green.
- Live: `scripts/eval_live.py` once (intake + a few routing and Arabic turns); one `@live` smoke run.

## End-of-day demo check (every L3 capability at demo depth)
- [ ] "Can I talk to someone?" → handoff card; the case is in the dev inbox; the chat continues.
- [ ] "We already lease two stores" → existing-tenant redirect.
- [ ] Arabic message with ٠٥٠١٢٣٤٥٦٧ is saved as a mobile; «مو متأكد من الفئة» keeps the category unconfirmed.
- [ ] After submitting for one mall, "also Mall B" → submitted in two typed messages.
- [ ] A derived unit type shows "from: 'specialty coffee kiosk'" on the confirm card.
- [ ] With `X-Mock-Faults: llm:unavailable`, the user finishes the inquiry in form mode and submits; when the model returns, the chat carries on.
- [ ] `docs/STATUS.md` §0 Day 3 ✅; rows 21, 21b 🟡.
