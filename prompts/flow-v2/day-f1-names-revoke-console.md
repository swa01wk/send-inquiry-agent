# Flow v2 Day F1 (Fri 13 Nov): chart names, revoke on Reject Lead, console fixes

Read first: @docs/specs/flow-v2-alignment.md (§2 rows FV2–FV4, §3.5, §3.6, §3.9, §4) @docs/testing/flow-v2-test-plan.md (§3, §8) @docs/flow-v2/scenarios.json (S19, S20) @backend/app/agent/case_prompt.md @backend/app/agent/reviewer_prompt.md

## Goal
Everything the applicant and the reviewers read uses the v2 chart's names:
- statuses: Tenant Qualified, Tenant Not Qualified, Lead Approved, Lead Rejected;
- roles: Leasing Admin, Regional Sales Manager, Regional Product Line Manager;
- "Forecasted Sales Data".

Reject Lead revokes the Azure AD invitation made at first approval. The console loses the contact Remove button and the extra confirm on document reject.

## Backend PR (Claude): lands first; use it, don't rebuild it
- `backend/app/workflow/labels.py`: `status_label(case)` (first-level vs final-level `rejected` from `case.decisions`), `role_label(role)`, `STAGE_LABELS` for the status page. `StatusService`, `case_brief`, `api/case_cards.py`, `api/review.py` and the status API read it.
- Templates in `app/notifications/templates/`: chart names; "Forecasted Sales Data" in `sales_data_request`, `sales_data_received`; `first_level_approved` says "Tenant Qualified". Template ids don't change.
- `IdentityService.revoke(invitation_id)` (mock: `revoked_at`; removes the account only if created by that invitation). `Invitation.revoked_at`. Effect `revoke_primary` on final-level `rejected` (policy `identity.revoke_on_lead_rejection: true`). Audit `identity_revoked`.
- Console (`frontend/src/review/`):
  - contact rows have no Remove;
  - document Reject applies with its remarks in one step;
  - role and status labels come from the API's `*_label` fields.
- Frontend label maps (`InquiryStatusPage`, `CaseStatusCard`, `SalesDataUploadCard`) use the API labels.
- Tests: `tests/flow/test_labels.py` (incl. the wording grep), `tests/lifecycle/test_revoke.py`; Vitest for the console and status page; Playwright `e2e/tests/flow-v2/s19-not-qualified.spec.ts`, `s20-qualified.spec.ts` (console half and labels; `expectFlowPath` lands on F2, so these two only check labels and outbox today).
- `docs/spec.md`: F1 row of spec §7.

## Your track (Cursor): agent wording
1. **Case agent** (`case_prompt.md`, `case_tools.py` `_status_summary`):
   - name the stage with the chart label from `get_case_status`;
   - say "Forecasted Sales Data" (never "estimated");
   - after "Tenant Not Qualified": explain the outcome in one or two sentences, name no reviewer, promise no timeline, offer a new inquiry (`after_rejection`).
2. **Reviewer assistant** (`reviewer_prompt.md`): role names "Leasing Admin" and "Regional Sales Manager"; "Forecasted Sales Data".
3. **Intake and assisted prompts** (`system_prompt.md`, assisted prompt): any remaining "Lease Admin" or "Regional Leasing Manager" in replies the user can see → chart names.
4. **Scripts:** `backend/tests/e2e_scripts/flow-v2-s19.json` and `flow-v2-s20.json` (case-agent turns: "why was it rejected?", "where is my inquiry?").
5. **Live eval:** add `flow_v2` scenarios S19 and S20 (test plan §5 checks `explains_outcome_no_reviewer_names_no_promises`, `offers_new_inquiry`, `where_is_it_gives_right_stage`); re-run the `case` group.

## Tests
- `make test`; `make e2e-int ARGS='--grep "S19|S20"'` and the full `make e2e-int` (regression).
- AGENT-LIVE: `GROUP=flow_v2` S19, S20 ×3 at 3/3; `case` within tolerance.

## End-of-day check
- [ ] Leasing Admin rejects at first level → applicant email and status page say "Tenant Not Qualified"; no Azure AD invitation in the outbox (S19).
- [ ] Leasing Admin approves → "Tenant Qualified", invitation sent, no contacts request yet once F2 lands (today it still opens; S20 asserts labels only).
- [ ] RSM rejects at final level → invitation revoked in `/dev` identity state; an existing account (Oasis, `layla.hassan@oasiscoffee.example`) never touched.
- [ ] No "Lead — second review", "Regional Leasing Manager" or "estimated sales" anywhere (`test_labels.py` green).
- [ ] Console: no Remove on contacts; one-step Reject.
- [ ] `docs/STATUS.md` Flow v2 F1 row; tracker V4, V5, V8, V9, V14 → Done; S19, S20 → In review.
