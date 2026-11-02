# Step 12 — Baseline parity suite (B0)

Read first: @docs/specs/m0-modular-core.md (sections 2, 4) @docs/spec.md @.cursor/rules/backend.mdc @.cursor/rules/agent.mdc

Runs after steps 11c and 11e (pre-baseline and out-of-order fixes, #53 and #54), so the goldens record the corrected behaviour, including quiet card actions and `checks.remaining` / `checks.next_step`.

## Goal
Freeze today's behaviour before M0 restructures the backend, so every later step can prove it changed nothing the user sees.

## Build (`backend/tests/parity/`)
1. `recorder.py`: run a scripted scenario through the real HTTP app and write every SSE event to JSONL.
   - Record through `create_app` + httpx `AsyncClient` with `ASGITransport`, so SSE framing is captured. Don't call `run_turn` directly.
   - Most card actions are agent turns: script one reply for each. **Quiet actions** (spec §4) run no agent turn and need no scripted reply. These are:
     - `otp_failed` with attempts left;
     - a manual `resend_email_link` or `resend_otp`;
     - `email_verified` or `mobile_verified` while the other channel is still pending;
     - `document_number_set`.

     For example, `verify_email` (quiet while the mobile is pending), then `submit_otp` with the right code (an agent turn: `verification_complete`), then `documents_updated` (an agent turn). Assert that quiet actions have no `token` event.
   - Normalise, in order of appearance:
     - `message_id`s to `m1`, `m2`, …;
     - timestamps (including documents' `uploaded_at`);
     - submission references (`MockSubmitService` is random) to `GEO-<code>-<ref>`;
     - document file ids (`services/storage.py` `uuid4().hex`);
     - any `session_id` UUID that appears in a payload;
     - the verification card's `email.demo_token` and any email-link token.
   - Keep everything else.
2. Record seven golden transcripts into `golden/`:
   - CR happy path (through `documents_updated` and the review card);
   - skip CR;
   - existing CR;
   - landline-only contact;
   - two malls named;
   - wrong OTP three times. Click the email link first; it is quiet while the mobile is pending. Attempts 1 and 2 are quiet. Attempt 3 is an agent turn: a new code is sent automatically (`otp_resent`). Then the right code gives `verification_complete`.
   - documents before the email link (S14): SMS code, then both documents (`documents_complete still_needed=verify_email`, no review card), then the email link (`verification_complete`, review card). This covers guard rule 7 and `checks.next_step` moving from `verify_email` to `terms`.

   Reuse the step scripts in `tests/scenarios/agent_steps.py`, and `tests/e2e_scripts/s14-out-of-order.json` for the seventh. Landline-only and two-malls have no scenario yet: write new scripts and check them against today's real behaviour.
3. `test_golden.py`: replay each script and compare the normalised stream to its golden file:
   - event types in order;
   - card types and payloads;
   - draft `changed_keys`;
   - final phase;
   - final draft (`model_dump`).

   On mismatch, print a readable diff.
4. `make golden` regenerates the files; regeneration needs a deliberate commit.
5. `backend/scripts/export_fe_fixtures.py` turns each golden into a frontend mock scenario in `frontend/src/mocks/scenarios/<name>.json` (testing spec §2.2, §7). `make golden` runs it too, so a golden and its fixture always change together. Add an `@fe` Playwright test that replays each exported scenario.

## Scope
Don't change any `app/` code.

## Also
- Live-eval baseline: two runs of `make eval-live` (all groups, `EVAL_REPEATS=3`). These run in CI on `main` after #54 (`e2e.yml`, suite `eval`, group `all`). Record both scores, the run ids and any scenario below 3/3 in `docs/eval-notes.md` as the M0 baseline. They also close AGENT-LIVE for 11e, so set 11e to ✅ in `docs/STATUS.md` if both pass.
- Update `docs/STATUS.md` (row 12).

## Tests
**Layers** (`docs/specs/testing-strategy.md`): AGENT-DET (parity goldens), BE. AGENT-LIVE: record the baseline (`make eval-live`, ×2).

## Acceptance criteria
- `OPENAI_API_KEY= uv run pytest tests/parity -q` passes twice in a row.
- Changing one card payload field in `api/cards.py` makes it fail with a diff naming that field (then revert).
- `make ci` is green, including the exported fixtures in `make e2e-fe`.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/parity -q
```
