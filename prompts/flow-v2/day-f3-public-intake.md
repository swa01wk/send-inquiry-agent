# Flow v2 Day F3 (Mon 16 Nov): public intake in the app's order

Read first: @docs/specs/flow-v2-alignment.md (§2 rows FV1, FV9–FV15, §3.1, §3.2, §3.3, §4 ADR-V4) @docs/testing/flow-v2-test-plan.md (§4, §5, §6) @docs/flow-v2/scenarios.json (S1–S15, S17) @backend/app/agent/system_prompt.md @backend/app/agent/bundles.py @backend/app/agent/guard.py

## Goal
The public chat follows the chart and the app:
1. **Company Registration:** Verify or Skip; Skip asks "Are you sure you want to proceed without CR ID?". A registered CR goes to sign in with one line.
2. **Unit Type** (Store or Office) and **Sales Category**, from "what do you sell?".
3. **Basic Info**, then email and mobile verification. When verification succeeds, a pending inquiry is saved.
4. **Property Details:** up to 5 malls; no units shown.
5. Terms and privacy consent.
6. Documents.
7. Submit.

The agent helps fill each section conversationally and still takes answers given early, but asks one section at a time.

## Backend PR (Claude): lands first; use it, don't rebuild it
- **Policy and master data:**
  - `public_cr_check: verify_or_skip`;
  - `product_lines: [store, office]`, `review_routing.office: rlm_store`;
  - `max_malls_per_inquiry: 5`, `pending_inquiry_ttl_minutes: 120`, `terms_before_documents: true`;
  - master unit `office` (`OFF`, via `scripts/generate_master_data.py`);
  - reference and router regex with `OFF`.
- **Company Registration** (`app/agent/cr_check.py`):
  - `check_existing_customer`;
  - `cr_check` and `cr_skip {confirmed}` on self-service;
  - a typed CR is scrubbed and checked before the graph;
  - notes `cr_checked registered|not_registered`, `cr_invalid`, `cr_skip_confirm_shown`, `cr_skipped`;
  - `company_registration` card (deterministic), I8 updated.
- **Sections:**
  - `bundles.IntakeSection`, `SECTION_OF`;
  - `DraftSummary.section`, `checks.sections`;
  - `remaining_steps` and `can_submit` order;
  - `still_needed_line` names one section;
  - guard rule 8 `_later_section_ask`;
  - `_missing_send_verification_note` fires once Basic Info is done.
- **Sales Category:** `update_draft` error `category_needs_what_you_sell`.
- **Terms:** `terms` card and `accept_terms` action; the review card shows "Terms accepted".
- **Pending inquiry:**
  - `InquiryStatus.PENDING`, `CaseStatus.PENDING`, `verification_succeeded`, `expired` from `pending`;
  - `submit_failed` back to `pending`;
  - proactive expiry;
  - `resume_pending {email}` with a neutral reply and the `resume_link` email;
  - welcome quick reply "Continue my inquiry".
- **Space bundle:** unit cards removed; mall picker `max_select: 5`.
- **Flow steps:** `start`, `raise_tp`, `chk_tp`, `db`, `exist`, `display`, `redirect`, `emv`, `succ1`, `complete1`, `ref1`.
- **Tests:**
  - `tests/agent/test_company_registration.py`, `test_section_order.py`, `test_unit_category.py`;
  - `tests/lifecycle/test_pending_inquiry.py`;
  - `tests/api/test_pending_resume.py`, `test_terms_before_documents.py`;
  - validation and routing;
  - catalogue runner S1–S17;
  - Playwright `tests/flow-v2/s01`…`s15`, `s17` and the regression scripts in spec §5.3, re-scripted for the order.
- `docs/spec.md`: F3 row of spec §7; §1 flow summary, §2 field keys (`malls`), §3 tools, §4 actions, §7 cards, §9 policy.

## Your track (Cursor): the agent and the chat
1. **System prompt** (`system_prompt.md`, the "Rules in force" and "Ask next" blocks):
   - Sections in the app's order, one section per turn, conversational: offer to take several values in one message, never a field-by-field interrogation.
   - Company Registration:
     - ask for the CR or offer Skip via the card;
     - never repeat a CR;
     - on `cr_checked registered`, say "You're already registered with us — please sign in" in one line and stop (E1);
     - on `not_registered`, move to Unit Type.
   - Unit Type: offer Store and Office as quick replies; explain them in one line if asked.
   - Sales Category: ask "What do you sell?", map to the list, confirm on a card. Never set it from the brand alone ("Max" → ask).
   - Basic Info: name, company name and address, brand (EN and AR; propose the Arabic, confirm), email, mobile or office landline. Then point to the verification card.
   - After verification: one line ("Your details are saved — let's add the property details"), then Property Details. At least one mall, several allowed; never mention units or unit numbers (I9).
   - Terms, then documents, then the review card.
   - "Continue my inquiry": ask for the email, point to the button; the reply is the same either way.
2. **Cards:**
   - `CompanyRegistrationCard`: input, Verify, Skip, inline confirm, masked CR, error.
   - `TermsCard`: checkbox → `accept_terms`.
   - `ReviewCard`: shows "Terms accepted" when `terms_before_documents`.
   - Step tabs: read `checks.sections`.
   - Remove `CrQuestionCard` from the self-service path (keep it for `ask_then_sign_in`).
   - Vitest, `@fe` scenarios, screenshots.
3. **Guard copy:** the note for rule 8 ("Ask about <section> first") and the verification nudge.
4. **Scripts:** `flow-v2-s01.json` … `flow-v2-s17.json` (intake), regenerated with `scripts/generate_e2e_scripts.py --flow-v2`; re-record the regression scripts in spec §5.3.
5. **Goldens:** `make golden`; new `flow-v2-s01`, `flow-v2-s10`, `flow-v2-s13`; re-recorded ones listed with the reason in the PR.
6. **Live eval:** `flow_v2` S1–S17 with the test plan §5 checks; KPI `questions_per_section`; re-run `intake`, `cr_privacy` (now I8 as changed), `document_extract`.

## Tests
- Vitest and `make e2e-fe` for the new cards.
- `make e2e-int ARGS='--grep "S([1-9]|1[0-7]) "'`, then the full `make e2e-int`.
- AGENT-LIVE: `flow_v2` S1–S17 ×3 at 3/3; `intake` within tolerance.
- E2E-LIVE smoke: S1, S3.

## End-of-day check
- [ ] Skip → confirm → Unit Type (Store/Office) → "we sell coffee" → category confirmed → Basic Info → verification card → pending inquiry in `GET /api/dev/flow/<session>` → Property Details with two malls → terms → documents → Submit → `GEO-STR-…` (S1, S12).
- [ ] `1010000000` → one line + sign-in card; nothing else asked (S3).
- [ ] `101012345` → asked again, still at Company Registration (S5).
- [ ] Office → `GEO-OFF-…`, routed to the Regional Sales Manager (S10).
- [ ] Leave after verification, come back within 2 h with "Continue my inquiry" → resume link → chat resumes at Property Details; after 2 h → abandoned (S9).
- [ ] Submit fault → back to pending → retry → one reference (S17).
- [ ] `docs/STATUS.md` F3 row; tracker V1, V2, V10, V11, V12, V13, E1 → Done; S1–S15, S17 → In review.
