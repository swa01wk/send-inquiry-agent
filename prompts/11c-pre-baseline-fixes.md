# Step 11c — Pre-baseline fixes

Read first: @docs/specs/pre-baseline-fixes.md @docs/spec.md @.cursor/rules/agent.mdc @backend/app/agent/tools.py @backend/app/agent/actions.py @frontend/src/hooks/useChatSession.ts

This step runs **before** `12-baseline-parity.md`, so the golden transcripts record the corrected behaviour.

## Goal
Close four gaps that change what the user sees: unconfirmable-until-shown derived values, a turn when the required documents are complete, no Office product line, and two contract bugs.

## Build
1. **Confirm only what was shown (spec §3.1).**
   - `AgentState` gains `turn_index: int` and `confirm_card_turns: dict[str, int]`; `Session` gains `confirm_card_turns`. `run_turn` increments `turn_index` for every message and action, and persists both fields with the session like `confirm_card_keys`.
   - Wherever a `confirm_fields` card is emitted with a key list, record `confirm_card_turns[card_id] = turn_index`.
   - `confirm_fields` skips any key that isn't on a card whose recorded turn is lower than the current `turn_index`, with reason `not_shown`.
   - Remove the "hasn't had a chance to see" sentence from `system_prompt.md` and `docs/agent-system-prompt.md` (keep the two in sync).
2. **Documents complete (spec §3.2).**
   - New UI action `documents_updated` in `agent/actions.py`: recompute required documents from the draft; note `[ui_event] documents_complete` or `[ui_event] documents_pending <doc_types>`.
   - `useChatSession`: after an upload or delete, send `documents_updated` only when `required_docs_uploaded` rises to `required_docs_total`.
   - Add `documents_complete` to the `[ui_event]` list in the prompt: thank the user in one or two sentences, mention optional documents once, point to the review card.
   - Regenerate the affected e2e scripts with `backend/scripts/generate_e2e_scripts.py`.
3. **Remove Office (spec §3.3)** from `data/master_data.json`, `data/faq.json`, `services/submit.py`, `docs/spec.md` §8–9 and `docs/assumptions.md`.
4. **Contract bugs (spec §3.4).**
   - De-duplicate `written_keys` in `domain/draft_ops.py:write_fields` (keep order).
   - `normalise_saudi_landline`: 8 or 9 digits after `+966`, not starting with 5. Update `docs/spec.md` §2.
5. **Document numbers on the documents card (spec §3.5):** `numbers[]` in the `document_upload` payload (CR ID read-only, VAT ID, National ID, National Address), the `set_document_number` action, inputs in `DocumentChecklistCard` next to each document.
6. **Doc and rule fixes (spec §3.6)**: reword the `submit_inquiry` mentions in `.cursor/rules/project.mdc` and `.cursor/rules/agent.mdc`; add a correction note to `docs/eval-notes.md`; delete `domain/draft_merge.py`.
7. Fold spec §4 into `docs/spec.md`. Update `docs/STATUS.md` (row 11c).

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE, FE (Vitest), INT, AGENT-DET. The prompt changes, so also AGENT-LIVE (`scripts/eval_live.py` twice; the 11d harness doesn't exist yet) and an E2E-LIVE smoke run.
- `tests/agent/test_confirm_shown.py`: the five cases in spec §3.1.
- `tests/api/test_documents_complete.py`: complete → review card in the same turn; premature → `documents_pending`.
- Frontend: the hook sends `documents_updated` exactly once, and not for optional documents.
- `tests/domain/test_master_data.py`: no `office` id, `OFF` code or "Office" text in seed data or FAQ.
- `tests/api/test_document_card.py`: CR ID read-only from the draft; a valid VAT ID is saved as `user`; an invalid one returns its error code. Vitest for the inputs.
- Validation: `+966 11 234 5678` is a landline; `+966 5…` is still a mobile.
- Update existing tests that relied on `office` or the 8-digit landline rule; say which in the PR.

## Acceptance criteria
- Gate P1–P5 in the spec.
- No other behaviour change (existing scenario tests pass unchanged apart from the updates listed above).

## Verify
```
make test && make lint && make e2e
```
