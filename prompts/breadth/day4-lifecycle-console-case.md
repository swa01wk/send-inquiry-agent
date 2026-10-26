# Breadth Day 4 (Fri 30 Oct) — Review lifecycle, reviewer console, case assistant (L4 core)

Read first: @docs/DELIVERY-PLAN.md (§A2, §A4, §A5) @docs/specs/l4-outcome-assistance.md (sections 1, 3.1–3.5, 3.9) @docs/specs/m0-modular-core.md (section 6) @prompts/23-lifecycle-core.md @prompts/24-reviewer-console.md @prompts/25-case-assistant.md @prompts/26-second-level-requests.md

## Goal
After submission, a reviewer can act on the case in a console that shows every step and actor, and the applicant answers each request in chat from the emailed link, without redoing intake.

## Claude's PRs (backend + console UI — don't build these)
**Backend**
- `app/workflow/machine.py`: the pure `transition()` with every row of M0 §6 and the reviewer-queue actor check; every transition, legal or not, recorded in the audit log.
- Case data (L4 §3.1) on the inquiry, kept in the snapshot store; `DocType.sales_data`.
- Policy: `review_routing`, `second_level_contacts`, `rejection_categories`, `after_rejection`, `require_contacts_before_approval`, `auto_request_contacts_after_first_approval`.
- Mocks: `ReviewerDirectory` (`data/mock_world/reviewers.json`, including `customer_care` and `guest_service` staff for Day 5), `IdentityService` (invite with the tenant role it assigns, accept link in the outbox, `has_account`), `YardiService` (`data/mock_world/yardi.json`).
- Effects inline after each transition, keyed by `(inquiry_id, event_seq, effect)`; templates for every row of L4 §3.4; `submitted` routes to a queue; `approved_first` invites unless the contact has an account and opens a contacts request automatically.
- Review API (L4 §3.3) with `X-Reviewer-Id`, only when `REVIEWER_CONSOLE=true` and `INTEGRATIONS=mock`.
- `domain/case_brief.py` (deterministic brief, L4 §3.6).
- `case` token purpose; `/inquiry/case?t=` resume in case mode (also from `track` tokens).
- Applicant UI actions `resubmit_documents`, `submit_contacts`, `submit_sales_data`; notes per L4 §4.
- Lifecycle tests: every path and the authority checks.

**Console UI** (`/review`, `/review/cases/:id`; `VITE_REVIEWER_CONSOLE=1`)
- Mock sign-in (pick a reviewer); queue with stage, waiting on, age.
- Case page: the brief with source badges and evidence; documents; **audit timeline** (who did what, when — applicant, staff, reviewer, system, agent); an actions panel with only the legal actions (re-upload with document picker and remarks, reject with remarks and category, approve first level, request contacts, request sales data, withdraw, approve).
- Vitest for the pages; a Playwright check that only legal actions show per status.

## Your track (Cursor) — agent and chat
1. **Case agent** (`app/agents/case/` or a second graph from the same factory with its own tools and prompt):
   - tools: `get_case_status`, `request_reupload_documents`, `update_contacts`, `confirm_fields`, `show_contacts_review`, `request_sales_data_upload`, `search_faq`, `suggest_replies`, `request_handoff`;
   - prompt per L4 §3.5: outcome framing (stage, owner as a role, next step), re-upload explanation from the remarks, one contacts bundle with "that's me" reuse, sales data, rejection and approval explanations; never promise, never name reviewers;
   - the chat endpoint uses the case agent when the inquiry isn't a draft.
2. **Chat cards:** `case_status`, `contacts`, `sales_data_upload`; `document_upload` gains re-upload mode with `requested_doc_types`.
3. **Route** `/inquiry/case`.
4. Playwright `@scripted` story **T2** (re-upload loop) with an applicant and a reviewer browser context.

## Tests
- Vitest for the new chat cards.
- Story T2 green; S1–S3 and S13 still green.

## End-of-day demo check (L4 core)
- [ ] Submit an inquiry → it appears in the right reviewer's queue → request a Brand Profile re-upload → the email link opens the case in chat → the agent explains why → upload → Resubmit → back in first review. No intake question is asked again.
- [ ] Approve first level → Azure AD invitation (with the role) and the automatic contacts request in the dev inbox → "I'm the signatory; billing is Omar Saleh, omar@…, +966 5…" → contacts sent.
- [ ] The case page's audit timeline shows every step with its actor; a reviewer from another queue can't act on the case.
- [ ] `docs/STATUS.md` §0 Day 4 ✅; rows 23–26 🟡.
