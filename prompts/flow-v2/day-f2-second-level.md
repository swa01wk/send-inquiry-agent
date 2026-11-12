# Flow v2 Day F2 (Sat 14 Nov): Approve Lead? → contacts → Approve Lead; unit assignment; chart steps in code

Read first: @docs/specs/flow-v2-alignment.md (§2 rows FV1, FV5–FV8, §3.1, §3.7, §3.8, §3.10) @docs/testing/flow-v2-test-plan.md (§3, §4, §5) @docs/flow-v2/scenarios.json (S21–S24) @docs/spec.md ("Second level, flow v2", "Chart steps") @backend/app/agent/case_prompt.md

## Goal
The second level follows the chart:
- The Regional Sales Manager assigns the unit, may ask for Forecasted Sales Data, and decides "Approve Lead?".
- Yes → "Lead Approved". The contacts request opens. The tenant gives the Authorized Signatory and the Billing Contact; nobody approves them one by one. The same RSM then gives the final "Approve Lead" → accounts → Yardi.
- No → Reject Lead → "Lead Rejected", and the invitation is revoked (F1).

Every chart step a case reaches is recorded in code and readable at `GET /api/dev/flow/{id}`.

## Backend (Claude): merged in #92/#93 and #94; use it, don't rebuild it
- **Machine:**
  - `CaseStatus.lead_approved`; events `unit_assigned {mall_id, unit_ref, area_sqm?}` and `lead_approved`; `Case.assigned_unit`.
  - `lead_approval_blockers`: `unit_not_assigned`, `sales_data_pending`, `open_request:<kind>`.
  - In `lead_approved`, the final `approved` is blocked by `missing_contact:<role>` and `open_request:contacts`. There is no reject after Yes.
  - The old second-level rows apply only to pre-flow-v2 cases (`_row_enabled`).
- **Policy:** `lead_approval {enabled, require_unit_assigned}`, `auto_request_contacts_after_first_approval: false`, `contacts.approval_required: false`.
- **Effects:** on `lead_approved`, the `lead_approved` email, prefill of tenant contacts, then a system `contacts_requested`. `send_lead` carries `assigned_unit`.
- **No approval state with approval off (#94):** the brief and the contacts card rows send `approval: null`. `ContactsCard` already hides the chip in that case.
- **Case tools:** `get_case_status` adds "Still needed before the final Approve Lead: Authorized Signatory, Billing Contact." in `lead_approved`. `update_contacts`, `record_signatory_answer` and `show_contacts_review` work there unchanged.
- **Status:** the case label is "Lead Approved". The status page shows it under "Tenant Qualified", with "Add company contacts" in `waiting_on_you`.
- **Proactive (E4):** applicant reminders for open sales data and contacts requests; no stall flag while the tenant owes the contacts.
- **Console:** Assign the unit, Request Forecasted Sales Data, Approve Lead? (Yes / No), and the final Approve Lead (`approve-lead-final`).
- **Chart steps:** `workflow/flow.py`, audit `flow_step`, `GET /api/dev/flow/{id}`, `POST /api/dev/flow/seed {stage: submitted|qualified|lead_approved}`.
- **Playwright:**
  - S19–S24 in `e2e/tests/flow-v2/`; helpers `seedFlowCase`, `expectFlowPath`, `mailForCase`, `tenantSendsSalesData` in `e2e/support/flowV2.ts`.
  - The tenant side still uses stand-ins: S21 sends the sales data through the API, S23 uses the `t1-contacts` script, and S24 uses `rd-contact-approval`.
- **Still on Claude's side:** the AGENT-DET catalogue runner (`tests/flow_v2/test_catalogue.py`) lands with F3.

## Your track (Cursor): case agent, cards, scripts, evals
1. **Case agent in `lead_approved` (`case_prompt.md`; E3 groundwork, full pass on F4):**
   - When the case opens with the contacts request, say the lead was approved ("Lead Approved"). Ask the signatory question first and point to the card. Then ask for the billing contact, and mention the optional roles once.
   - Before saying what's left, call `get_case_status` and use its "Still needed…" line, in plain words.
   - Never mention approving contacts one by one, "waiting for Cenomi to approve this contact", or verifying contacts. After the contacts are sent, say the leasing team will give the final approval. Don't promise an outcome.
   - Remove or reword the prompt lines that assume per-contact approval. For example: "use `get_case_status` before saying a document or contact is approved" should now cover documents only.
2. **`ContactsCard`:**
   - With `approval` null on every row, show no approval chip and no "Waiting for Cenomi". Add a Vitest case for this.
   - Mark the mandatory roles (`row.required`).
   - Show "Still needed: …" from the required rows that have no email. Use the labels "Authorized Signatory" and "Billing Contact".
3. **`SalesDataUploadCard` and the case agent at "Tenant Qualified":** call it "Forecasted Sales Data" everywhere; the upload works in `second_review`. After it's sent, say the RSM will review it. Don't say the lead is approved.
4. **Scripts** in `backend/tests/e2e_scripts/`, same format as `t1-contacts.json`:
   - `flow-v2-s21.json`: the tenant uploads and sends the Forecasted Sales Data from the case chat.
   - `flow-v2-s23.json`: signatory = me plus a billing contact typed in one message, then the review card.
   - `flow-v2-s24.json`: signatory Yes on the card, then billing.
   - `flow-v2-s22.json`: the tenant opens the case after Reject Lead and asks why.

   Then switch the stand-ins in `e2e/tests/flow-v2/s21`–`s24` to the case chat with `e2eCaseScenario=flow-v2-s2x`. Keep the reviewer steps and `expectFlowPath` as they are.
5. **Live eval** (`scripts/eval_live.py`):
   - If the `flow_v2` group from F1 isn't there yet, add it first, with one scenario per catalogue entry, seeded with `POST /api/dev/flow/seed`.
   - S21: `says_forecasted`. S22: `says_lead_rejected`, `no_reason_invented`. S23: `signatory_question_first`, `e3_lists_whats_missing`, `no_per_contact_approval_mentioned`. S24: `handles_yes_no_unsure`.
   - Re-run `signatory` and `case`, which must stay within `EVAL_TOLERANCE`.

## Tests
- `make ci`: Vitest for `ContactsCard` and `SalesDataUploadCard`, plus `tests/agent/test_case_e2e_scripts.py` for the new scripts.
- `make e2e-int ARGS='--grep @flow-v2'`, then the full `make e2e-int`, then `make e2e-demo`.
- AGENT-LIVE: `make eval-live GROUP=flow_v2` for S21–S24, ×3 at 3/3; `signatory` and `case` within tolerance.

## End-of-day check
- [ ] `POST /api/dev/flow/seed {"stage": "qualified"}` → the RSM assigns a unit and asks for Forecasted Sales Data → 73 h on the dev clock → reminder drafted → the tenant uploads in the case chat → **Yes, approve lead** → "Lead Approved" (S21).
- [ ] The case chat asks the signatory question first, then billing. No approval chips or "waiting for approval" anywhere. **Approve Lead** stays disabled with "Billing Contact still needed" until it's given; approve → accounts invited → Yardi payload has `assigned_unit` → `end` in the flow path (S23).
- [ ] "Yes, that's me" copies the primary contact as signatory (S24).
- [ ] **No, reject lead** → "Lead Rejected"; the invitation is revoked; the case agent says "Lead Rejected" and invents no reason (S22).
- [ ] `docs/STATUS.md` F2 row. Tracker: V7, V11 (console) and S21–S24 → Done once the evals pass.
