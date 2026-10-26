# Step 28 — Approval to Yardi, L4 KPIs and the L4 gate

Read first: @docs/specs/l4-outcome-assistance.md (sections 2, 3.7, 3.10, 3.11) @backend/scripts/kpi_report.py @docs/eval-notes.md

## Goal
A final approval invites the extra contacts, tells the applicant, and hands the lead to Yardi exactly once, with recovery; then the whole L4 gate is run.

## Build
1. On `approved` (effects, spec §3.4 and §3.7): invitations for additional contacts without one; `inquiry_accepted`; `YardiService.send_lead(LeadPayload, idempotency_key=f"lead:{inquiry_id}")` → `sent_to_yardi` or `yardi_failed` with retries; after `YARDI_MAX_ATTEMPTS`, flag the case for operations in the console.
2. Status page and case agent: "Approved — your details are with the leasing team for a proposal" only after `sent_to_yardi`.
3. `kpi_report.py`: add the L4 KPIs (spec §3.11), from audit events and console timestamps.
4. Make sure stories T1–T10 (T9 and T10 in `docs/specs/intake-channels.md` §4) all exist in `e2e/tests/stories/` and pass.
5. Run the L4 gate: X1–X9 and intake-channels C5, two live eval runs (Case, Contacts, Reviewer scenarios), the KPI report. Record results in `docs/eval-notes.md` and the gate in `docs/STATUS.md`.
6. Fold remaining L4 contract changes into `docs/spec.md`; add the L4 assumptions (spec §6) to `docs/assumptions.md`.

## Tests
**Layers** (`docs/specs/testing-strategy.md`): Gate step: all six layers; AGENT-LIVE and E2E-LIVE twice each.
- `send_lead` is idempotent under retries and concurrent effects; a repeat approval can't send twice.
- **Playwright:** stories T1 and T7.

## Acceptance criteria
- Every L4 gate row has a passing test or a recorded result.
- `docs/STATUS.md` shows the L4 gate result.

## Verify
```
make gate && cd backend && uv run python scripts/kpi_report.py --last-run
```
