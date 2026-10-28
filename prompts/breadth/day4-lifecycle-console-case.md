# Breadth Day 4 (Fri 30 Oct) — Review lifecycle, reviewer console, case assistant (L4 core)

Read first: @docs/DELIVERY-PLAN.md (§A2, §A4, §A5) @docs/specs/l4-outcome-assistance.md (sections 1, 3.1–3.5, 3.9) @docs/specs/m0-modular-core.md (section 6) @docs/spec.md (section 13) @prompts/25-case-assistant.md @prompts/26-second-level-requests.md

## Goal
After submission, a reviewer can act on the case in a console that shows every step and actor, and the applicant answers each request in chat from the emailed link, without redoing intake.

## Already on `main` (#40, #41): use these, don't rebuild them
**Lifecycle and data**
- `app/workflow/machine.py`: `transition()` covers every M0 §6 row, `legal_events` and `approval_blockers`. `app/workflow/service.py`: `apply_event` is the only path that changes a case (it audits `case_transition`, then runs effects). `app/workflow/effects.py`: emails, the Azure AD invite, the automatic contacts request, the Yardi lead.
- `app/workflow/models.py`: `Case`, `CaseRequest` (`kind` reupload | contacts | sales_data, `remarks`, `doc_types`), `TenantContact`, `CONTACT_ROLE_LABELS`.
- `services.cases` (`CaseStore`) and `_case_for(session, runtime)` in `app/agent/actions.py`: a case session's `session.case_id` is the reference.
- `app/workflow/contacts.py`:
  - `write_contacts(current, entries, primary)` → `(contacts, errors)`. Entries are `{role, first_name?, last_name?, email?, contact_number?, same_as_primary?, source?}`; `same_as_primary` is "that's me". Errors are keyed `role.field`.
  - `contacts_blockers(contacts)`.

**Opening a case in chat**
- `POST /api/cases/open {token}` takes a `case` token (the request emails) or a `track` token (the tracking link). It returns the same shape as `POST /api/sessions`: a case-mode session (`session.mode == "case"`, `session.case_id`), an assistant message, a `case_status` card and a card for each open request. `session.contacts_draft` holds the contacts being collected.
- Email links point at `<PUBLIC_BASE_URL>/inquiry/case?t=…`.

**Cards the backend already builds** (`app/api/case_cards.py`, payloads in `app/api/schemas.py`)

| `card_type` | Builder | Payload | Button → UI action |
| --- | --- | --- | --- |
| `case_status` | `build_case_status_card(case)` | `CaseStatusPayload {reference, status, stage, stage_label, owner_role, last_change, open_requests[], outcome?, outcome_remarks?, next_step}` | none |
| `document_upload` (re-upload mode) | `build_reupload_card(draft, request, master, max_mb=)` | `DocumentUploadPayload` with `mode: "reupload"`, `requested_doc_types`, `remarks` | **Resubmit** → `resubmit_documents` |
| `contacts` | `build_contacts_card(contacts, request)` | `ContactsPayload {request_id, remarks, rows[ContactRow], can_submit, blockers[]}` | **Send contacts** → `submit_contacts` |
| `sales_data_upload` | `build_sales_data_card(draft, request, max_mb=)` | `SalesDataPayload {request_id, remarks, uploaded, file_name?, size_bytes?, allowed_extensions, max_mb}` | upload with `doc_type=sales_data` (case sessions only), then **Send** → `submit_sales_data` |

`request_cards(case, draft, master, max_mb=, contacts=)` gives the card for each open request.

**Applicant actions** (`handle_ui_action`): `resubmit_documents`, `submit_contacts` and `submit_sales_data` check their request, then fire the event. Their notes are:
- `[ui_event] documents_resubmitted` / `resubmit_blocked <missing doc types | no_request>`;
- `contacts_submitted` / `contacts_blocked <blockers>`;
- `sales_data_submitted` / `sales_data_blocked <missing_file | no_request>`.

On success they also send the refreshed `case_status` card.

**Console** (`/review`, `/review/cases/:reference`; needs `REVIEWER_CONSOLE=true` and `VITE_REVIEWER_CONSOLE=1`, both already set in `e2e/playwright.config.ts`)
- Mock sign-in, then the queue, then the case page with only the legal actions.
- Test ids you can use from Playwright:
  - `reviewer-sign-in`, `queue-row-<ref>`, `case-stage`;
  - `action-<name>` (e.g. `action-request_reupload`, `action-approve_first`), `approval-blockers`;
  - `requests`, `timeline`.
- `e2e/support/submit.ts`: `submitScriptedInquiry(page, request, 's1-happy-path')` returns the reference, and `reviewerFor(request, reference)` returns the reviewer whose queue holds the case. `e2e/tests/l4-reviewer-console.spec.ts` shows the flow.

## Your track (Cursor): agent and chat
1. **Send case sessions to the case agent** (`backend/app/api/chat.py`). Today a case-mode session still goes through `route_message` and the intake graph. When `session.mode == "case"`:
   - skip `route_message` (and the redirect path);
   - run the case graph, for both messages and the three UI action notes.
   Intake sessions are unchanged.
2. **Case agent:** a second graph from the same factory as `build_graph`, with its own tool list and prompt (e.g. `app/agent/case_graph.py`, `case_tools.py`, `case_prompt.md`), stored on `app.state` next to `graph`.
   - Tools, which only read the case or show cards and never change its status:
     - `get_case_status` → the `case_status` card plus a short text summary for the model (stage, owner role, open requests with remarks);
     - `request_reupload_documents` → `build_reupload_card` for the open re-upload request;
     - `update_contacts(entries)` → `write_contacts(...)` into `session.contacts_draft`; returns the errors to the model;
     - `show_contacts_review` → `build_contacts_card`;
     - `request_sales_data_upload` → the sales-data card;
     - reuse `search_faq`, `suggest_replies` and `request_handoff`.
     Leave `confirm_fields` and `start_follow_on` out for Day 4. Pressing **Send contacts** confirms what the card shows.
   - Prompt per L4 §3.5:
     - outcome framing: stage, who acts next as a role, what the applicant can do now;
     - re-upload: say which documents and paraphrase the remarks;
     - contacts: one bundle question, with "that's me" → `same_as_primary`;
     - sales data;
     - rejection: explain the remarks plus `after_rejection`;
     - first approval: explain the invitation; final approval: explain that the lead goes to the leasing team's system.
     Never promise an outcome or timeline, never name a reviewer, never say something was resubmitted, sent or approved without the matching `[ui_event]`.
   - Scripted mode: add e2e scripts under `backend/tests/e2e_scripts/` for T2.
3. **Chat cards** (frontend):
   - types in `src/types/contracts.ts` for the three payloads above, plus `mode`, `requested_doc_types` and `remarks` on the upload payload;
   - `CaseStatusCard`, `ContactsCard` and `SalesDataUploadCard` in `CardSlot`;
   - `DocumentChecklistCard` in re-upload mode: only the requested types, the reviewer's remarks, and a **Resubmit** button.
4. **Route** `/inquiry/case` reads `t`, calls `POST /api/cases/open`, then shows the chat like a resumed session. On `token_expired` / `token_invalid`, show the same message and tracking-link hint as the verify and status pages.
5. **Router:** `route_message` is never called for case sessions (covered by item 1). Add a unit test.
6. **Story T2 (re-upload loop)**, Playwright `@scripted`, with two browser contexts:
   - reviewer: `/review` → request a Brand Profile re-upload with remarks;
   - applicant: the `reupload_request` email's link (dev outbox) → `/inquiry/case` → re-upload card → upload → **Resubmit** → `case_status` shows first review;
   - reviewer: reload → stage `First review`, timeline has `Documents resubmitted`.

## Tests
- Vitest for the three new cards and the re-upload mode.
- Backend: a case-session chat turn uses the case graph and never calls the router; the case tools write nothing to the case.
- Stories T2 and the console spec green; S1–S3 and S13 still green (`make e2e-int`).
- Live: one `eval_live` pass over a few case turns (outcome framing, re-upload explanation, contacts bundle).

## End-of-day demo check (L4 core)
- [ ] Submit an inquiry → it appears in the right reviewer's queue → request a Brand Profile re-upload → the email link opens the case in chat → the agent explains why → upload → Resubmit → back in first review. No intake question is asked again.
- [ ] Approve first level → Azure AD invitation and the automatic contacts request in the dev inbox → "I'm the signatory; billing is Omar Saleh, omar@…, +966 5…" → contacts card → Send contacts.
- [ ] The case page's audit timeline shows every step with its actor; a reviewer from another queue can't open the case.
- [ ] `docs/STATUS.md` §0 Day 4 ✅; rows 23–26 🟡.
