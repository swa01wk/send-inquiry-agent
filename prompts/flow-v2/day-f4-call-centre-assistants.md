# Flow v2 Day F4 (Tue 17 Nov): call centre contact check; case agent and reviewer assistant

Read first: @docs/specs/flow-v2-alignment.md (§2 rows FV16–FV18, §3.4, §3.10, §3.11) @docs/testing/flow-v2-test-plan.md (§5) @docs/flow-v2/scenarios.json (CC1–CC3, S16, S18, S21, S23, S24) @backend/app/agent/case_prompt.md @backend/app/agent/reviewer_prompt.md

## Goal
- **Call centre:** an existing CR leads to a check of the caller's contact.
  - The contact exists → the executive informs them to raise the inquiry through the tenant platform. The agent gives the words to say and can email a sign-in link (E5).
  - New → fresh capture of the same sections, without documents, then the application link.
- **Case agent:** walks the tenant through the contacts after lead approval (E3).
- **Reviewer assistant:** suggests whether to ask for Forecasted Sales Data, with a reason (E2).
- **Mid-flow questions:** S16 regression on the new section order.

## Backend PR (Claude): lands first; use it, don't rebuild it
- **Call centre:**
  - **as built:** a `contact_check` card in the chat (not a REST endpoint). **Check contact** sends `contact_check {email}` → `IdentityService.has_account`; see `docs/spec.md` §17;
  - outcomes `inform` (status `redirected`, reason `existing_contact`; `inform_tenant` card with `say` and **Email sign-in link**) or `new_contact`;
  - action `send_sign_in_link` + template `sign_in_link`; policy `callcentre.offer_sign_in_link`;
  - the `existing_cr_choice` card and its paths removed;
  - capture without Yardi prefill;
  - flow steps `raise_cc`, `chk_cc`, `db`, `crx`, `pcx`, `inform`, `exec`, `email_link`, `open_form`, `bic`, `update_bi`, `mob`, `succ2`, `upload_submit`, `ref2`.
- **Chat cards:** `ContactCheckCard`, `InformTenantCard` (replace `ExistingCrChoiceCard`).
- **Reviewer assistant tool:** `assess_forecasted_sales_need()` (facts + matching rule), policy `forecasted_sales.suggest_when`. Emits `reviewer_suggestion {kind: sales_data_need, action: request_sales_data}`; **Use** prefills the Ask the applicant form.
- **Notes the assisted agent now sees** (`[ui_event] …`): `contact_existing inform` (give the words to say, point to **Email sign-in link**; collect nothing more), `contact_new fresh_capture` (capture the sections in order), `contact_check_invalid` (quiet), `sign_in_link_sent to=<masked>`, `link_blocked existing_contact`. `verify_cr` on an existing CR returns "Ask the executive for the caller's email and to press Check contact on the card. Collect nothing else until the check is done."
- **Tests:** `tests/api/test_callcentre_flow_v2.py`, `tests/agent/test_reviewer_fsd_suggestion.py`; catalogue runner CC1–CC3, S16; Playwright `tests/flow-v2/cc1`…`cc3`, `s16`, `s18`; `a2-call-centre`, `a2-existing-cr` updated.
- `docs/spec.md`: F4 row of spec §7; §15 intake channels.

## Your track (Cursor): prompts and wording
1. **Assisted prompt (E5):**
   - On `inform`, give the executive one or two sentences to say: "You already have a Tenant Central account — please raise the inquiry from Leasing Opportunities after signing in."
   - Point to **Email sign-in link** on the card (the agent never sends it).
   - Before the check is done, ask only for the caller's email.
   - On a new contact, capture Unit Type and Sales Category, Basic Info and Property Details in the app's order; never ask the executive for documents.
2. **Case prompt (E3):**
   - In `lead_approved`, start with the signatory question.
   - "No" → the signatory's name, email and mobile in one question.
   - Then the billing contact; mention the optional roles once.
   - Say what's still missing before the lead can be approved.
   - Never mention per-contact approval.
   - Handles "not sure" (explain the role) and a contact given before the request opened.
3. **Reviewer prompt (E2):**
   - When the RSM opens a case in `second_review` or asks, call `assess_forecasted_sales_need`.
   - Word one suggestion with its reason ("Suggest asking for forecasted sales data: a new company asking for 200–300 sqm"), or say it isn't needed and why.
   - Never request it yourself.
4. **S16:** after a side question (status, FAQ, a person, Arabic), return to the current section, not the first missing field.
5. **Scripts:** `flow-v2-cc1.json` … `cc3.json`, `flow-v2-s16.json`, `flow-v2-s18.json`.
6. **Live eval:** `flow_v2` CC1–CC3, S16, S18, S21 (`e2_suggestion_has_reason`, `e2_never_sends_request`), S23, S24; re-run `channels`, `case`.

## Tests
- Vitest for the call-centre panel; `make e2e-fe`.
- `make e2e-int ARGS='--grep "CC[1-3]|S16|S18"'`, then the full `make e2e-int`.
- AGENT-LIVE: `flow_v2` all 27 ×3; `channels`, `case` within tolerance.
- E2E-LIVE smoke: CC1.

## End-of-day check
- [ ] Executive enters `1010000000`, then `existing.tenant@zarahome.example` → Inform with words to say → **Email sign-in link** → `sign_in_link` in the outbox; no inquiry (CC1).
- [ ] Same CR, a new email → fresh capture (no Yardi values) → application link → applicant changes their last name → OTP → terms → documents → Submit (CC2, CC3).
- [ ] RSM asks the assistant about forecasted sales → a suggestion with a reason; nothing sent (S21).
- [ ] Case chat after lead approval: signatory first, then billing; missing roles named (S23).
- [ ] Mid-flow FAQ, status, "a person", Arabic → back to the same section (S16).
- [ ] `docs/STATUS.md` F4 row; tracker V3, E2, E3, E5 → Done; S16, S18, CC1–CC3 → In review.
