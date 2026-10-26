# Step 23 — Lifecycle core: case data, review routing, effects, back-office mocks

Read first: @docs/specs/l4-outcome-assistance.md (sections 1, 3.1, 3.2, 3.4) @docs/specs/m0-modular-core.md (section 6) @backend/app/workflow/ @backend/app/store/ @backend/app/notifications/ @backend/app/policy/

**Start in plan mode:** show the case-data fields and migration, the effects outbox (table, keys, retry), the routing table in the policy, and the new mocks. Wait for approval before writing code.

## Goal
A submitted inquiry moves through the whole §7.1.1 b–c lifecycle under the state machine, with every side effect (notifications, invitations, Yardi) sent exactly once. Backend only; the console and agents come next.

## Build
1. Case data on `Inquiry` (spec §3.1): `review_queue`, `requests`, `decisions`, `tenant_contacts`, `sales_data`, `document_history`, `onboarding`, `yardi`. Alembic migration `0002_case_data`. Models in `app/store/models.py`; `TenantContact` reuses `FieldValue`.
2. Policy additions: `review_routing` (product line × region → role), `second_level_contacts` (required and optional roles), `rejection_categories`, `after_rejection`, `require_contacts_before_approval`.
3. Make the L4 rows of the state machine live (M0 §6), including the actor check: a reviewer event needs a reviewer whose role and regions match `review_queue`.
4. Effects (spec §3.4): a `case_effects` outbox keyed by `(inquiry_id, event_seq, effect)`; a worker in the app lifespan runs pending effects through the gateway with retries; failures are audited and never roll back the transition. `submitted` triggers `routed`.
5. Mocks (spec §3.2), each behind the gateway and honouring `MOCK_FAULTS`:
   - `ReviewerDirectory` from `data/mock_world/reviewers.json` (one reviewer per queue, plus a region manager per role);
   - `IdentityService` (Azure AD): `invite`, `status`; the invitation message carries an accept link (`GET /api/dev/identity/accept/{invitation_id}`, dev tools only);
   - `YardiService`: `search_companies`, `brands_for_company`, `send_lead`, from `data/mock_world/yardi.json`.
6. Templates for every row of spec §3.4, each with its `kind`.
7. `domain/payload.py`: `LeadPayload` for Yardi.
8. Fold the data, workflow, service and config changes into `docs/spec.md`; update `docs/STATUS.md` (row 23).

## Tests (`tests/lifecycle/`)
**Layers** (`docs/specs/testing-strategy.md`): BE (lifecycle, effects, authority). No agent or UI change.
- Every path in spec §1 driven by direct events: approve → approve → `sent_to_yardi`; reject at each level; re-upload loop; contacts and sales-data requests; withdraw; re-link.
- `test_authority.py`: a reviewer from another queue or region, the applicant, or the system can't fire reviewer events; illegal transitions are rejected and audited.
- `test_effects.py`: each event's messages land in the outbox exactly once, even when the worker retries; an effect failure leaves the transition in place.
- Routing: Store/Media/Specialty in each region resolve to the right queue.

## Acceptance criteria
- Gates X1 (backend part), X2 (state machine part), X5 and X7 pass.
- Parity suite and L3 stories still green.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/lifecycle tests/workflow tests/audit tests/parity -q
```
