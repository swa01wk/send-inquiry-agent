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

## Backend PR (Claude): merged first; use it, don't rebuild it
Contracts are in @docs/spec.md §16 (and §4, §7, §9 rows marked flow v2). Everything sits behind **`flow_v2_intake.enabled: false`** in `policy.yaml`; scripted scenarios named `flow-v2-s…` (not S18–S24) already run v2.
- **Policy and master data:**
  - `flow_v2_intake: {enabled, product_lines: [store, office], max_malls: 5, pending_inquiry_ttl_minutes: 120, terms_before_documents: true}`;
  - on a v2 inquiry `get_policy()` returns the v2 view (`product_lines`, `max_malls_per_inquiry: 5`, `public_cr_check: verify_or_skip`);
  - `review_routing.office: rlm_store`; master unit `office` (`OFF`); `GEO-OFF-…` references.
- **`InquiryDraft.intake_flow`** (`v1`/`v2`), set at session creation (`cr_question.flow_v2_intake_for`).
- **Company Registration** (`app/agent/cr_check.py`): `check_existing_customer`, `skip_customer_check`; `cr_check {cr_number}`, `cr_skip {}` then `cr_skip {confirmed: true}`; a typed CR is scrubbed and checked before the graph. Notes: `cr_checked registered|not_registered`, `cr_invalid <code>` (quiet), `service_error cr <kind>` (quiet), `cr_skip_confirm_shown` (quiet), `cr_skipped`. Registered → `sign_in_prompt` and `Session.closed`. Not registered → `cr_status: new`, nothing prefilled.
- **Welcome (v2):** `company_registration` card + quick replies "Continue my inquiry" (`action: resume_pending`, placeholder "Your email address") and "What do I need to get started?".
- **Sections** (`app/domain/sections.py`): `IntakeSection`, `SECTION_OF`, `current_section`; `DraftSummary.section`, `checks.sections`; `can_submit` and `remaining_steps` in section order; `next_bundle_hint` / `still_needed_line` name the current section only; guard rule 8 (`_later_section_ask_note`) and the verification nudge (`_v2_missing_verification_note`).
- **Sales Category:** `update_draft` refuses a derived category from the brand alone: `category_needs_what_you_sell`.
- **Terms:** `terms` card (guard shows it before documents) and `accept_terms`; `ReviewPayload.terms_on_own_card`.
- **Pending inquiry:** `InquiryStatus.PENDING` (repository sets it on save; no `CaseStatus.PENDING`: there is no case before submit); `pending_by_email`, `expire_pending` (purge loop + lazily on resume); `resume_pending {email}` → fixed reply `RESUME_PENDING_REPLY`, **no agent turn**, `resume_link` email whose link is the verify link.
- **Flow steps:** `start`, `raise_tp`, `chk_tp`, `db`, `exist`, `display`, `redirect`, `emv`, `succ1`.
- **Invariants:** I8 on the v2 public chat; I9 (no unit named before submit). `eval_live` passes `flow_v2_intake`.
- **Tests:** `tests/api/test_flow_v2_intake.py`, `tests/api/test_pending_resume.py`, `tests/store/test_pending_inquiry.py`, `tests/domain/test_section_order.py`, `tests/agent/test_flow_v2_intake_rules.py` (pytest marker `intake_v2` switches it on).
- **Not in the backend PR (after yours):** the catalogue runner for S1–S17 and Playwright `tests/flow-v2/s01`…`s17`; they need your cards and scripts. Claude adds them once your PR is up.

## Your track (Cursor): the agent and the chat
0. **Flip the switch:** `flow_v2_intake.enabled: true` in `backend/app/policy/policy.yaml`, in the same PR as the prompt, cards and scripts. Then fix tests that assumed the v1 welcome on self-service (mark them for v1 or update them).
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
   - `CompanyRegistrationCard` (payload in spec §7): input, Verify, Skip, inline confirm (`skip_confirm`), `state`, masked CR, error. Updates in place (card id `company_registration`).
   - Quick reply `action: "resume_pending"`: show an email field in place; on send, post the `resume_pending {email}` action (never a chat message).
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
