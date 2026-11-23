# 18 Nov Day B1 (Wed 25 Nov): buttons that carry values, and the leasing team's voice

Read first: @docs/specs/demo-18nov-feedback.md (§2 rows NG1–NG5, NG17, NG18; §3.1, §3.2, §3.3, §3.4 "No link in the chat", §3.8; §4 ADR-N1–N3) @docs/testing/demo-18nov-test-plan.md (§3 B1, §4, §5 NV01–NV02, §6 `category_options`, `leasing_team_tone`) @backend/app/agent/system_prompt_v2.md @frontend/src/components/cards/ConfirmFieldsCard.tsx @frontend/src/components/cards/VerificationCard.tsx @frontend/src/components/chat/CardSlot.tsx

## Goal
1. **Unit type** offers Store, Office, Media and Specialty (N1, M34).
2. **Sales category** is chosen from option buttons built from master data, never derived and confirmed with "Looks right" (N3).
3. **No "Looks right" anywhere.** Each confirm row shows its value as its own button, plus Change (N4, M27).
4. **The agent speaks as the leasing team**, opens Basic Info with "Tell me a bit more about you and your company" and an example, and never announces the next section (N2, N5, N6, M28).
5. **No verification link in the chat** (N7).
6. The first-approval email stops calling the tenant "qualified" (N13).

## Backend PR (Claude, MS6): merged first; use it, don't rebuild it
Contracts are folded into @docs/spec.md (rows marked "18 Nov B1").
- **Policy and master data:**
  - `flow_v2_intake.product_lines: [store, office, media, specialty]`;
  - `flow_v2_intake.examples` (`what_you_sell`, `office_business`, `basic_info_answer`), read into Rules in force;
  - master `sales_category_groups` (`fnb`, `retail`, `beauty`, `entertainment`, `services`, each with `label`, `label_ar`, `categories`); `label_ar` on every category.
- **`choice` card** (`build_choice_card` in `app/api/cards.py`): payload `{key, prompt, options: [{value, label, label_ar}], lang, chosen}`, card id `choice-<key>`.
- **Tool `show_category_options(candidates, evidence)`:** drops unknown ids, expands groups, max 4, keeps order; `no_category_match` when empty; still refuses brand-only evidence (`category_needs_what_you_sell`).
- **Actions:**
  - `choose_option {card_id, key, value}`: value must be on the card; writes `source: user`, `confirmed: true`; note `[ui_event] option_chosen <key>=<value>`;
  - `confirm_field {card_id, key}`: confirms one key; note `[ui_event] fields_confirmed <key>`. `confirm_card` stays accepted, but no card sends it.
- **Exact typed option:** a typed message that exactly names one option (English or Arabic, case and spaces ignored) is handled as `choose_option` before the graph.
- **`Session.lang`:** set by code from the last typed message (the check `guard._wrong_language_note` uses); the `choice` card reads it.
- **`confirm_fields` payload:** each row gains `value_label` (the value as the button shows it); the card-level confirm is gone.
- **Verification card:** no `demo_token` in any mode. `Settings.email_link_demo`, `AgentRuntime.email_demo_token`, `EMAIL_LINK_DEMO` in `.env.example` and `e2e/playwright.config.ts` are removed.
- **Guard rule 9 `_third_person_team`:** "our leasing team" or "the leasing team will" in a self-service or case reply → one route-back. The note text is a placeholder for you to word.
- **Template:** `first_level_approved.txt` without "qualified tenant".
- **e2e helpers:**
  - `steps.ts` `verify_email` and `InquiryPage.verifyEmail` open `completeVerifyLink(outbox)` through `POST /api/verifications/email`;
  - new steps `choose_option`, `confirm_field`;
  - `confirmSection` taps each row's value button. Older stories that clicked "Looks right" or the demo link are fixed here.
- **Catalogue and stories:** NV01, NV02 entries; `scripts/flow_v2_e2e_compile.py` handles NV ids; scripts `flow-v2-nv01.json`, `flow-v2-nv02.json`; `e2e/tests/demo-18nov/nv01-media-category-buttons.spec.ts`, `nv02-arabic-buttons.spec.ts`, against the test ids in the test plan §4.
- **Evals:** groups `category_options` and `leasing_team_tone` in `scripts/eval_live.py` (English and Arabic), checks in `app/agent/eval_checks.py`, unit tests in `tests/flow_v2/test_eval_checks.py`.
- **Tests:** the B1 rows in the test plan §3.

## Your track (Cursor, MS7): the agent and the chat
1. **System prompt** (`system_prompt_v2.md`, the section lines and the examples at lines 32, 123 and 129):
   - **Unit Type:** offer the four product lines from Rules in force as quick replies (`suggest_replies`), in the chat's language. One line each if asked what they mean.
   - **Sales Category:** after the unit type, ask in the M28 wording with the policy's examples (Office: "What does the company do?"). Then call `show_category_options` with candidates from what they said they sell. With a broad answer, pass the group. Never write `sales_category` yourself. After `option_chosen`, move on without repeating it.
   - **Basic Info:** open with "Tell me a bit more about you and your company: your name, the company name and address, your brand, an email and a phone number", then show the policy's example answer once.
   - **Voice:** you are the leasing team. Never "our leasing team will contact you" or "who should our leasing team contact"; say "we'll contact you". Never announce the next section ("we'll move to the mall"); ask the next question as an interviewer would.
   - **Confirming:** point to the value buttons ("tap your name to confirm it, or Change"); never "tap Looks right".
   - **Verification:** say where the link went; never offer to open it here.
2. **Cards:**
   - `ChoiceCard` (new): options as buttons, Arabic labels and `dir="rtl"` when `lang` is `ar`, chosen state, posts `choose_option`. Register in `CardSlot.tsx`.
   - `ConfirmFieldsCard`: remove "Looks right" (line 45); each unconfirmed row gets a value button (`value_label`, posts `confirm_field`) and Change (`edit_field`); confirmed rows show a tick.
   - `VerificationCard`: remove the demo link button and its waiting state (line 140); keep the status text and Resend.
   - Test ids from the test plan §4. Vitest; `@fe` specs `cards-choice`, `cards-confirm-fields`, `cards-verification`; new screenshot baselines (`e2e.yml` suite `fe` with `update_snapshots`).
3. **Guard copy:** rule 9's note ("Speak as the leasing team: say 'we', not 'our leasing team'").
4. **Scripts and goldens:** re-record the intake goldens whose wording changes (`make golden`), with the reason in the PR.
5. **Switch on what MS6 left off** (so MS6 could merge with today's frontend):
   - Policy `flow_v2_intake.category_from_options_only: true` (then `update_draft` refuses `sales_category` on a v2 inquiry, and Rules in force says so).
   - Remove `test.fixme` from `e2e/tests/demo-18nov/nv01-*.spec.ts` and `nv02-*.spec.ts`.
   - Prompt text: `system_prompt_v2.md` lines 32, 123 and 129 still say "our leasing team"; guard rule 9 sends those replies back once until you rewrite them.
   - `e2e/support/steps.ts` `confirmSection` already taps the value buttons when the card has them (and falls back to "Looks right"); drop the fallback once the button is gone.
6. **Live evals:** `make eval-live GROUP=category_options`, `GROUP=leasing_team_tone` (3/3, English and Arabic), then the full `make eval-live`. Record both in `docs/eval-notes.md`.

## Tests
- Vitest and `make e2e-fe` for the three cards.
- `make e2e-nov18 ARGS='--grep "NV0[12]"'`, then the full `make e2e-int`.
- AGENT-LIVE: the two groups at 3/3; every other group within tolerance.

## End-of-day check
- [ ] Media → "we do coffee and breakfast" → two buttons (Café, Restaurant) → tap Café → Basic Info opener with an example → value buttons for the Arabic brand name → … → `GEO-MED-…`; the case's final level is the RPLM (Media) (NV01).
- [ ] The same in Arabic: Arabic buttons, right to left (NV02).
- [ ] "Max" alone → asks what they sell; no buttons yet.
- [ ] No "Looks right" and no "Open verification link" anywhere in the chat.
- [ ] No reply says "our leasing team" or "we'll move to".
- [ ] `docs/STATUS.md` B1 row; tracker N1–N7, N13 → Done; MS6, MS7 → Done.
