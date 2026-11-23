# 18 Nov Day B3 (Fri 27 Nov): Property Details one question at a time

Read first: @docs/specs/demo-18nov-feedback.md (§2 rows NG8–NG10; §3.5; §4 ADR-N6; §8 M31, G7, G8) @docs/testing/demo-18nov-test-plan.md (§3 B3, §4, §5 NV06–NV07, §6 `property_sequence`, `mall_fuzzy`) @backend/app/agent/system_prompt_v2.md (Property Details) @backend/app/agent/bundles.py (`still_needed_line`) @frontend/src/components/cards/ReviewCard.tsx

## Goal
1. **One property question per turn**, in the order size → budget → lease length → start date → mall. Muzammil wants these before the mall so they can filter the malls later (unit matching, from 7 Dec) (N10, M31).
2. **"Flexible" or "not sure" is an answer.** It's never asked again, and none of the four blocks Submit. Anything given early is kept and skipped.
3. **A new field: desired start**, a month or "as soon as possible" (N11).
4. **The budget basis** (total or per square metre) is asked once when the figure doesn't say.
5. **Mall names are matched in code**, including misspellings. An ambiguous name gives buttons; an unknown one gives the mall picker (N12).

M31 is *to confirm* with Muzammil.

## Backend PR (Claude, MS10): merged first; use it, don't rebuild it
Contracts are folded into @docs/spec.md (rows marked "18 Nov B3").
- **Fields:**
  - `FieldKey.DESIRED_START` (`YYYY-MM` or `asap`, group `property`, optional);
  - `FieldKey.RENT_BASIS` (`total` | `per_sqm`, default `total`);
  - `InquiryDraft.flexible: list[Literal["area", "budget", "lease_period", "desired_start"]]`.
- **Tool `mark_flexible(items, evidence)`:** user's words only; the items aren't asked again.
- **Hint:** `bundles.still_needed_line` for `property_details` names one item, the first of area, budget, lease period, desired start and malls with no value and not flexible.
- **Mall matching:**
  - `MasterData.match_mall(text) -> MallMatch` (exact id, name or alias; Arabic; then `difflib` ratio ≥ 0.8); malls in master data gain `aliases`;
  - `update_draft` passes every `malls` entry through it: one → id; several → nothing written, a `choice` card for `malls` and the note `mall_ambiguous`; none → `mall_not_found` (then `show_mall_picker`, unchanged).
- **Downstream:** desired start and rent basis on the review card payload, the case brief (`app/domain/case_brief.py`) and the submission payload (`app/domain/payload.py`, Yardi mock `desired_start`).
- **e2e:** NV06, NV07 catalogue entries, scripts and specs (`nv06-property-one-at-a-time.spec.ts`, `nv07-mall-matching.spec.ts`).
- **Evals:** groups `property_sequence` and `mall_fuzzy` (English and Arabic) with their checks and unit tests.
- **Tests:** the B3 rows in the test plan §3.

## Your track (Cursor, MS11): the agent and the chat
1. **System prompt**, Property Details (line 34 today asks it all in one question):
   - Ask the item the hint names, one per turn, as an interviewer would: "Roughly how much space are you looking for?", "What's your budget for rent?", "How long a lease are you thinking of?", "When would you like to open?", then "Which mall would you like?".
   - If they give several at once, save them all (`update_draft`) and ask the next missing one. Never re-ask a saved or flexible item.
   - "Flexible", "not sure", "any" → `mark_flexible` with their words, then move on.
   - Budget without a basis ("250 per year"): ask once, "Is that the total rent, or per square metre?". Store the basis.
   - Start date: "January" → propose `2027-01` with a value button; "as soon as possible" → `asap`.
   - Malls: pass what they typed; on `mall_ambiguous`, point to the buttons; never guess an id. Never mention units (I9).
2. **Cards:**
   - `ReviewCard`: desired start ("January 2027", "As soon as possible") and "Flexible" for flexible items; budget with its basis.
   - `ChoiceCard` for `malls` (from B1, reused).
   - Vitest and a screenshot.
3. **Goldens** whose property turns change, re-recorded with the reason. `questions_per_section` for `property_details` rises by design: note it in `docs/eval-notes.md`.
4. **Live evals:** `make eval-live GROUP=property_sequence`, `GROUP=mall_fuzzy` (3/3, English and Arabic), then the full `make eval-live`.

## Tests
- Vitest and `make e2e-fe` for `ReviewCard`.
- `make e2e-nov18 ARGS='--grep "NV0[67]"'`, then the full `make e2e-int`.
- AGENT-LIVE: the two groups at 3/3; every other group within tolerance.

## End-of-day check
- [ ] "Around 40 sqm for three years" → both saved → asks the budget → "flexible" → asks the start → "January" → value button → asks the mall (NV06).
- [ ] "250 per year" → one question about the basis, then on.
- [ ] "mall of arbia" → Mall of Arabia saved, no picker; "riyadh mall" → buttons for the Riyadh malls; nothing saved until the tap (NV07).
- [ ] The review card shows "January 2027" and "Budget: flexible"; the case brief in the console shows the start date.
- [ ] `docs/STATUS.md` B3 row; tracker N10–N12 → Done; MS10, MS11 → Done.
