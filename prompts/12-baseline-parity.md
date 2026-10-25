# Step 12 — Baseline parity suite (B0)

Read first: @docs/specs/m0-modular-core.md (sections 2, 4) @docs/spec.md @.cursor/rules/backend.mdc @.cursor/rules/agent.mdc

## Goal
Freeze today's behaviour before M0 restructures the backend, so every later step can prove it changed nothing the user sees.

## Build (`backend/tests/parity/`)
1. `recorder.py`: run a scripted scenario through the app (`create_app` + `ScriptedChatModel` + httpx `AsyncClient`) and write every SSE event to JSONL.
   - Normalise `message_id`s to `m1`, `m2`, … in order of appearance.
   - Normalise timestamps and email-link tokens to placeholders.
   - Keep everything else.
2. Record six golden transcripts into `golden/`:
   - CR happy path;
   - skip CR;
   - existing CR;
   - landline-only contact;
   - two malls named;
   - wrong OTP three times.

   Reuse the step scripts in `tests/scenarios/agent_steps.py`; add scripts for the new ones.
3. `test_golden.py`: replay each script and compare the normalised stream to its golden file:
   - event types in order;
   - card types and payloads;
   - draft `changed_keys`;
   - final phase;
   - final draft (`model_dump`).

   On mismatch, print a readable diff.
4. `make golden` regenerates the files; regeneration needs a deliberate commit.

## Also
- Run `scripts/eval_live.py` twice and record both scores in `docs/eval-notes.md` as the M0 baseline.

## Acceptance criteria
- `pytest tests/parity` is green on the current code.
- Changing any card payload field makes it fail with a diff that names the field.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/parity -q
```
