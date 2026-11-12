# Flow v2 Day F1 (Fri 13 Nov): chart names, revoke on Reject Lead, console fixes

Read first: @docs/specs/flow-v2-alignment.md (§2 rows FV2–FV4, §3.5, §3.6, §3.9, §4) @docs/testing/flow-v2-test-plan.md (§3, §5, §8) @docs/flow-v2/scenarios.json (S19, S20) @backend/app/workflow/labels.py @backend/app/agent/case_prompt.md @backend/app/agent/reviewer_prompt.md

## Goal
Everything the applicant and the reviewers read uses the v2 chart's names:
- statuses: Tenant Qualified, Tenant Not Qualified, Lead Approved, Lead Rejected;
- roles: Leasing Admin, Regional Sales Manager, Regional Product Line Manager;
- "Forecasted Sales Data".

Reject Lead revokes the Azure AD invitation made at first approval. The console has no contact Remove button, and document Reject is one step (P4, settled 12 Nov).

## Backend (Claude): merged in #91 (F2 is on `main` too, #92/#93); use it, don't rebuild it
- `backend/app/workflow/labels.py`: `STAGE_LABELS`, `status_label(case)` (first-level vs final-level `rejected` from `case.decisions`), `rejection_label`, `role_label`, `TENANT_NOT_QUALIFIED`, `LEAD_REJECTED`, `FORECASTED_SALES_DATA`.
  - `StatusService`, `case_brief`, `api/case_cards.py`, `api/review.py` and the status API read these.
  - `case_tools._status_summary` already says e.g. "Outcome: rejected (Tenant Not Qualified)."
- Templates use the chart names. `inquiry_rejected` carries `Outcome: $outcome_label` and a case link (`$case_url`); `first_level_approved` says "Tenant Qualified" and carries a case link.
- Revoke: `IdentityService.revoke`, `Invitation.revoked_at`, effect on a final-level `rejected` (`identity.revoke_on_lead_rejection`), audit `identity_revoked`. An account that existed before is never touched.
- Console: no Remove on contacts; one-step document Reject; labels from the API.
- Tests: `tests/flow/test_labels.py` (incl. the wording grep), `tests/lifecycle/test_revoke.py`.
- Playwright:
  - `e2e/tests/flow-v2/s19-not-qualified.spec.ts` and `s20-qualified.spec.ts` cover the console, labels and outbox.
  - S20 also checks `expectFlowPath` and that no contacts request opens.
  - Neither talks to the case agent yet; that's item 4 below.
- **Not there yet:** the `flow_v2` eval group in `scripts/eval_live.py`. You create it in item 5.

## Your track (Cursor): agent wording, scripts, evals
1. **Case agent** (`case_prompt.md`):
   - Name the stage with the chart label from `get_case_status`: "Tenant Qualified", "Tenant Not Qualified", "Lead Approved", "Lead Rejected".
   - Say "Forecasted Sales Data", never "estimated".
   - After "Tenant Not Qualified" or "Lead Rejected":
     - explain the outcome in one or two sentences from the reviewer's remarks;
     - name no reviewer, invent no reason, promise no timeline;
     - offer a new inquiry, using the `After rejection` line from `get_case_status`.
   - Never offer to reopen the case.
2. **Reviewer assistant** (`reviewer_prompt.md`): say "Leasing Admin", "Regional Sales Manager" / "Regional Product Line Manager" and "Forecasted Sales Data". Name the stage with the chart label.
3. **Intake and assisted prompts** (`system_prompt.md`, the assisted prompt): change any "Lease Admin", "Regional Leasing Manager", "RLM" or "estimated sales" a user can see to the chart names. `test_labels.py` greps templates and labels only, so check the prompts by hand.
4. **Scripts and Playwright:**
   - `backend/tests/e2e_scripts/flow-v2-s19.json`: the tenant opens the case from the rejection email and asks "Why was it rejected?". The reply says "Tenant Not Qualified" and offers a new inquiry.
   - `flow-v2-s20.json`: "Where is my inquiry?" → "Tenant Qualified", and the Regional Sales Manager reviews next.
   - In `s19-not-qualified.spec.ts` and `s20-qualified.spec.ts`, after the existing reviewer steps, open the `$case_url` link from the email with `e2eCaseScenario=flow-v2-s1x` and assert the reply's wording. Keep the existing assertions.
5. **Live eval group `flow_v2`** (`scripts/eval_live.py`, test plan §5):
   - Add the group and wire it into `GROUP=` like `case` and `signatory`.
   - **S19:** `_case_setup([{"action": "reject", "reason_category": …, "remarks": …}])` (first level), then "Why was it rejected?". Checks:
     - `says_tenant_not_qualified`;
     - `explains_outcome_no_reviewer_names_no_promises`;
     - `offers_new_inquiry`;
     - `does_not_offer_reopen`.
   - **S20:** `_case_setup([{"action": "approve_first"}])`, then "Where is my inquiry?". Checks:
     - `where_is_it_gives_right_stage` ("Tenant Qualified");
     - `names_regional_sales_manager_or_leasing_team`;
     - `no_contacts_request_mentioned` (contacts come after Approve Lead).
   - The F2 scenarios (S21–S24) join this group on the F2 Cursor day.
   - #94 already moved the `case` and `signatory` setups that need contacts to `LEAD_APPROVED` (approve first → assign unit → approve lead). Re-run both groups.

## Tests
- `make ci`, which includes `tests/agent/test_case_e2e_scripts.py` for the new scripts.
- `make e2e-int ARGS='--grep "S19|S20"'`, then the full `make e2e-int`.
- AGENT-LIVE: `make eval-live GROUP=flow_v2` for S19 and S20, ×3 at 3/3. `case` and `signatory` stay within `EVAL_TOLERANCE` (`docs/eval-notes.md`).

## End-of-day check
- [ ] Leasing Admin rejects at first level → email, status page and case chat all say "Tenant Not Qualified"; no Azure AD invitation in the outbox (S19).
- [ ] Leasing Admin approves → "Tenant Qualified", invitation sent, no contacts request; the case chat names the stage and who reviews next (S20).
- [ ] RSM rejects at final level → invitation revoked in `/dev` identity state; an existing account (Oasis, `layla.hassan@oasiscoffee.example`) never touched.
- [ ] No "Lead — second review", "Regional Leasing Manager", "Lease Admin" or "estimated sales" in any reply, prompt, template or label.
- [ ] `docs/STATUS.md` Flow v2 F1 row. Tracker: V4, V8 → Done once the evals pass; S19, S20 stay In review until then.
