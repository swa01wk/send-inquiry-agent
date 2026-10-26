# Step 12 — Baseline parity suite (B0)

Read first: @docs/specs/m0-modular-core.md (sections 2, 4) @docs/spec.md @.cursor/rules/backend.mdc @.cursor/rules/agent.mdc

Runs after step 11c (pre-baseline fixes), so the goldens record the corrected behaviour.

## Goal
Freeze today's behaviour before M0 restructures the backend, so every later step can prove it changed nothing the user sees.

## Build (`backend/tests/parity/`)
1. `recorder.py`: run a scripted scenario through the real HTTP app and write every SSE event to JSONL.
   - Record through `create_app` + httpx `AsyncClient` with `ASGITransport`, so SSE framing is captured. Don't call `run_turn` directly.
   - Card actions are agent turns. Script one reply for each action (for example `verify_email`, then `submit_otp`, then `documents_updated`).
   - Normalise, in order of appearance:
     - `message_id`s to `m1`, `m2`, …;
     - timestamps (including documents' `uploaded_at`);
     - submission references (`MockSubmitService` is random) to `GEO-<code>-<ref>`;
     - document file ids (`services/storage.py` `uuid4().hex`);
     - any `session_id` UUID that appears in a payload;
     - the verification card's `email.demo_token` and any email-link token.
   - Keep everything else.
2. Record six golden transcripts into `golden/`:
   - CR happy path (through `documents_updated` and the review card);
   - skip CR;
   - existing CR;
   - landline-only contact;
   - two malls named;
   - wrong OTP three times. Click the email link first, so `verification_complete` fires on the right turn.

   Reuse the step scripts in `tests/scenarios/agent_steps.py`. Landline-only and two-malls have no scenario yet: write new scripts and check them against today's real behaviour.
3. `test_golden.py`: replay each script and compare the normalised stream to its golden file:
   - event types in order;
   - card types and payloads;
   - draft `changed_keys`;
   - final phase;
   - final draft (`model_dump`).

   On mismatch, print a readable diff.
4. `make golden` regenerates the files; regeneration needs a deliberate commit.

## Scope
Don't change any `app/` code.

## Also
- Run `scripts/eval_live.py` twice and record both scores in `docs/eval-notes.md` as the M0 baseline.
- Update `docs/STATUS.md` (row 12).

## Acceptance criteria
- `OPENAI_API_KEY= uv run pytest tests/parity -q` passes twice in a row.
- Changing one card payload field in `api/cards.py` makes it fail with a diff naming that field (then revert).
- `make test`, `make lint` and `make e2e` are green.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/parity -q
```
