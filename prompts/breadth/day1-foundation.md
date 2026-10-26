# Breadth Day 1 (Tue 27 Oct) — Foundation

Read first: @docs/DELIVERY-PLAN.md (sections 1, 2) @prompts/11c-pre-baseline-fixes.md @docs/specs/pre-baseline-fixes.md

## Goal
Corrected intake, CI that runs every layer we have today, and business rules in a policy file.

## Backend track (Claude's PRs — don't build these)
1. **Harness PR (morning):** Make targets `check`, `check-be`, `check-fe`, `test-be`, `test-fe`, `e2e-int` (alias `e2e`), `test-agent`, `eval-live`, `ci` (= check + test + e2e-int); `.github/workflows/ci.yml` with `backend`, `frontend` and `integration` jobs; `.github/pull_request_template.md` with the per-layer Testing table (testing strategy §5). The scripted job moves out of `e2e.yml`.
2. **Policy PR (after 11c merges):** step 17 items 1–5 (policy file, rules read from it, "Rules in force" prompt block, generated master data with Arabic names and regions, `MasterDataSource`). Keeps every existing mall and category id.

## Your track (Cursor)
Run `prompts/11c-pre-baseline-fixes.md` in full:
- confirm only values shown on an earlier confirm card;
- `documents_updated` action and the documents-complete turn;
- Office removed from seed data, FAQ and unit codes;
- landline 8 or 9 digits; `written_keys` de-duplicated;
- the doc and rule fixes.

## Tests
- Everything 11c lists.
- Because 11c changes the prompt: `scripts/eval_live.py` twice (no lower score than before) and one `@live` smoke run.

## End-of-day demo check
- [ ] The happy path in `docs/demo-script.md` works; the review card appears right after the second required upload.
- [ ] "office" is offered nowhere.
- [ ] `ci.yml` is green on the 11c PR.
- [ ] `docs/STATUS.md` §0: Day 1 ✅, rows 11c ✅ and 17 🟡 (demo depth) once the policy PR merges.
