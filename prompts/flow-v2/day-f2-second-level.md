# Flow v2 Day F2 (Sat 14 Nov): Approve Lead? → contacts → Approve Lead; unit assignment; chart steps in code

Read first: @docs/specs/flow-v2-alignment.md (§2 rows FV1, FV5–FV8, §3.1, §3.7, §3.8, §3.10) @docs/testing/flow-v2-test-plan.md (§3, §4, §6) @docs/flow-v2/scenarios.json (S21–S24) @backend/app/agent/case_prompt.md @prompts/feedback/day-r2-document-contact-approval.md

## Goal
The second level follows the chart:
- The Regional Sales Manager verifies and assigns the unit, optionally asks for Forecasted Sales Data, and decides "Approve Lead?".
- Yes opens the contacts request. The tenant gives the Authorized Signatory and Billing Contact, which are not approved one by one, and the same RSM gives the final "Approve Lead" → accounts → Yardi.
- No → Reject Lead (with revoke, F1).

Every chart step a case reaches is recorded in code and readable at `GET /api/dev/flow/{id}`.

## Backend PR (Claude): lands first; use it, don't rebuild it
- **Chart steps:** `backend/app/workflow/flow.py` (`FlowNode`, `IGNORED_NODES`, `record_flow_step`); audit type `flow_step` (allowlist); emission for every lifecycle node in spec §3.1 (intake nodes land on F3, call centre on F4); `GET /api/dev/flow/{id}`; `POST /api/dev/flow/seed {stage, unit_type?, malls?, applicant?}` applying real events.
- **Machine** (`workflow/machine.py`, `models.py`):
  - `CaseStatus.LEAD_APPROVED`;
  - events `unit_assigned`, `lead_approved`; the rows in spec §3.7, with old rows removed;
  - blockers `unit_not_assigned`, `sales_data_pending`, `missing_contact:<role>`;
  - `Case.assigned_unit {mall_id, unit_ref, area_sqm}`.
- **Policy:** `auto_request_contacts_after_first_approval: false`, `contacts.approval_required: false`, `lead_approval.require_unit_assigned: true`.
- **Effects:**
  - on `lead_approved`: `prefill_tenant_contacts`, `auto_contacts_request`, `lead_approved_email` (new template);
  - `send_lead` adds `assigned_unit`;
  - `approved_first` no longer opens contacts;
  - legacy cases with an open contacts request still approve (`legacy_contacts_open`).
- **Proactive (E4):** reminders for open contacts in `lead_approved` and sales data in `second_review`; no stall flag while the tenant owes contacts.
- **Console** (`ReviewCasePage`, `ActionsPanel`), final reviewer:
  - in `second_review`: **Assign unit** (test ids `assign-unit-*`), **Request Forecasted Sales Data**, **Approve Lead?** with **Yes, approve lead** / **No, reject lead** (`approve-lead-yes`, `approve-lead-no`);
  - in `lead_approved`: contacts read-only, mandatory roles marked, missing ones listed, **Approve Lead** (`approve-lead-final`) disabled until both are in.
- **Case agent tools** (deterministic part):
  - `get_case_status` returns the chart label and, in `lead_approved`, `missing_contacts`;
  - `update_contacts` and `record_signatory_answer` work in `lead_approved`;
  - `build_contacts_card` drops the per-contact approval chips when `approval_required: false`.
- `demo_seed.py` cases follow the new flow.
- **Tests:**
  - `tests/lifecycle/test_lead_approval.py`, `test_lead_contacts.py`, `test_unit_assignment.py`;
  - `tests/domain/test_payload.py`;
  - `tests/proactive/test_flow_v2_reminders.py`;
  - `tests/flow/test_flow_steps.py`;
  - catalogue runner `tests/flow_v2/test_catalogue.py` with S18–S24;
  - Playwright `e2e/support/{scenarios,flow,steps}.ts`, `e2e/pages/console.ts`, `tests/flow-v2/s21`…`s24`, and S19/S20 now with `expectFlowPath`;
  - existing `t1-lifecycle-to-yardi`, `a1-approvals`, `l4-reviewer-console`, `demo.spec.ts` updated (spec §5.3).
- `docs/spec.md`: F2 row of spec §7; §13 lifecycle states and events.

## Your track (Cursor): case agent and cards
1. **Case agent in `lead_approved` (E3, groundwork; full prompt work on F4):**
   - When the contacts request opens, ask the signatory question first (point to the card), then the billing contact, then mention the optional roles once.
   - Say what's still missing before Approve Lead, in plain words.
   - Never mention per-contact approval or "waiting for Cenomi to approve this contact".
2. **`ContactsCard`:** hide the approval chips when the payload has no `approval`; mark the mandatory roles; show "Still needed: …" from `missing_contacts`.
3. **`SalesDataUploadCard` and the case agent:** "Forecasted Sales Data" (the F1 wording) and the upload in `second_review`.
4. **Scripts:** `flow-v2-s21.json` … `flow-v2-s24.json` (case-agent turns from the catalogue steps).
5. **Goldens:** none (the parity recorder is intake-only).
6. **Live eval:** `flow_v2` S21 (`says_forecasted`), S22, S23 (`e3_lists_whats_missing`, `signatory_question_first`, `no_per_contact_approval_mentioned`), S24 (`handles_yes_no_unsure`); re-run `signatory` and `case`.

## Tests
- Vitest for `ContactsCard`, the console states; `make e2e-fe`.
- `make e2e-int ARGS='--grep "S1[89]|S2[0-4]"'`, then the full `make e2e-int`.
- AGENT-LIVE: `flow_v2` S21–S24 ×3 at 3/3; `signatory`, `case` within tolerance.

## End-of-day check
- [ ] `POST /api/dev/flow/seed {"stage": "qualified"}` → RSM assigns a unit, asks for Forecasted Sales Data → 73 h on the dev clock → reminder drafted → tenant uploads in the case chat → **Yes, approve lead** → status "Lead Approved" (S21).
- [ ] Contacts: the signatory question first; **Approve Lead** disabled with "Billing Contact still needed"; enabled once given; approve → accounts invited → Yardi payload has `assigned_unit` → status "Approved" → `end` in the flow path (S23).
- [ ] "Yes, that's me" copies the primary contact as signatory (S24).
- [ ] **No, reject lead** → "Lead Rejected", invitation revoked (S22).
- [ ] `GET /api/dev/flow/<reference>` lists the chart steps in order for each of the above.
- [ ] `docs/STATUS.md` F2 row; tracker V6, V7, V11 (console), E4 → Done; S21–S24 → In review.
