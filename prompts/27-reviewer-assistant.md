# Step 27 — Reviewer assistant

Read first: @docs/specs/l4-outcome-assistance.md (section 3.6) @backend/app/domain/case_brief.py (from step 24) @backend/app/agents/registry.py

**Start in plan mode:** show the `reviewer` agent spec (tools, prompt, guard), how drafted notes reach the action forms, and the `assistant_suggestion` audit event. Wait for approval before writing code.

## Goal
Reviewers get a grounded assistant beside each case: it explains the case, suggests Yardi matches, drafts remarks, and flags what's missing — and never decides.

## Build
1. `app/agents/reviewer/` registered in the agent registry, with tools per spec §3.6: `get_case_brief`, `search_yardi_companies`, `list_company_brands`, `find_related_inquiries`, `draft_reviewer_note`.
2. Prompt rules: answer only from the brief and tool results; cite which field or document a statement comes from; for approve or reject requests, say the decision is the reviewer's and point to the button.
3. Guard: no claim that a decision or request was made; no statement about the applicant that isn't in the brief.
4. `POST /api/review/cases/{id}/assistant` streams the reply with the same SSE events as the applicant chat. A suggestion card type `reviewer_suggestion {kind, text, yardi_company?, yardi_brand?}` with **Use** fills the matching action form (it does not submit it).
5. Audit `assistant_suggestion {kind, used}`; `used` is set when the reviewer submits an action built from it.
6. Frontend: the assistant panel on the case page; suggestion cards wire into the actions panel.
7. Update `docs/spec.md` and `docs/STATUS.md` (row 27).

## Tests
- Yardi suggestions follow the first-word rule and only active companies; brands only for the chosen company.
- The reviewer agent has no tool that can change a case (allowlist test).
- Drafted notes land in the form unsent; suggestion use is audited.
- **Playwright:** stories T5 and the reviewer half of T6.
- Live eval: "Reviewer" scenario — "what's missing?", "summarise the documents", "approve this".

## Acceptance criteria
- Gate X4 passes (grounded briefs and answers).
- Gate X2 holds with the assistant in place.

## Verify
```
make test && make lint && make e2e
```
