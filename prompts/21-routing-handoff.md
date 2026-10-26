# Step 21 — Intent routing and human handoff

Read first: @docs/specs/l3-reliable-intake.md (sections 3.5, 3.6) @backend/app/agents/ (from step 16) @docs/agent-system-prompt.md

**Start in plan mode:** show the intent schema, the rules that decide before the classifier, the classifier prompt, and the handoff triggers. Wait for approval before writing code.

## Goal
Each message reaches the right handler, and the user can always reach a person when the agent can't finish.

## Build
1. `app/agents/router.py`, which runs before the intake and status agents:
   1. Rules first: a reference pattern, an explicit request for a person, an existing-CR match.
   2. Otherwise a structured-output classifier (`ROUTER_MODEL`) returning `{intent, confidence}`, given the message and the inquiry status.
   3. Below `ROUTER_MIN_CONFIDENCE`, or mid-intake, default to `inquiry_intake`.

   Intents and handlers are as in spec §3.5. Record the routing decision in the audit trail.
2. Replies for `general_inquiry` and `existing_tenant_new_space` come from a small `redirect` agent with no write tools. Its copy explains where to go (General Inquiries after sign-in; Leasing Opportunities for existing tenants) and offers to continue a leasing inquiry.
3. Handoff:
   - triggers from spec §3.6;
   - a `handoff` card (`{phone, email, hours, short_ref}` from `CALL_CENTRE_*` config);
   - a `request_handoff` action;
   - `CallCentreService.create_case` with the inquiry payload, the reason and a short summary;
   - audit event `handoff_created`.

   The inquiry stays resumable.
4. Frontend: a `HandoffCard` component in `CardSlot`, styled like the other cards.
5. `tests/routing/fixtures.jsonl`: at least 60 labelled messages across all intents, including Arabic and mixed-language ones.

## Tests
- **Routing:** accuracy of at least 95% on the fixture set with a scripted classifier. The same set is also run against the real model as a live eval scenario.
- **Handoff:** each trigger produces exactly one card, one case and one audit event.
- **Playwright:** stories S7 and S8 (spec §3.13).

## Acceptance criteria
- Gate E1 passes.
- Handoff covered for every trigger.
- `docs/spec.md` and `docs/STATUS.md` (row 21) updated.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/routing tests/handoff -q
```
