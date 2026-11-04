# Re-demo Day R1 (Thu 5 Nov): "Do you have a CR?", Lease Admin and the approval email, document review service

Read first: @docs/specs/demo-feedback.md (§1, §2 rows D1–D4, D9 and D14, §3.1–3.3, §4, §6) @docs/assumptions.md (Demo feedback assumptions) @docs/spec.md @docs/agent-system-prompt.md @prompts/feedback/README.md

## Goal
The public chat opens with "Do you have a CR?":
- **Yes** goes to sign-in, landing on Leasing Opportunities.
- **No** carries on in chat.
- The public page never asks for, accepts, looks up or repeats a CR number.

Every new case lands in the Lease Admin's queue for first-level review, with an "Inquiry for approval" email that opens the case (F7). RLM or RPLM review it after that. Company and brand profiles are sent to a document review service, and its expiry date is stored on the document.

## Backend PR (Claude): lands first; use it, don't rebuild it

**CR question (spec §3.1)**
- Policy `public_cr_check: ask_then_sign_in` (default). `lookup` keeps today's behaviour for old goldens and tests.
- Card `cr_question`, built by `build_cr_question_card()` in `app/api/channel_cards.py`, with payload `{prompt, yes_label, no_label, answered?: bool}`. `POST /api/sessions` returns it with the welcome message on the self-service channel. It takes the place of the welcome quick-reply chips there.
- UI action `cr_answer {has_cr: bool}` in `handle_ui_action`:
  - **Yes:** `sign_in_prompt` card (new wording, `sign_in_url` = `<PUBLIC_BASE_URL>/tenant/opportunities`), audit `inquiry_redirected {reason: "has_cr"}`, session `redirected`. Note: `[ui_event] cr_answer yes`.
  - **No:** `draft.cr_status = "none"`; company name and address become required basic info. Note: `[ui_event] cr_answer no`.
- Tool `record_cr_answer(has_cr: bool)` runs the same handler. It's in the new `SELF_SERVICE_TOOLS` list. `verify_cr` and `skip_cr` are removed from self-service, and `ASSISTED_TOOLS` is unchanged.
- `app/agent/cr_question.py`, `scrub_cr_numbers(text) -> (text, found: bool)`:
  - runs on every self-service user message before history and audit;
  - replaces a CR-format number (ten digits, Arabic-Indic digits included) with `[CR number removed]`;
  - when it finds one, the turn gets the note `[guard] cr_number_typed` and the sign-in card is attached.
- Invariant `I8` (INV8) in `app/agent/invariants.py`: no CR number, and no company name or address from a CR lookup, in self-service assistant text or cards.

**Lease Admin (spec §3.2)**
- `ReviewRole` gains `lease_admin`.
- `policy.first_level_review_role: lease_admin`; `ReviewQueue.first_role`.
- `EVENT_LEVEL` in `machine.py`, with `_check_actor` choosing the role by level.
- `reviewers.json` gains a Lease Admin per region and a manager.
- Notifications: `review_assigned` goes to the Lease Admin at routing and to the final queue at `approved_first`.
- Approval email (F7, spec §3.2): the routing email reads "Inquiry for approval: {brand}, {mall}" and links to `/review/cases/{reference}?as=<reviewer id>`. With dev tools on, `?as=` signs in that mock reviewer and opens the case. `e2e/support/outbox.ts` gets a helper to open it.
- Console:
  - the queue filters by the signed-in role's level;
  - stage labels: "First review — Lease Admin" and "Final review — RLM / RPLM";
  - `/dev` gains a Lease Admin persona.
- `e2e/support/submit.ts`: `reviewerFor(request, reference, level?)` returns the Lease Admin by default and the RLM or RPLM with `level: 'final'`.

**Document review service (spec §3.3)**
- `app/services/document_review.py`:
  - `DocumentReviewService` protocol and `MockDocumentReviewService`, driven by file name: `*expired*` gives 30 days ago, `*soon*` gives today plus 7, anything else gives today plus 365. Dates come from the app clock.
  - registered in `services/container.py` and called through the gateway after a company or brand profile upload;
  - the result goes on `DocumentRef.review`, and a timeout or outage gives `status: "pending"`.
- Contract tests: `tests/services/test_document_review.py` (`-m contract`).
- Isolation test: `tests/security/test_document_text_isolation.py`.

**Tests in the backend PR**
- `tests/agent/test_cr_question.py`: the scrubber, the action, the tool list per channel, audit redaction.
- `tests/api/test_cr_question.py`.
- `tests/lifecycle/test_review_levels.py`: a wrong-role case for every reviewer event.
- `tests/lifecycle/test_effects.py`: the approval email goes once, to the Lease Admin of the region, with a working link (D14).
- Updated T1/T2 and the console specs.
- Playwright `rd-cr-question` (`@scripted`), with its scripts in `backend/tests/e2e_scripts/`.

## Your track (Cursor): agent and chat
1. **`CrQuestionCard`** (`frontend/src/components/cards/`):
   - two buttons sending `cr_answer`; once answered, both are disabled and the chosen one is marked, like `ExistingCrChoiceCard`;
   - add it to `CardSlot` and to `src/types/contracts.ts`;
   - Vitest, plus an `@fe` scenario and a card screenshot.
2. **Intake prompt** (`backend/app/agent/system_prompt.md`, mirrored in `docs/agent-system-prompt.md`):
   - Remove "Company — the CR number … through `verify_cr`" and the `verify_cr` and `skip_cr` tool notes from the self-service prompt. Keep them in the assisted prompt.
   - The opening asks one question: whether the company has a CR. It points to the card and never asks for the number. Replace the example first reply ("Do you have your company's CR number? It lets me pull in your company details…").
   - On a typed yes or no, call `record_cr_answer`.
   - On `[ui_event] cr_answer yes` or `[guard] cr_number_typed`, say in one or two warm sentences that signing in is quickest, because their company details are already on file there. Point to the button, never repeat a number, and stop collecting.
   - On `[ui_event] cr_answer no`, carry on with the company bundle: company name and address together, then brand and space.
   - Under "Rules in force", replace "Existing tenants (the CR already has a Tenant Central account)…" with the self-service rule above. The assisted rule stays.
   - Never say whether a CR, company or person is known to Cenomi.
3. **Guard:** if the model's reply contains a CR-format number on the self-service channel, retract and retry once, with the note `[guard] cr_number_in_reply` (same pattern as the other guard retries).
4. **Scripted mode:** scripts for `rd-cr-question` (yes, no, typed number), regenerated with `generate_e2e_scripts.py`.
5. **Goldens:** re-record the goldens that start with a CR lookup under `ask_then_sign_in` (`make golden`). Their `lookup` versions stay as `*-lookup` goldens, and the frontend fixtures are re-exported.
6. **Live eval group `cr_privacy`** in `scripts/eval_live.py`, with the five scenarios in spec §6. Add `I8` to `e2e/support/invariants.ts`.
7. **Prompt snapshot:** update it, with the reason in the PR.

## Tests
- Vitest for `CrQuestionCard`; `make e2e-fe`.
- `make e2e-int`: `rd-cr-question` passes; S1–S3, S13, S14, T1, T2 and the `a2-*` suites still pass.
- AGENT-LIVE: `cr_privacy` ×3 at 3/3, plus `intake` (which holds the routing and out-of-order scenarios) and `channels` within tolerance of the step 12 baseline. Run one group with `GROUP=<name> make eval-live`.
- E2E-LIVE smoke: one self-service persona, with I8 on.

## End-of-day check
- [ ] New chat → "Do you have a CR?" card. **Yes** → sign-in card → `/tenant/opportunities`. **No** → company and brand questions.
- [ ] Type "my CR is 1010000000": sign-in reply, and the number appears in neither the draft panel, the SSE events nor the audit (`GET /api/dev/audit/{id}`).
- [ ] Call-centre console: an executive enters a CR exactly as before (`a2-existing-cr` passes).
- [ ] Submit a no-CR inquiry → "Inquiry for approval" email in the dev inbox → its link opens the case for the **Lease Admin**. It's not in RLM's queue, and RLM opening it gets `not_in_queue`.
- [ ] Upload `brand_profile.pdf` → `GET /api/dev/audit/{id}` shows the `document_review` call and an expiry date.
- [ ] `docs/STATUS.md` Re-demo R1 ✅; `docs/spec.md` updated (spec §7, R1 row); tracker I2, I3, I8, I13 set to Done.
