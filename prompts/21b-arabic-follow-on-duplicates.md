# Step 21b — Arabic safety nets, follow-on inquiries, duplicate check

Read first: @docs/specs/l3-reliable-intake.md (sections 3.10, 3.11, 3.12) @backend/app/domain/validation.py @backend/app/agent/confirm_policy.py @backend/app/agent/guard.py @backend/app/agent/contact_infer.py @backend/app/policy/ (from step 17)

**Start in plan mode:** show the digit normalisation point, the Arabic doubt and capture patterns, how a session moves to a follow-on inquiry (new inquiry, checkpoint thread, divider in the UI), and where the duplicate check runs. Wait for approval before writing code.

## Goal
The deterministic checks work as well in Arabic as in English; a second inquiry for another mall reuses everything already verified; and a likely duplicate is caught before it reaches a reviewer.

## Build
1. **Arabic (spec §3.10, Must).**
   - One `normalise_digits(text)` in `domain/validation.py` (Arabic-Indic and Eastern Arabic-Indic → ASCII), applied before every numeric rule and in `contact_infer`.
   - `confirm_policy.py`: Arabic doubt phrases; cover every derived field, not only unit type and sales category.
   - Guard capture heuristics recognise Arabic business words and names.
   - Add an Arabic happy-path script and golden transcript to `tests/parity/`; add an "Arabic" scenario to `scripts/eval_live.py`.
2. **Follow-on inquiries (spec §3.11, Should).**
   - Tool `start_follow_on(mall_id?)`, allowed only when the current inquiry is submitted.
   - Creates a new inquiry with `follow_on_of`, moves the session to it (new checkpoint thread seeded with a one-line summary note), and copies company, brand, unit type, sales category and contact as `verified`, unconfirmed, in one confirm card titled "Same details as <reference>".
   - Carries `email_verified` and `mobile_verified` when unchanged and within `follow_on_reuse_hours`; copies Company Profile and Brand Profile by reference.
   - Note `follow_on_started from=<ref>`; the prompt asks only for the new mall and space details.
   - Frontend: a divider "New inquiry" in the chat; a **Start another inquiry** button on the status page (uses the `track` token).
3. **Duplicate check (spec §3.12, Should).**
   - `InquiryIndex.find_open(mall_id, cr_number, company_norm, brand_norm)` over the inquiry store.
   - Runs on `verification_complete`; notes `duplicate_own reference=<ref>` or `duplicate_other`; sets `possible_duplicate_of`.
   - `duplicate_policy: block` adds a `duplicate_open` blocker to `can_submit`.
   - Prompt: never reveal another applicant's reference or contact.
4. Fold the contract changes into `docs/spec.md`; update `docs/STATUS.md` (row 21b).

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE, AGENT-DET (Arabic golden), FE (follow-on divider, status-page button), INT (stories S4–S6). AGENT-LIVE (new `arabic` group) and E2E-LIVE (S4, S5 live).
- `tests/arabic/`: digits in CR, phone, VAT, area and rent; Arabic doubt keeps the field unconfirmed; Arabic capture triggers the guard note; Arabic mall names match.
- `tests/follow_on/`: copied fields are `verified` and unconfirmed; verification carries over only within the window and when unchanged; documents are referenced, not duplicated; a follow-on from a draft inquiry is refused.
- `tests/duplicates/`: own vs other contact; `warn` vs `block`; the other applicant's details never appear in the note or reply.
- **Playwright:** stories S4, S5 and S6 (spec §3.13).

## Acceptance criteria
- Gate E8 passes.
- A follow-on reaches `submitted` in two typed messages in the scripted story.
- Parity suite green (Arabic golden added).

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/arabic tests/follow_on tests/duplicates tests/parity -q && cd .. && make e2e
```
