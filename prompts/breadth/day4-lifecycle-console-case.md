# Breadth Day 4 (Fri 30 Oct) — Review lifecycle, reviewer console, case assistant (L4 part 1)

Read first: @docs/DELIVERY-PLAN.md (§A2, §A5) @docs/specs/l4-outcome-assistance.md (sections 1, 3.1–3.5, 3.9) @docs/specs/m0-modular-core.md (section 6) @prompts/23-lifecycle-core.md @prompts/24-reviewer-console.md @prompts/25-case-assistant.md @prompts/26-second-level-requests.md

## Goal
After submission, a reviewer can act on the case, and the applicant answers each request in chat from the emailed link, without redoing intake.

## Backend track (Claude's PR — don't build these)
- `app/workflow/machine.py`: the pure `transition()` with every row of M0 §6 and the reviewer-queue actor check.
- Case data (L4 §3.1) on the inquiry, held in the in-memory store; `DocType.sales_data`.
- Policy: `review_routing`, `second_level_contacts`, `rejection_categories`, `after_rejection`, `require_contacts_before_approval`.
- Mocks: `ReviewerDirectory` (`data/mock_world/reviewers.json`), `IdentityService` (Azure AD, accept link in the outbox), `YardiService` (`data/mock_world/yardi.json`).
- Effects run inline after each transition, keyed by `(inquiry_id, event_seq, effect)`; templates for every row of L4 §3.4; `submitted` routes the case to a queue.
- Review API (L4 §3.3) with `X-Reviewer-Id`, only when `REVIEWER_CONSOLE=true` and `INTEGRATIONS=mock`.
- `domain/case_brief.py` (deterministic brief, L4 §3.6).
- `case` token purpose; `/inquiry/case?t=` resume in case mode (also from `track` tokens).
- Applicant UI actions `resubmit_documents`, `submit_contacts`, `submit_sales_data`; notes per L4 §4.
- Lifecycle unit tests: every path and the authority checks.

## Your track (Cursor)
1. **Reviewer console** (`/review`, `/review/cases/:id`; `VITE_REVIEWER_CONSOLE=1`):
   - mock sign-in (pick a reviewer from `GET /api/review/me` options);
   - queue: stage, waiting on, age;
   - case page: the brief with source badges and evidence, documents, and an actions panel showing only legal actions (re-upload with document picker and remarks, reject with remarks and category, approve first level, request contacts, request sales data, withdraw, approve). Re-linking company and brand comes on Day 5.
2. **Case agent** (`app/agents/case/` or a second graph built from the same factory with its own tools and prompt):
   - tools: `get_case_status`, `request_reupload_documents`, `update_contacts`, `confirm_fields`, `show_contacts_review`, `request_sales_data_upload`, `search_faq`, `suggest_replies`, `request_handoff`;
   - prompt per L4 §3.5: outcome framing, re-upload explanation from the remarks, one contacts bundle with "that's me" reuse, sales data, rejection and approval explanations; never promise, never name reviewers.
   - The chat endpoint uses the case agent when the inquiry isn't a draft.
3. **Cards:** `case_status`, `contacts`, `sales_data_upload`; `document_upload` gains re-upload mode with `requested_doc_types`.
4. **Route** `/inquiry/case`.
5. Playwright `@scripted` story **T2** (re-upload loop) with an applicant and a reviewer browser context.

## Tests
- Vitest for the new cards and console pages.
- Story T2 green; S1–S3 still green.

## End-of-day demo check
- [ ] Submit an inquiry → it appears in the right reviewer's queue → request a Brand Profile re-upload → the email link opens the case in chat → the agent explains why → upload → Resubmit → back in first review.
- [ ] Approve first level → Azure AD invitation in the dev inbox → request contacts → "I'm the signatory; billing is Omar Saleh, omar@…, +966 5…" → contacts sent.
- [ ] `docs/STATUS.md` §0 Day 4 ✅; rows 23–26 🟡.
