# Step 24 — Reviewer console and case brief

Read first: @docs/specs/l4-outcome-assistance.md (sections 3.3, 3.6 "Case brief", 3.9) @docs/design-spec.md @.cursor/rules/frontend.mdc @backend/app/workflow/ (from step 23)

**Start in plan mode:** show the review API, the mock sign-in, the page layout (queue, case) and the deterministic case-brief model. Wait for approval before writing code.

## Goal
Someone can play the reviewer: see their queue, open a case with a grounded brief, and take every decision §7.1.1 b–c allows, through the state machine. No assistant yet.

## Build
**Backend**
1. `/api/review/*` (spec §3.3 API table), enabled only when `REVIEWER_CONSOLE=true` and `INTEGRATIONS=mock`; otherwise 404. `X-Reviewer-Id` resolves a reviewer from the directory; unknown → 401.
2. `POST /api/review/cases/{id}/actions {action, payload}` maps each console action to its state-machine event with the reviewer as actor. Errors: `illegal_transition`, `not_in_queue`, `invalid_payload` (for example empty remarks).
3. `domain/case_brief.py`: the deterministic brief in spec §3.6 (fields with source and evidence, verification, documents with history, duplicates and follow-ons, requests, decisions, stage ages, next-decision checklist from the policy). Pydantic model; no LLM.

**Frontend** (routes from L3 step 18)
1. `/review`: mock sign-in (pick a reviewer), then the queue: stage, waiting on, age, duplicate flag.
2. `/review/cases/:id`: the brief, fields with `SourceBadge`, documents (download), request history, audit timeline, and an actions panel with only the legal actions and their forms (documents picker, remarks, reason category, Yardi pickers).
3. Same tokens and components as the chat; accessible and responsive (rules in `.cursor/rules/frontend.mdc`).
4. Update `docs/spec.md` and `docs/STATUS.md` (row 24).

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE, FE (queue and case page suites), INT (stories T8, T3 reviewer half).
- API: each action happy path and each error; a reviewer can't see another queue's case.
- `tests/case_brief/`: every brief line traces to a field, document or audit event; a derived value shows its evidence; a skipped CR shows as skipped.
- Frontend: queue and case pages render; actions panel shows only legal actions per status.
- **Playwright:** story T8 (routing and access) and the reviewer half of T3 (reject with remarks).

## Acceptance criteria
- Gates X4 (brief part) and X6 (reviewer part) pass.
- A full lifecycle can be clicked through in the console with the dev inbox open beside it.

## Verify
```
make ci
```
