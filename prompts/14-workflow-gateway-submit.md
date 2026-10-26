# Step 14 — Workflow state machine, tool gateway, idempotent submit

Read first: @docs/specs/m0-modular-core.md (sections 6, 7) @backend/app/agent/actions.py @backend/app/agent/tools.py @backend/app/services/

**Start in plan mode:** propose the transition table in code, the gateway API, and the new submit flow step by step. Wait for approval before writing code.

## Goal
One reference per inquiry, no matter how often or how concurrently Submit is pressed. Every external call has a timeout and a typed failure.

## Build
1. `app/workflow/machine.py`: `transition(inquiry, event, actor)`, a pure function implementing the table in spec §6. It raises `IllegalTransition`. Define the L4 states and events now (the amended rows in §6, including the reviewer-queue check on the actor); leave them untriggered.
2. `app/gateway/`:
   - `Gateway.call(name, fn, *, idempotent, timeout_s, audit_args)`;
   - `GatewayError(kind)` with kinds `timeout`, `unavailable`, `rejected`, `invalid`;
   - jittered retries for idempotent calls.

   Route every service call in tools, actions and the documents router through it.
3. `app/domain/payload.py`: `InquiryPayload` built from the draft (§7.1.1 basic info, document references, verification flags). Not a raw `model_dump`.
4. `SubmitService.submit(payload, *, idempotency_key)` and `lookup(idempotency_key)`. The mock returns the same reference for a repeated key.
5. Rewrite `_accept_and_submit` as spec §7.2 steps 1–5:
   - persist `draft → submitting` before calling out;
   - map gateway outcomes to `submitted`, back to `draft`, or `submit_pending`;
   - reconcile with `lookup`;
   - a repeat on a submitted inquiry returns the stored reference and success card.
6. New `[ui_event]` notes: `submit_pending`, `submit_failed <reason>`, `submitted reference=… (repeat)`. Teach them in the system prompt. Extend the guard so a reply never claims success on `submit_pending`.

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE, AGENT-DET, INT (repeat Submit in the browser). New `[ui_event]` notes in the prompt, so AGENT-LIVE (intake) and an E2E-LIVE smoke run.
- `tests/workflow/test_machine.py`: every legal transition, and a sample of illegal ones.
- `tests/workflow/test_idempotent_submit.py`:
  - two concurrent `accept_and_submit` calls → one reference;
  - a repeat returns the same reference;
  - a timeout then reconcile → `submitted`;
  - a definite rejection → back to `draft`.
- `tests/gateway/test_gateway.py`: forced timeout, unavailable and rejected for each wrapped service.

## Acceptance criteria
- Gates G3, G5 and G6 pass.
- Parity suite green.
- `docs/STATUS.md` updated (row 14).

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/workflow tests/gateway tests/parity -q
```
