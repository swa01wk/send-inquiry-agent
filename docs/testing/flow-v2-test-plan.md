# Flow v2 test plan

**Spec:** [`docs/specs/flow-v2-alignment.md`](../specs/flow-v2-alignment.md) (gate rows FV1–FV22) · **Scenarios:** [`docs/flow-v2/scenarios.json`](../flow-v2/scenarios.json) (S1–S24, CC1–CC3) · **Layers:** [`docs/specs/testing-strategy.md`](../specs/testing-strategy.md) · **Tracker:** [Flow v2 build tracker](https://claude.ai/artifact/N6P9iLDCZBniCLoNmXng67), test matrix section

The intake and review flow is Cenomi's business process, so every scenario is tested on every layer that can see it. All four layers read the same catalogue, so they can't disagree about what a scenario is (ADR-V6).

## 1. What each layer proves

| Layer | What runs | Model | Proves for flow v2 | Command | Where |
| --- | --- | --- | --- | --- | --- |
| BE | pytest: machine, effects, labels, flow steps, policy, API | none | The chart's rules hold in code: states, blockers, roles, revoke, pending expiry, routing, `flow_step` emission | `make test-be` | CI, every PR |
| AGENT-DET | pytest scenario runner over the catalogue with scripted models | scripted | Each scenario's path, cards, draft and status, turn by turn, without a browser | `make test-agent` (`-m flow_v2` for this suite only) | CI, every PR |
| INT | Playwright `@scripted @flow-v2`, real FE + BE, `AGENT_MODE=scripted` | scripted | The browser shows the right cards, the console acts, and the path matches the chart; desktop Chrome and mobile WebKit | `make e2e-int ARGS='--grep @flow-v2'` | Swaroop's Mac before every merge; CI on demand (`e2e.yml`) |
| AGENT-LIVE | `eval_live.py GROUP=flow_v2`, ×3 | Azure `gpt-5.4-mini` | The real model asks in the right order, words outcomes correctly and breaks no invariant | `make eval-live GROUP=flow_v2` | Swaroop's Mac; F3–F5 |
| E2E-LIVE | Playwright `@live @flow-v2` | Azure `gpt-5.4-mini` | A real user in a real browser gets the outcome | `make e2e-live ARGS='--grep @flow-v2'` | Swaroop's Mac; F5 |
| FE | Vitest and `@fe` Playwright for new cards and console states | none | `company_registration`, `terms`, unit assignment, Approve Lead?, contacts read-only, sign-in link | `make test-fe`, `make e2e-fe` | CI (Vitest); Mac (`@fe`) |

Claude's workspace can't run browsers, so Claude's PRs list INT, E2E-LIVE and AGENT-LIVE as not run; Swaroop runs INT before merging (as in R1–R5).

## 2. The catalogue

`docs/flow-v2/scenarios.json`, one entry per scenario:

| Key | Meaning | Used by |
| --- | --- | --- |
| `chart_paths` | Copied verbatim from the scenario page; the first is the main path, the rest are branches | `expectFlowPath`, `tests/flow_v2/test_catalogue.py` |
| `not_path` | Steps that must not appear | same |
| `seed` | For after-submit scenarios: `POST /api/dev/flow/seed` body | Playwright, pytest |
| `steps` | Abstract steps (`say`, `cr_verify`, `cr_skip`, `confirm_card`, `verify_email`, `enter_code`, `pick_malls`, `accept_terms`, `upload`, `submit`, `reviewer`, `dev_clock_advance_*`, `resume_pending`, `cc_*`, …) | Playwright step runner, pytest runner, eval driver |
| `expect` | Final status and label, draft or case fields, outbox templates, cards | all |
| `layers` | Which layers run it (`e2e_live: false` for code-only scenarios) | Playwright tags, eval selection |
| `eval.checks` | Check ids (§5) | `eval_live.py` |
| `decisions`, `changes`, `day` | M/A/G and V/E ids; build day | reports, tracker |

**Path rule.** Drop `ignored_nodes` (connectors A1–A3, B1–B2 and the out-of-scope `reg1`, `reg2`) from each chart path. Each remaining path must appear in order, as a subsequence, in the recorded `path`. A loop (S6 `emv → succ1 → emv`, S18 `docsok → … → docsok`) needs the step recorded twice. Every `not_path` step must be absent.

**Changing a scenario.** Edit the catalogue, the scripted model script (`backend/tests/e2e_scripts/flow-v2-sNN.json`) and, if the chart changed, the scenario page, all in one PR.

## 3. Backend tests (BE), by day

| Day | File | Covers |
| --- | --- | --- |
| F1 | `tests/flow/test_labels.py` | `status_label`, `role_label`; no "Lead — second review", "Regional Leasing Manager" or "estimated sales" left in `app/notifications/templates/`, `workflow/labels.py`, `agent/*_prompt.md`, `system_prompt.md`, frontend label maps (FV2) |
| F1 | `tests/lifecycle/test_revoke.py` | Reject Lead revokes the case's primary invitation; first-level reject doesn't; an existing account (A1) has no invitation and stays (FV3) |
| F2 | `tests/lifecycle/test_lead_approval.py` | New rows; removed rows refused; `lead_approved` blockers `unit_not_assigned`, `sales_data_pending`; no reject from `lead_approved`; wrong role and wrong region for each new event (FV5) |
| F2 | `tests/lifecycle/test_lead_contacts.py` | Contacts request opens on `lead_approved` only; `approved` blockers `missing_contact:*`; no per-contact events with `approval_required: false` (FV6) |
| F2 | `tests/lifecycle/test_unit_assignment.py`, `tests/domain/test_payload.py` | `unit_assigned` validation (mall must be on the inquiry); Yardi payload `assigned_unit` (FV7) |
| F2 | `tests/proactive/test_flow_v2_reminders.py` | Reminder drafted at 72 h for contacts in `lead_approved` and sales data in `second_review`; no stall flag while the tenant owes contacts (FV8) |
| F2 | `tests/flow/test_flow_steps.py` | Each lifecycle event records its steps (spec §3.1 table); `GET /api/dev/flow/{id}` by session, inquiry and reference; `POST /api/dev/flow/seed` paths are real (FV1) |
| F3 | `tests/agent/test_company_registration.py` | Verify, Skip with and without confirm, 9 digits, registered, not registered, service error, typed CR scrubbed and checked, I8 (FV9) |
| F3 | `tests/agent/test_section_order.py` | `IntakeSection`, `DraftSummary.section`, blocker order, bundle hint names one section, guard rule 8 fires once and not when the user raised the field (FV10) |
| F3 | `tests/agent/test_unit_category.py` | Only Store and Office; `category_needs_what_you_sell`; Office → `rlm_store`, `GEO-OFF-` (FV11) |
| F3 | `tests/lifecycle/test_pending_inquiry.py` | `verification_succeeded` → `pending`; nothing else moves; `expired` at 120 min (dev clock); `submit_failed` returns to `pending` (FV12) |
| F3 | `tests/api/test_pending_resume.py` | `resume_pending` same reply with and without a pending inquiry; link resumes; expired → no link (FV13) |
| F3 | `tests/domain/test_validation.py`, `tests/lifecycle/test_routing.py` | 1–5 malls, `too_many_malls` at 6; first mall's region routes (FV14) |
| F3 | `tests/api/test_terms_before_documents.py` | `accept_terms`; submit still needs terms (FV15) |
| F4 | `tests/api/test_callcentre_flow_v2.py` | Contact check, Inform, sign-in link email, fresh capture without prefill, landline-only application link (FV16) |
| F4 | `tests/agent/test_reviewer_fsd_suggestion.py` | `assess_forecasted_sales_need` facts; no request fired by the assistant (FV17) |

## 4. AGENT-DET: the catalogue runner

`backend/tests/flow_v2/test_catalogue.py`, marker `flow_v2` (and `agent`):

- one parametrized test per scenario id. It drives the HTTP app in-process (`httpx.ASGITransport`), with `X-Test-Scenario: flow-v2-sNN` and `X-Mock-Faults` from the steps;
- steps run through `tests/flow_v2/steps.py`, which maps each abstract step to the API: chat message, UI action, upload, review API call, dev clock, dev flow seed;
- at the end it asserts the path rule, `expect`, and invariants I1–I9 on every turn (`app/agent/invariants.py`).

Scripted model scripts: `backend/tests/e2e_scripts/flow-v2-s01.json` … `flow-v2-s24.json`, `flow-v2-cc1.json` … `cc3.json`. They're generated by `scripts/generate_e2e_scripts.py --flow-v2` from the catalogue steps where the model speaks, and validated by the existing script test.

## 5. AGENT-LIVE: eval group `flow_v2`

`scripts/eval_live.py`, `GROUP=flow_v2`. One eval scenario per catalogue entry (27). Each turn is driven from `steps`: UI actions go through the HTTP app, typed turns go to the real model. After-submit scenarios seed with `POST /api/dev/flow/seed`, then talk to the case agent or the reviewer assistant.

**Pass rule.** Each scenario runs 3 times (`EVAL_REPEATS=3`) and passes at 3/3. The gate (FV21) is two consecutive days at 27/27. The existing groups must stay within `EVAL_TOLERANCE` of `docs/eval-notes.md`. Results: `backend/eval-results/flow_v2-<date>.json` and a row in `docs/eval-notes.md`.

**Checks.** Deterministic where possible (state, cards, regex); none uses a model to judge.

| Check id | How it's judged | Scenarios |
| --- | --- | --- |
| `asks_sections_in_order` | The section of each question (field names mapped by `bundles.SECTION_OF`) never goes back to an earlier section, and matches `DraftSummary.section` | S1 |
| `one_section_per_turn` | No reply asks for fields of two sections | S1 |
| `no_field_asked_twice` | `unnecessary_questions` KPI = 0 | S1 |
| `skip_confirm_shown` | `company_registration` card reached `confirm_skip` before `skipped` | S1 |
| `never_claims_submitted_before_reference` | `claims_submission` false on every reply before `reference` | S1 |
| `no_cr_in_reply`, `no_lookup_company_details` | I8 | S2, S3 |
| `asks_company_name_and_address` | Basic Info reply asks for company name and address; draft has them from `user` | S2 |
| `moves_to_unit_type` | The first reply after the check asks for Unit Type | S2 |
| `one_line_then_sign_in`, `asks_nothing_else` | Registered: reply ≤ 2 sentences, `sign_in_prompt` card, no question mark after it | S3, S4 |
| `sign_in_is_the_way_in`, `no_access_promise` | Mentions sign in; no "create", "request access", "we'll set up" | S4 |
| `asks_again_plainly_or_offers_skip`, `never_moves_on_with_bad_cr` | After `invalid_cr_number`, the reply asks for the CR or offers Skip; `section` still `company_registration` | S5 |
| `friendly_retry`, `offers_person_past_limit`, `never_repeats_code` | Plain-language checks; handoff offer after `resend_throttled`; no 4-digit code in replies | S6 |
| `never_says_email_already_registered`, `never_asks_for_login` | Regex over replies | S7 |
| `says_nothing_kept_until_verified` | "come back later" before verification → reply says details aren't kept until verified | S8 |
| `on_return_says_whats_done_and_next_section`, `resume_reply_neutral` | After resume, one line of what's done + the next section; the `resume_pending` reply is identical for a known and an unknown email | S9 |
| `asks_what_you_sell`, `never_infers_category_from_brand_alone`, `offers_only_enabled_unit_types` | A question about products before `sales_category` is written; with "Max" as the only input no category is written; quick replies are Store and Office | S10 |
| `asks_for_at_least_one_mall`, `no_invented_mall` | City only → mall picker or a question; every mall id in master data | S11 |
| `accepts_several_malls`, `no_pushback_on_two_regions` | Two malls saved; no "one mall only" wording | S12 |
| `confirms_derived_values_before_moving_on`, `never_reasks_value_from_document` | Confirm card before the next section; KPI | S13 |
| `gives_refusal_reason_plainly`, `names_the_right_document` | After an upload error note | S14 |
| `warns_once_neutrally` | One duplicate warning; no blame wording | S15 |
| `answers_then_offers_to_continue`, `arabic_in_arabic`, `no_promises` | Existing `off_topic_offers_continue`, Arabic letters, `_no_timeline_promise`; plus `returns_to_section` (the side replies come back to Basic Info, never to unit type) and `draft_unchanged_by_side_questions` | S16 |
| `says_not_sent_invents_no_reference`, `offers_retry` | No `GEO-` in replies after `submit_pending` | S17 |
| `names_only_rejected_document_and_remark` | Case agent names the Brand Profile and paraphrases the remark | S18 |
| `explains_outcome_no_reviewer_names_no_promises`, `offers_new_inquiry`, `explains_outcome_offers_new_inquiry` | `_no_reviewer_names`, `_no_timeline_promise`, `after_rejection` offered | S19, S22 |
| `where_is_it_gives_right_stage` | Mentions "Tenant Qualified" or its plain meaning; no stage ahead of the case | S20 |
| `says_forecasted`, `e2_suggestion_has_reason`, `e2_never_sends_request` | "forecasted" present, "estimated" absent; the **reviewer assistant's** reply to the RSM gives a reason from the facts (new to Cenomi, area); no sales-data request on the case after it (scenario "S21 E2 reviewer assistant suggestion") | S21 |
| `e3_lists_whats_missing`, `signatory_question_first`, `no_per_contact_approval_mentioned`, `handles_yes_no_unsure` | Existing signatory checks; missing roles named; no "approve each contact" wording | S23, S24 |
| `e5_gives_words_to_say`, `no_inquiry_created`, `asks_same_sections_without_documents`, `no_prefill_claims`, `assisted_words_for_executive`, `no_documents_asked_from_executive` | Assisted channel checks | CC1–CC3 |

## 6. Playwright (INT and E2E-LIVE)

```text
e2e/
  support/scenarios.ts     # loads docs/flow-v2/scenarios.json; scenario(id) → typed entry
  support/flow.ts          # expectFlowPath(request, id, scenario): path rule against GET /api/dev/flow/{id}
  support/steps.ts         # runSteps(ctx, steps): maps abstract steps to page objects
  pages/inquiry.ts         # + verifyCr(cr), skipCr(confirm), acceptTerms(), continueMyInquiry(email)
  pages/console.ts         # reviewer console: approveDocuments, rejectDocument, assignUnit, approveLeadQuestion, approveLead, rejectLead, requestForecastedSales, askAssistant
  pages/callcentre.ts      # contactCheck, sendSignInLink, capture, submit
  tests/flow-v2/
    s01-new-prospect-skips-cr.spec.ts
    …
    s24-applicant-is-signatory.spec.ts
    cc1-existing-contact.spec.ts
    cc2-existing-cr-new-contact.spec.ts
    cc3-new-cr.spec.ts
  fixtures/files/forecasted_sales.xlsx   # new, tiny valid xlsx
```

Each spec:
1. `test.describe('S1 New prospect, no CR (skips) @flow-v2 @scripted' + (live ? ' @live' : ''))`.
2. Seeds (after-submit) or opens the chat with `X-Test-Scenario: flow-v2-s01` (scripted) or none (live).
3. `runSteps` with the per-turn checks (`plainLanguage`, I1–I9 when `E2E_LIVE=1`).
4. Asserts `expect` (status and label through `GET /api/dev/flow/{id}` and the console, cards, outbox via `support/outbox.ts`).
5. `expectFlowPath`.
6. axe scan; on mobile, no horizontal scroll.

Projects: `desktop-chrome` and `mobile` (WebKit), as today. Reviewer contexts run desktop only.

**Live rules.** `retries: 1`; a scenario passes if either attempt passes. The gate (FV20) is at least 22/24 on two runs, plus CC1–CC3. Results go to `e2e/results/live-flow-v2-<date>.json` and a row in `docs/eval-notes.md`.

## 7. Regression

Run after every build day (`make e2e-int`), not only `@flow-v2`. The stories this spec replaces or changes are listed in the spec §5.3. Their scripts change in the same PR as the behaviour. `make golden` re-records the intake goldens whose order changes, with the reason in the PR.

## 8. What each day must show (PR Testing table)

| Day | BE / AGENT-DET (CI) | INT (Swaroop's Mac) | AGENT-LIVE | E2E-LIVE |
| --- | --- | --- | --- | --- |
| F1 | F1 files + whole suite | S19, S20 + regression | `case` group within tolerance | — |
| F2 | F2 files + catalogue S21–S24 | S21–S24, S18 + regression | `case` group | — |
| F3 | F3 files + catalogue S1–S17 | S1–S17 + regression | `flow_v2` S1–S17 ×3 | smoke S1, S3 |
| F4 | F4 files + catalogue CC1–CC3, S16 | CC1–CC3, S16 + regression | `flow_v2` all ×3 | smoke CC1 |
| F5 | whole suite | all 27 on desktop and mobile | `flow_v2` 27/27 on two days; all groups | `@live @flow-v2` ≥ 22/24 + CC, twice |

Each PR's Testing section lists what ran and what didn't, per layer.
