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
- Policy `public_cr_check`. **The backend PR ships it as `lookup`**, so `main` keeps working with today's prompt and goldens. Your PR flips it to `ask_then_sign_in` (step 0 below).
- `app/agent/cr_question.py`:
  - `cr_question_active(assisted=, channel=)` is true only on the self-service channel under `ask_then_sign_in`, so staff keep the lookup (D3);
  - `scrub_cr_numbers(text) -> (text, found)` replaces a CR-format number with `[CR number removed]`. It matches ten digits not starting with 0, and Arabic-Indic digits too;
  - `apply_cr_answer(draft, has_cr)`: Yes gives `cr_status = "existing"` with no number stored; No gives `cr_status = "skipped"`, the existing skip path. Both statuses were reused so `compute_phase`, `can_submit` and form mode don't change.
- Card `cr_question` (`build_cr_question_card()` in `app/api/channel_cards.py`), payload `{prompt, yes_label, no_label, answered: "yes" | "no" | null}`. Under `ask_then_sign_in`, `POST /api/sessions` returns it in place of the welcome quick replies. The second welcome bubble reads "…To start, does your company have a CR?".
- UI action `cr_answer {has_cr: bool}`:
  - **Yes:** the card is re-sent as answered, plus `sign_in_prompt` (reason `has_cr`, new wording, `sign_in_url` = `<PUBLIC_BASE_URL>/tenant`, which opens Leasing Opportunities after sign-in). Also audit `inquiry_redirected {reason: has_cr}` and `Session.closed = "redirected_to_sign_in"`. Note: `[ui_event] cr_answer yes`.
  - **No:** note `[ui_event] cr_answer no`.
  - Otherwise: `cr_already_done`, `cr_answer_invalid` (payload not a boolean), or `cr_answer_off` (lookup policy or a staff chat).
- Tool `record_cr_answer(has_cr)` runs the same steps when they answer in words. It's in `TOOLS` and not in `ASSISTED_TOOLS`. Under `ask_then_sign_in`, `verify_cr` and the form-mode `cr_check` card on the public page check nothing: they say lookups are off.
- Chat endpoint: on the public page, every typed message is scrubbed before the transcript, the audit, the router and the model see it. A scrubbed number counts as Yes: the sign-in card is streamed, and the turn gets the note `[guard] cr_number_typed` (`CR_TYPED_NOTE` in `cr_question.py`, text included).
- The bundle hint under `ask_then_sign_in` says "ask whether the company has a CR, pointing to the card's buttons. Never ask for the CR number."
- Invariant `I8` (INV8) in `app/agent/invariants.py`, wired into `scripts/eval_live.py`. It flags a CR number, or a company name or address from the mock CR registry that the applicant didn't type, in self-service replies or card payloads.

**Lease Admin (spec §3.2)**
- `ReviewRole` gains `lease_admin`; `policy.first_level_review_role: lease_admin`; `ReviewQueue.first_role`, `role_for(level)` and `roles`.
- `REVIEW_LEVEL` in `machine.py` is built from the transition table. Rows from `first_review` and `reupload_requested` are first level, plus anything listed in `FIRST_LEVEL_EVENTS`, which is empty now and gets R2's document and contact events. `_check_actor` picks the role by level.
- `reviewers.json` gains `lease_admin-central`, `-western`, `-eastern` and `-manager`.
- Both roles see the case in their queue. Each sees only the actions for its own level.
- Notifications:
  - `review_assigned` goes to the Lease Admin at routing;
  - it goes to the final reviewer at `approved_first` (effect `review_assigned_final`);
  - `reupload_received` goes to the Lease Admin.
- Approval email (F7): `review_assigned` is now `action_required`, with subject "Inquiry for approval: {brand} at {mall} ({reference})". The body names the stage, and the link is `/review/cases/{reference}?as=<reviewer id>` (`?as=` only with dev tools). `ReviewCasePage` reads `?as=`, signs that mock reviewer in and drops the parameter.
- Brief, status page and Needs attention name the role of the level that's waiting.
- Tests written before R1 run with `first_level_review_role: null`, as they were written (autouse fixture in `tests/conftest.py`). Tests marked `lease_admin` run with the shipped policy.
- Playwright: `reviewerFor(request, reference, level = 'first' | 'final')` and `openCaseAs(page, reviewer, reference)`. T1, A1, the console spec and the demo spec switch to the RLM at final review.

**Document review service (spec §3.3)**
- `app/services/document_review.py`: the `DocumentReviewService` protocol and `MockDocumentReviewService`, driven by file name:
  - `expired` gives 30 days ago;
  - `soon` gives today plus 7 days;
  - anything else gives today plus 365 days;
  - `timeout` and `unavailable` raise the matching outage.
- The upload endpoint calls it through the gateway (service `document_review`) for company and brand profiles only. It stores `DocumentRef.review` (`{status, expiry_date, fields, checked_at}`, typed values only) and audits `document_reviewed {doc_type, status, has_expiry}`. An outage stores `pending`, and the upload still succeeds.

**Tests in the backend PR**
- `tests/agent/test_cr_question.py`: scrubber, policy and channel, tool lists, both answers, `verify_cr` off, hint, I8.
- `tests/api/test_cr_question_api.py`: welcome card, Yes, No, a bad payload, a typed CR number never kept, `cr_check` off.
- `tests/lifecycle/test_review_levels.py` (`lease_admin`): every reviewer row has a level, routing, the approval email and its link, first level for the Lease Admin only, final level for the RLM only, and the brief role.
- `tests/services/test_document_review.py` (`contract`) and `tests/security/test_document_text_isolation.py`.

## Your track (Cursor): agent and chat
0. **Flip the policy:** `public_cr_check: ask_then_sign_in` in `backend/app/policy/policy.yaml`, in the same PR as items 1–7 (the prompt, card and goldens have to change together).
1. **`CrQuestionCard`** (`frontend/src/components/cards/`):
   - two buttons sending `cr_answer {has_cr: true | false}`; when `answered` is set, both are disabled and the chosen one is marked, like `ExistingCrChoiceCard`;
   - add `cr_question` to the `CardType` union and the payload type `{prompt, yes_label, no_label, answered: 'yes' | 'no' | null}`;
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
3. **Guard:** use `contains_cr_number` from `app/agent/cr_question.py`. If the model's reply contains a CR-format number on the self-service channel, retract and retry once, with the note `[guard] cr_number_in_reply` (same pattern as the other guard retries).
4. **Playwright `rd-cr-question`** (`@scripted`, it needs the card): Yes → sign-in card → `/tenant` → Leasing Opportunities; No → company questions; a typed number → sign-in reply, and the number isn't in the draft panel, SSE events or `GET /api/dev/audit/{id}`. Scripts go in `backend/tests/e2e_scripts/`, regenerated with `generate_e2e_scripts.py`.
5. **Goldens:** re-record the goldens that start with a CR lookup under `ask_then_sign_in` (`make golden`). Their `lookup` versions stay as `*-lookup` goldens, and the frontend fixtures are re-exported.
6. **Live eval group `cr_privacy`** in `scripts/eval_live.py`, with the five scenarios in spec §6. `I8` already runs on every eval turn (`public_cr_question` is set from the session); add `I8` to `e2e/support/invariants.ts`.
7. **Prompt snapshot:** update it, with the reason in the PR.

## Tests
- Vitest for `CrQuestionCard`; `make e2e-fe`.
- `make e2e-int`: `rd-cr-question` passes; S1–S3, S13, S14, T1, T2 and the `a2-*` suites still pass.
- AGENT-LIVE: `cr_privacy` ×3 at 3/3, plus `intake` (which holds the routing and out-of-order scenarios) and `channels` within tolerance of the step 12 baseline. Run one group with `GROUP=<name> make eval-live`.
- E2E-LIVE smoke: one self-service persona, with I8 on.

## End-of-day check
- [ ] New chat → "Do you have a CR?" card. **Yes** → sign-in card → `/tenant` → Leasing Opportunities. **No** → company and brand questions.
- [ ] Type "my CR is 1010000000": sign-in reply, and the number appears in neither the draft panel, the SSE events nor the audit (`GET /api/dev/audit/{id}`).
- [ ] Call-centre console: an executive enters a CR exactly as before (`a2-existing-cr` passes).
- [ ] Submit a no-CR inquiry → "Inquiry for approval" email in the dev inbox → its link opens the case for the **Lease Admin**. It's not in RLM's queue, and RLM opening it gets `not_in_queue`.
- [ ] Upload `brand_profile.pdf` → `GET /api/dev/audit/{id}` shows the `document_review` call and an expiry date.
- [ ] `docs/STATUS.md` Re-demo R1 ✅; `docs/spec.md` updated (spec §7, R1 row); tracker I2, I3, I8, I13 set to Done.
