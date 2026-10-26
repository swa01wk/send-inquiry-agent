# Step 30 — Triggers, "Needs attention" and the drafting agent

Read first: @docs/specs/l5-governed-proactivity.md (sections 3.2, 3.4, 3.5, 3.6) @backend/app/proactive/ (from step 29) @backend/app/domain/case_brief.py

**Start in plan mode:** show each trigger's condition in code, the console view and its actions, and the `proactive` agent with its deterministic draft checks. Wait for approval before writing code.

## Goal
Stuck cases surface to the right owner with the next step prepared, and applicants get timely, policy-approved nudges — without any proactive path deciding anything.

## Build
1. Triggers per spec §3.2: stalled review, escalation, pending applicant action, abandoned draft (Must); late duplicate (Should). Conditions read thresholds from the policy and time from the `Clock`.
2. `app/agents/proactive/`: drafts the reminder from the case brief and open requests inside the template frame. No write tools.
3. Draft checks (deterministic): names each open request; no promise or timeline; no reviewer name; only template-allowed fields. On failure, use the plain template text and audit why.
4. Console:
   - `GET /api/review/attention`, `POST /api/review/attention/{id}/approve` (optional edited text) and `/dismiss` (reason);
   - a "Needs attention" view ranked per spec §3.4, with a badge count in the console header.
5. Templates: `review_stalled`, `review_escalated`, `tenant_reminder`, `draft_resume`.
6. Update `docs/spec.md` and `docs/STATUS.md` (row 30).

## Tests
- `test_triggers.py`: each trigger fires at the threshold, not before; once per period; not after the condition clears.
- `test_drafts.py`: every check, including fallback.
- `test_authority.py`: no proactive code path can call the state machine.
- **Playwright:** stories P1–P6 (spec §3.6), using the dev clock.
- Live eval: "Proactive" scenario scoring drafted reminders.

## Acceptance criteria
- Gates Y1, Y3 and Y4 pass.

## Verify
```
make test && make lint && make e2e
```
