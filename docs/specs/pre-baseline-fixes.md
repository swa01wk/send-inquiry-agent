# Pre-baseline fixes

**Status:** locked (PRD v1.0, `docs/PRD.md`) · **Before:** [M0](m0-modular-core.md) step 12 (baseline parity) · **Cursor step:** `prompts/11c-pre-baseline-fixes.md`

## 1. Why

Step 12 freezes today's behaviour in golden transcripts. Anything that changes what the user sees after that point means regenerating the goldens and explaining the diff in review. These fixes change visible behaviour, so they land first and the baseline records the corrected behaviour.

Each fix closes a gap between the agent and either a golden rule or the business flow (requirements v2.1.7.1, §7.1.1):

| # | Gap | Rule or requirement |
| --- | --- | --- |
| F1 | `confirm_fields` can confirm a derived value the user never saw. "Never confirm a value the user hasn't had a chance to see" is only a prompt sentence | Golden rules 1 and 2; framework anti-patterns "prompt-only policy" and "silent derivation" |
| F2 | Uploading the last required document doesn't run a turn, so the review card appears only after the user's next message | §7.1.1: documents → submit; framework L3 capability 5 (stop when completion conditions are met) |
| F3 | Office is still offered as a product line (`data/master_data.json`, `data/faq.json`), so the agent can map a user to it | §1 and §7.1.1 list three product lines: Store, Media, Specialty |
| F4 | Two known contract bugs leak into what the parity suite compares | Handoff §9 |
| F5 | The documents card has no inputs for VAT ID, National ID and National Address, and doesn't show the CR ID, although the fields and validators exist | §7.1.1 documents table ([traceability](workflows-7-1.md) R32–R38) |

## 2. Gate

| # | Criterion | Proved by |
| --- | --- | --- |
| P1 | The agent can't confirm a key that wasn't on a confirm card shown before the current user message | `tests/agent/test_confirm_shown.py` |
| P2 | Completing the required documents runs one agent turn and shows the review card without a typed message | `tests/api/test_documents_complete.py`, Playwright `@scripted` happy path |
| P3 | No `office` unit type anywhere in seed data, FAQ, unit codes or prompts | `tests/domain/test_master_data.py` grep check |
| P4 | `make test`, `make lint`, `make e2e` green; because the prompt changes, `scripts/eval_live.py` run twice with no lower score and an `@live` smoke run (testing strategy §4) | CI and local run; results in the PR |
| P5 | The documents card shows the CR ID read-only and accepts VAT ID, National ID and National Address next to their uploads, validated by the existing rules | `tests/api/test_document_card.py`, Vitest, Playwright `@scripted` |

## 3. Work items

### 3.1 F1: confirm only what was shown (Must)

**Rule, in code.** `confirm_fields` confirms a key only if:
1. the key is listed on a `confirm_fields` card (`confirm_card_keys`), and
2. that card was emitted **before the current user message**, so the user had a chance to see it.

Keys that fail either check are skipped with the reason `not_shown`, the same way `user_expressed_doubt` is reported today.

**Mechanism.**
- Add `confirm_card_turns: dict[card_id, int]` next to `confirm_card_keys` in `Session` and `AgentState`. It records the user-turn number when the card's key list was last emitted.
- Add `turn_index: int` to `AgentState`, incremented in `run_turn` for every typed message and every UI action.
- `confirm_fields` allows a key when some card lists it and `confirm_card_turns[card_id] < turn_index`.
- A card re-emitted with new keys this turn (for example, a correction) resets its turn number, so the new values wait for the next user message.

**Unaffected.**
- The `confirm_card` UI action (the user pressed Confirm on the card) stays as it is: the user saw it by definition.
- `edit_field` writes `source=user`, so it needs no confirmation.
- The review card remains the last check before consent.

**Prompt.** Remove the sentence "Never confirm a value the user hasn't had a chance to see" from `system_prompt.md` and `docs/agent-system-prompt.md`; the tool result now says `not_shown` when the agent tries.

**Tests (`tests/agent/test_confirm_shown.py`).**
- Derived in turn N and confirmed in the same turn → skipped `not_shown`.
- Derived in turn N, confirmed in turn N+1 → confirmed.
- A key never put on a confirm card → skipped `not_shown`.
- `verify_cr` prefill (verified) follows the same rule.
- Re-emitted card with a corrected value → the new value waits a turn.

### 3.2 F2: run a turn when the required documents are complete (Must)

Uploads are REST calls (`POST /api/sessions/{id}/documents`), not chat turns, so nothing tells the agent the documents step is done.

**New UI action `documents_updated`** (payload `{}`).
- **Frontend.** `useChatSession.uploadDocumentForType` and `removeDocument` compare `draft.checks.required_docs_uploaded` before and after the call. When it reaches `required_docs_total` (from below), they send `documents_updated`. Nothing is sent for optional uploads or while required documents are still missing.
- **Backend** (`agent/actions.py`). The handler doesn't trust the frontend: it recomputes from the draft.
  - All required documents present → note `[ui_event] documents_complete`.
  - Otherwise → note `[ui_event] documents_pending <doc_type> …` (the frontend sent it early, or a delete raced it).
- **Agent turn.** As with every action, the note runs a turn. The guard already emits the `review` card when the phase becomes `review`. The agent replies in one or two sentences: thanks, optional documents can still be added, and the review card is ready.
- **Prompt.** Add `documents_complete` to the list of `[ui_event]` notes the agent understands.

**Tests.**
- `tests/api/test_documents_complete.py`: uploading the second required document then sending `documents_updated` yields a turn with the review card; a premature action yields `documents_pending`.
- Frontend: the hook sends the action once when the count reaches the total, and not for optional documents.
- Playwright `@scripted` happy path: the review card appears after the second upload with no typed message. Update `backend/tests/e2e_scripts/` with `backend/scripts/generate_e2e_scripts.py`.

### 3.3 F3: remove Office (Must)

- Remove `office` from `backend/app/data/master_data.json`, the `OFF` code from `services/submit.py` `_UNIT_CODES`, and the Office sentence from the `unit_types` answer in `data/faq.json` (and its `office` keyword).
- `docs/spec.md` §8 unit codes and §9 seed data, and `docs/assumptions.md` (Submit row), drop `OFF`.
- Step 17 (policy file) no longer needs to remove Office; it only asserts the product lines come from the policy.

### 3.4 F4: contract bugs that affect parity (Should)

- `write_fields` lists `mobile` or `landline` twice in `written_keys` for `contact_number`; de-duplicate, keeping order. `changed_keys` in the `draft` event then lists each key once.
- Saudi landline rule: accept 8 **or 9** digits after `+966` for a number not starting with 5 (real numbers such as `+966 11 234 5678` have 9). Update `normalise_landline`, `docs/spec.md` §2 field table, and the validation tests.

### 3.5 F5: document numbers on the documents card (Must)

Requirements §7.1.1 pair each optional document with its number: CR ID (10 digits, **disabled**, from basic info), VAT ID (15 digits), National ID (10 digits, of the primary contact) and National Address. The fields `vat_number`, `national_id_number` and `national_address` and their validators exist, but nothing collects them.

- The `document_upload` card payload gains `numbers: [{key, label, value, editable, error}]`: `cr_number` (read-only, from the draft), `vat_number`, `national_id_number`, `national_address`. Each row sits next to its document in the card.
- New UI action `set_document_number {key, value}`: validates with the existing rule, writes the field as `user`, confirmed; note `document_number_set <key>` or `document_number_invalid <key> <code>`. It runs a turn like every action; the agent replies only if the value was invalid.
- The agent may still save these numbers from chat with `update_draft`, as today.
- The review card already lists them under Documents.

### 3.6 Doc and rule fixes (Could)

- `.cursor/rules/project.mdc` golden rule 3 and `.cursor/rules/agent.mdc` mention a `submit_inquiry` tool that doesn't exist. Submit is the `accept_and_submit` UI action; reword both.
- `docs/eval-notes.md`: the first entry mentions forced tool choice, which the graph no longer does; add a correction note (don't rewrite history).
- Delete `domain/draft_merge.py` (unused).

## 4. Contract changes to fold into `docs/spec.md`

| Area | Change |
| --- | --- |
| Actions | `documents_updated {}` → notes `documents_complete` or `documents_pending <doc_types>` |
| Tools | `confirm_fields` skips keys not shown on an earlier confirm card (`not_shown`) |
| Data | Landline: `+966` + 8 or 9 digits, not starting with 5 |
| Seed data | Unit types Store, Media, Specialty; codes `STR`, `MED`, `SPC` |
| Cards | `document_upload` gains `numbers[]` |
| Actions | `set_document_number {key, value}` → notes `document_number_set <key>` or `document_number_invalid <key> <code>` |

## 5. Out of scope

Everything in M0 and later. No change to the graph shape, services or SSE events.
