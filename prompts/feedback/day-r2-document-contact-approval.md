# Re-demo Day R2 (Fri 6 Nov): document approval with expiry, contact approval, signatory question

Read first: @docs/specs/demo-feedback.md (§2 rows D5–D8, §3.4, §3.5, §4, §5, §6) @docs/assumptions.md (Demo feedback assumptions: Document expiry, Document approval, Contact approval) @docs/spec.md @backend/app/agent/case_prompt.md @prompts/feedback/day-r1-cr-question-lease-admin.md

## Goal
First-level review becomes an approval process:
- The Lease Admin confirms each document's expiry date, then approves or rejects each document. First-level approval waits until every required document is approved, and a re-upload needs approval again.
- After first-level approval, the contacts request opens with "Are you the authorised signatory?". The Lease Admin then approves or rejects each contact the tenant enters, and RLM or RPLM can't approve the lead until the required contacts are approved.

## Backend PR (Claude): lands first; use it, don't rebuild it

**Documents (spec §3.4)**
- `DocumentDecision` and `Case.document_decisions`, created at submit from the draft's documents (with expiry from `DocumentRef.review`).
- `app/workflow/expiry.py`, `expiry_status(decision, today, policy) -> "expired" | "expiring_soon" | "valid" | "unknown"`. Policy: `document_expiry.expiring_soon_days: 14`.
- First-level events, each with `file_id` and a stale-file guard:
  - `document_expiry_confirmed {doc_type, file_id, expiry_date}`;
  - `document_approved {doc_type, file_id, remarks?}`, refused when the expiry is expired or unknown;
  - `document_rejected {doc_type, file_id, remarks}`.
- `reupload_requested` with no `doc_types` uses the rejected documents.
- `documents_resubmitted` sets the re-uploaded documents back to `pending`.
- `approved_first` blockers: `document_pending:<type>`, `document_rejected:<type>`, `expiry_unconfirmed:<type>`.
- Console document rows (`ReviewCasePage`, test ids `doc-row-<type>`, `doc-approve-<type>`, `doc-reject-<type>`, `doc-expiry-<type>`, `doc-expiry-status-<type>`):
  - viewer link, expiry status chip, editable date, **Approve**, and **Reject** with remarks;
  - an expired document preselects Reject with the remark "This document expired on {date}. Please upload a current one." The Lease Admin still presses the button.
- `CaseBrief.documents` gains `approval`, `expiry` and `expiry_status`; `next_decision_checklist` lists what's pending.
- Fixtures `e2e/fixtures/files/company_expired.pdf` and `brand_soon.pdf`.

**Contacts (spec §3.5)**
- `TenantContact`: `contact_id`, `approval`, `approval_remarks`, `approved_by`, `added_by`.
- Card `signatory_question` (`build_signatory_question_card()` in `app/api/case_cards.py`), with payload `{prompt, yes_label, no_label, answered?}`.
- UI action `signatory_answer {is_signatory: bool}`:
  - **Yes:** writes `authorized_signatory` with `same_as_primary`, approved on entry (`approved_by: "system:verified_primary"`, policy `contacts.applicant_signatory_needs_approval: false`). Note: `[ui_event] signatory_answer yes`.
  - **No:** note `[ui_event] signatory_answer no`.
  - Both refresh the contacts card.
- Lease Admin events in `second_review`:
  - `contact_approved {contact_id}`;
  - `contact_rejected {contact_id, remarks}`, which opens a contacts request for that role (`CaseRequest.roles`);
  - `contact_added {contact}` if time allows (Should), approved on entry.
- `contacts_provided`: new or changed contacts go to `pending`, and unchanged approved ones stay approved. Contacts prefilled from the tenant record are approved on entry.
- `approved` blockers: `contact_not_approved:<role>`.
- Console contact rows (`contact-row-<role>`, `contact-approve-<role>`, `contact-reject-<role>`): Lease Admin acts, RLM read-only.

**Tests in the backend PR**
- `tests/lifecycle/test_document_review.py`, `test_document_expiry.py` (simulated clock) and `test_contact_review.py`. They include stale `file_id`, double approval (two tabs), a wrong role and a wrong region.
- `tests/durability/`: a restart between `document_approved` and its effects.
- Playwright `rd-document-approval`, `rd-expiry` and the backend half of `rd-contact-approval`.

**What the backend PR gives your track** (see `docs/spec.md` §13.1)
- Shared handler: `actions.signatory_answer_result(session, runtime, is_signatory)`, built on `workflow/contacts.apply_signatory_answer(contacts, primary, is_signatory)`. Your `record_signatory_answer` tool calls `apply_signatory_answer` and returns `Command(update={"contacts_draft": …, "signatory_answer": "yes"|"no"})`; `sequential_tool_node` and `events.py` already carry `signatory_answer` back to the session.
- `signatory_answer` is in the agent state (`state["signatory_answer"]`), and `build_contacts_card(..., case=, signatory_answer=)` fills each row's `approval` / `approval_remarks` and the payload's `roles` and `signatory_answer`. `show_contacts_review` already passes them.
- Notes the agent sees: `[ui_event] signatory_answer yes|no`, `signatory_answer no_request`, `signatory_answer_invalid`.
- Frontend types: `ContactRow.approval`, `approval_remarks`; `ContactsPayload.roles`, `signatory_answer`; `SignatoryQuestionPayload` in `contracts.ts`. Add `'signatory_question'` to `CardType` with the card (left out to avoid clashing with your R1 `cr_question` edit).
- Older tests run without per-item approval unless marked `approvals` (`tests/conftest.py`); scripted Playwright stories approve through `approveDocumentsViaApi` / `approveContactsViaApi` (`e2e/support/submit.ts`).
- Test files as built: `tests/lifecycle/test_approval_machine.py` (pure), `test_document_approval.py`, `test_document_expiry.py`, `test_contact_approval.py`, `tests/durability/test_decision_restart.py`; Playwright `rd-document-approval.spec.ts`, `rd-expiry.spec.ts`, `rd-contact-approval.spec.ts` (console half; extend it with the signatory card and the tenant's fix).

## Your track (Cursor): agent and chat
1. **`SignatoryQuestionCard`**: two buttons sending `signatory_answer`, disabled once answered. Add it to `CardSlot` and `contracts.ts`, with Vitest, an `@fe` scenario and a screenshot.
2. **`ContactsCard`**:
   - shows each contact's approval chip ("Waiting for Cenomi", "Approved", "Needs a change" with the remarks);
   - for a contacts request opened by a rejection, shows only the requested roles, with the reviewer's remarks.
3. **Case agent** (`case_prompt.md`, `case_tools.py`):
   - Tool `record_signatory_answer(is_signatory: bool)` calls the same handler as the card.
   - When the contacts request opens, ask one thing first: whether they're the authorised signatory, and point to the card. Explain the role in plain words if they're unsure ("the person who can sign the lease for your company").
   - **Yes:** carry on with the billing contact, and mention the optional roles once.
   - **No:** ask for the signatory's name, email and mobile in one question, then the billing contact.
   - A rejected contact: name the role, paraphrase the remarks, and ask only for that contact.
   - A rejected or expired document: name the document and paraphrase the remarks. For an expired one, say a current version is needed. Ask only for those documents, using today's re-upload card.
   - Never say a document or contact is approved without the matching state in `get_case_status`.
4. **Scripted mode:** scripts for `rd-contact-approval` and the re-upload turns of `rd-document-approval`.
5. **Goldens:** add `rd-contact-approval`, and export its frontend fixture.
6. **Live eval group `signatory`** with the three scenarios in spec §6. Re-run the existing `case` group, which holds the contacts-bundle scenario.

## Tests
- Vitest for both cards; `make e2e-fe`.
- `make e2e-int`: `rd-document-approval`, `rd-expiry` and `rd-contact-approval` pass. T1 and T2 pass with the Lease Admin acting at first level and documents approved before approval.
- AGENT-LIVE: `signatory` ×3 at 3/3; `case` within tolerance.
- E2E-LIVE smoke: the case-chat persona.

## End-of-day check
- [ ] Submit with `company_expired.pdf` and `brand_soon.pdf`. The Lease Admin sees "Expired", with Reject preselected and Approve disabled, and "Expiring soon", which can be approved.
- [ ] The Lease Admin rejects the company profile, then presses **Request re-upload** with nothing selected. The request lists the company profile with the remark, and the applicant's case chat asks only for that file.
- [ ] Re-upload → the row is back to pending → approve both → **Approve first level** is enabled → approve.
- [ ] Contacts request: "Are you the authorised signatory?" → Yes → billing contact → the Lease Admin rejects billing → the tenant fixes it → the Lease Admin approves → RLM **Approve** is enabled.
- [ ] RLM trying a document or contact action gets `not_in_queue` (wrong-role test green).
- [ ] `docs/STATUS.md` Re-demo R2 ✅; `docs/spec.md` updated (spec §7, R2 row); tracker I4, I5, I16, I18 set to Done.
