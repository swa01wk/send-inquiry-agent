# Step 01 — Domain model, validation and submit rules

Read first: @docs/spec.md (sections 2 and 7 "DraftSummary") @.cursor/rules/backend.mdc @docs/assumptions.md

## Goal
Implement the inquiry draft with field provenance, all validation rules, `can_submit`, phase computation and the `DraftSummary` builder — pure Python, no FastAPI or LangGraph.

## Build (`backend/app/domain/`)
1. `models.py`: `Source`, `FieldKey` (enum of every key in the field table), `DocType`, `FieldValue`, `DocumentRef`, `InquiryDraft` (every `FieldKey` present with an empty `FieldValue`; `area_min=10`/`area_max=25000` as `default`, confirmed), `Blocker`, `Phase`.
2. `fields.py`: one registry describing each field (label, group, required, validator, display formatter) so nothing else hard-codes labels.
3. `validation.py`:
   - one validator per rule in the table; return `ValidationError(code, message)` or the normalised value (e.g. phone → `+9665XXXXXXXX`);
   - `classify_contact_number(raw) -> ("mobile"|"landline", normalised) | error`;
   - cross-field checks: area range, rent min ≤ max and rent period required when rent is given;
   - document checks: allowed extensions and max size.
4. `draft_ops.py` (pure functions returning a new draft):
   - `write_fields(draft, [(key, value, source)]) -> (draft, written_keys, errors)`: user/default → confirmed, derived/verified → unconfirmed; `contact_number` → mobile or landline;
   - `confirm(draft, keys)`;
   - `add_document` / `remove_document`.
5. `rules.py`: `can_submit(draft) -> list[Blocker]` in the exact order of spec section 2, and `compute_phase(draft)`.
6. `summary.py`: `build_draft_summary(draft, master, changed_keys) -> DraftSummary`, matching the spec's JSON exactly. Area, rent and lease show as single rows. Also `prompt_summary(draft)` → the dynamic block text from `docs/agent-system-prompt.md`.
7. `master.py`: load `app/data/master_data.json` (create it now from spec section 9) into typed models with lookup helpers (`label_for`, `malls_in_city`, `unit_code`).

## Tests (`backend/tests/domain/`)
- Every validator: valid and invalid cases (CR, email, mobile/landline classification, Arabic script, VAT, national ID, area, rent).
- `write_fields`: provenance and confirmed flags; derived values stay unconfirmed; contact classification.
- `can_submit`: each blocker appears and disappears correctly, in order; a fully complete draft returns `[]`.
- `compute_phase`: one test per phase.
- `build_draft_summary`: snapshot test of the JSON for a half-filled draft.

## Acceptance criteria
- `pytest backend/tests/domain` is green, with ≥ 90% line coverage on `app/domain`.
- No FastAPI, LangGraph or I/O imports in `app/domain` (except reading the master data file in `master.py`).

## Verify
```
cd backend && uv run pytest tests/domain -q && uv run mypy app/domain
```
