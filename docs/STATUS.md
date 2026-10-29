# Implementation status

The single place to see what's built, what's next and how the agent maps to the business flow. **Every implementation PR updates its row here**, and each gate step records its gate result (`.cursor/rules/project.mdc`).

**Objective.** Align the Send Inquiry Agent with the inquiry business process in requirements v2.1.7.1 §7.1 — from "Send us an inquiry" to a Yardi-ready lead — and make it genuinely agentic per the Agent Capability Maturity Framework (L3 → L4 → L5). Every external Cenomi system is simulated until Cenomi gives access.

**Scope:** locked in [`docs/PRD.md`](PRD.md) v1.0 (tag `poc-prd-v1.0`); changes follow PRD §11.

**Lifecycle:** the whole process with diagrams, verified against the agent, the framework (L1–L5) and the specs: [`docs/POC-LIFECYCLE.md`](POC-LIFECYCLE.md).

**Testing:** every step follows [`docs/specs/testing-strategy.md`](specs/testing-strategy.md); §7 below shows the state of each layer.

**Status values:** ✅ Done · 🟡 In progress, or built at demo depth during the breadth days · ⬜ Not started · ⛔ Blocked · ➖ Waived (with reason)

**Last updated:** 29 Oct 2026 · Day 5 intake channels (PR B)

## 0. Delivery plan

[`docs/DELIVERY-PLAN.md`](DELIVERY-PLAN.md) (§A4 lists every L3–L5 capability in the 5 days and its depth): Part A is the 5-day plan (every level at demo depth; day prompts in `prompts/breadth/`). Part B is the full implementation plan: two 2-week sprints and a short closing phase finish each step to its gate. §B0 there maps every step to what the 5 days built and what's left. In §2 below, 🟡 on a step means it was built at demo depth.

| Phase | Dates | Goal | Backend PR (Claude) | Frontend and agent PR (Swaroop) | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Day 1 | Tue 27 Oct | Foundation: 11c, harness, policy and master data | #24 harness; #26 card fix; #27 policy; #28 CI without Playwright; #29 live targets load `.env` | #25 (11c) | ✅ | Live checks recorded in `docs/eval-notes.md` |
| Day 2 | Wed 28 Oct | Simulated Cenomi, verification by link, resume, submit once, tracking; L3 core: restart-safe store, audit log v0, thin gateway | Day 2 backend PR (#31) | Day 2 frontend track | ✅ | Verify/resume/status/dev inbox, resend countdown, S1 Playwright, prompt notes |
| Day 3 | Thu 29 Oct | Routing, handoff, Arabic, follow-on; L3 core: form mode, evidence — every L3 capability at demo depth | #35 (handoff, Arabic, follow-on, evidence); #37 (form mode, S2/S3/S13); #39 (confirm card already confirmed) | #38 (router, redirect, handoff card, divider, evidence line, prompt) | ✅ | Router, redirect, handoff card, follow-on divider, Arabic guard capture, prompt sync |
| Day 4 | Fri 30 Oct | Review lifecycle, reviewer console with audit timeline, case assistant — L4 core | #40 (lifecycle backend, review API, case links); #41 (console UI, Yardi relink) | #43 (case agent, case cards, `/inquiry/case`, T2) | ✅ | Case agent, case cards, `/inquiry/case`, T2, case eval scenarios |
| Day 5 | Mon 2 Nov | Yardi handover, reviewer assistant, intake channels; L5 core: clock, triggers, notification policy, "Needs attention", drafted reminders; demo | #44 (L5 core, `/dev`, reset, `make demo`); #46 (intake channels backend, tenant APIs) | #45 (reviewer assistant, T1, approval wording); part B PR (assisted and tenant prompts, cards, reminder drafting, demo script) | ✅ | End-of-day check automated: `make e2e-demo` |
| Sprint 1 | 3–16 Nov | M0 and L3 gates (incl. E10, intake channels); full test harness | | | ⬜ | |
| Sprint 2 | 17–30 Nov | L4 gate; channels row C5 | | | ⬜ | |
| Closing | 1 Dec – ~16 Dec | L5 to gate quality (thin L5 runs from Day 5); production readiness | | | ⬜ | |

### What slipped (Day 5) — for Sprint 1 planning

- **#46** was closed when **#44**'s base branch was deleted on merge; stacked PRs need retargeting before merge order is retried.
- **`tenant-portal.spec.ts`** had never run before merge; it failed on a strict-mode locator (sr-only live region); fixed in part B.
- **Channel notes** were lost to the channel-unaware `next_bundle_hint`; fixed in code (assisted and existing-tenant hints, tenant brand pick before the model). The channels live eval has two scenarios and no repeats.
- The **reviewer assistant** had no scripted mode; added in C1 (`X-Test-Scenario` on the assistant endpoint).
- **`show_application_link`** still ran after **Ask them to sign in**; it is now blocked once that choice is made.
- **Document-row locators** in e2e matched the whole card; rows now have `doc-row-<type>` test ids.
- The **reviewer console** has no Guest Service channel label; those cases show **Started by the call centre**.
- There is no **kiosk** unit type in master data; kiosks map to **specialty**.

## 1. Gates

| Gate | Spec | Rows | Status | Result |
| --- | --- | --- | --- | --- |
| Pre-baseline | [pre-baseline-fixes.md](specs/pre-baseline-fixes.md) §2 | P1–P5 | ✅ | P1–P3, P5 in CI (#25, #26). P4: CI green; eval 18/20 (11c), 19/20 and a passing run 2 (#27); `@live` smoke 26/28, then 01 and 05 passing (`docs/eval-notes.md`) |
| M0 modular core | [m0-modular-core.md](specs/m0-modular-core.md) §2 | G1–G7 | ⬜ | — |
| L3 reliable intake | [l3-reliable-intake.md](specs/l3-reliable-intake.md) §2 | E1–E9 | ⬜ | — |
| Intake channels | [intake-channels.md](specs/intake-channels.md) §2 | C1–C6 (C1–C4, C6 with L3 as E10; C5 with L4) | ⬜ | — |
| L4 outcome assistance | [l4-outcome-assistance.md](specs/l4-outcome-assistance.md) §2 | X1–X9 | ⬜ | — |
| L5 governed proactivity | [l5-governed-proactivity.md](specs/l5-governed-proactivity.md) §2 | Y1–Y6 | ⬜ | — |

## 2. Steps

Each step is one Cursor prompt in `prompts/` and normally one PR.

| Step | Prompt | Delivers | Gate rows | Status | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 00–11, 11b | `00`–`11b` | v1 POC, POC assumptions, UI fixes, Playwright suites | — | ✅ | #1–#13 | Live e2e: desktop 14/14; mobile test 14 fix in #13, needs a live run to confirm |
| 11c | `11c-pre-baseline-fixes.md` | Confirm only what was shown; turn on documents complete; Office removed; document numbers on the documents card; landline and `written_keys` fixes | P1–P5 | ✅ | #25, #26 | #26: a corrected document number clears its card error |
| 11d | `11d-test-harness.md` | Six test layers with one command each, frontend Playwright, eval repeats and invariants, scenario catalogue, `ci.yml`, PR template | — | 🟡 | Day 1 harness PR | Day 1: Make targets, `ci.yml`, PR template. Left for B1: frontend-only Playwright, scenario catalogue, eval repeats and invariants, `@flaky`, prompt snapshot, coverage, `scripts/` linting, `eval-live` CI job |
| 12 | `12-baseline-parity.md` | Golden transcripts, `make golden`, frontend fixtures from goldens, live-eval baseline | G1 | ⬜ | | |
| 13 | `13-durable-state.md` | Inquiry store (memory, Postgres), turn lease, checkpointer, bounded history, retention | G2 | 🟡 | Day 2 backend PR | Day 2: JSON snapshots of sessions and the simulated systems in `DATA_DIR`, history restored after restart. Left: Postgres store, turn lease, checkpointer, retention; register `Source`, `InquiryDraft`, `DocType` for checkpoint deserialisation |
| 14 | `14-workflow-gateway-submit.md` | State machine (L4 rows defined), tool gateway, idempotent submit | G3, G5, G6 | 🟡 | Day 2 backend PR | Day 2: thin gateway (timeouts, four error kinds, faults, audited calls), submit once with an idempotency key. Left: retries, reconciliation (`submit_pending` follow-up), `InquiryPayload`, state machine (Day 4) |
| 15 | `15-audit-trail.md` | Redacted, append-only audit trail | G4 | 🟡 | Day 2 backend PR | Day 2: audit log v0 with a redaction allowlist, `GET /api/dev/audit/{id}`. Left: `inquiry_events` table, correlation ids, `audit_dump.py` |
| 16 | `16-supervisor-registry.md` | Supervisor, agent registry, `status` agent, Postgres CI matrix | G1, G7 | ⬜ | | Closes the M0 gate |
| 17 | `17-policy-config.md` | Policy file; generated master data with regions and Arabic names | E2 | 🟡 | #27 | Built: `policy.yaml` read by validators, `can_submit`, cards, `verify_cr`; "Rules in force" prompt block; 20 malls with Arabic names and regions; `MasterDataSource`; flip tests. Left: verification-channel flips (19), resend limits read (19), duplicate and follow-on read (21b), `allow_inquiry` tenant prefill (21c) |
| 18 | `18-integration-adapters.md` | Simulated Cenomi: mocks, scenario data, faults, notification outbox, dev inbox | E4, E7 | 🟡 | Day 2 backend PR (#31), Day 2 frontend | `/dev/inbox`, outbox API wired in e2e. Left: contract tests, `MOCK_LATENCY_MS`, sandbox/live stubs |
| 19 | `19-email-link-resume.md` | Email-link verification, cross-device resume, resend limits | E3 | 🟡 | Day 2 backend PR (#31), Day 2 frontend | `/inquiry/verify`, resume hydrate, resend countdown. Left: "Continue later", card polling |
| 20 | `20-status-page-notifications.md` | Submission email and SMS, tokenised status page | E4, E5 | 🟡 | Day 2 backend PR (#31), Day 2 frontend | Status page, success card tracking link. Left: retried failed sends |
| 21 | `21-routing-handoff.md` | Intent router, redirect agent, human handoff, form mode when the model is down | E1 | 🟡 | Day 3 backend PR A; Day 3 frontend and agent track | Built: handoff backend, form mode (PR B), `route_message` + redirect stream, `HandoffCard`, routing fixtures (≥ 90%). Left: other handoff triggers (Sprint 1), 60-message routing set |
| 21b | `21b-arabic-follow-on-duplicates.md` | Arabic safety nets; follow-on inquiries; duplicate check | E8 | 🟡 | Day 3 backend PR A; Day 3 frontend and agent track | Built: digits, doubt, `start_follow_on`, Arabic capture in guard, follow-on divider + prompt. Left: duplicate check, follow-on from tracking page, Arabic golden (Sprint 1) |
| 21c | `21c-intake-channels.md` | Call-centre assisted intake (§7.1.1 a2, §7.1.2 a2); existing tenants via Leasing Opportunities (§7.1.2 a1); public-page sign-in path (§7.1); `staff` source; contacts prefill and remove | E10, C1–C6 | 🟡 | #46; part B PR | Built: backend (#46) plus assisted and existing-tenant prompts, `basic_info_review`, `sign_in_prompt`, `existing_cr_choice`, send-link cards, `/callcentre` with mock staff sign-in, Tenant Central UI, channel badges and `/dev` persona links. Left: stories S9–S12, T10, `channels` eval repeats and invariants, access tests, prompt snapshots for both modes |
| 22 | `22-l3-gate.md` | Stories S1–S13, KPI report, the L3 gate run (evidence built on Day 3) | E1–E10 | 🟡 | Day 2 frontend (S1), Day 3 PR B (S2, S3, S13) | Stories S1, S2, S3, S13 scripted; evidence for derived values (Day 3 PR A). Left: S4–S8, KPI report. Closes the L3 gate |
| 23 | `23-lifecycle-core.md` | Case data, live L4 transitions, review routing, effects, Azure AD and Yardi mocks | X1, X2, X5, X7 | 🟡 | #40 | Built (Day 4 depth): `transition()` with every M0 §6 row and the queue check, case record in JSON snapshots, routing from the policy, inline effects keyed per event, reviewer directory, Azure AD and Yardi mocks, every §3.4 template, automatic contacts request, Yardi retries and operations flag. Left: `case_effects` outbox and worker, migration, Postgres (Sprint 2) |
| 24 | `24-reviewer-console.md` | Review API, mock sign-in, queue and case pages, case brief | X4, X6 | 🟡 | #40 (API, brief); #41 (pages); #44 / Day 5 UI | Built: Day 4 console plus channel labels on queue and case, **Remove** on prefilled contacts, re-link pickers, **Needs attention** entry and badge. Left: request history, reason categories, funnel and pending approvals (Should), form polish |
| 25 | `25-case-assistant.md` | Case links, `case` agent, re-upload loop, outcome framing, full status page | X1, X3 | 🟡 | #40; #44 / Day 5 | Built: Day 4 case agent and T2; status page **Waiting for you** with case-link buttons; second-review stage labelled **Lead — second review**; Yardi-approved copy only after `sent_to_yardi`. Left: guard rules, expired or closed links, `case` eval group |
| 26 | `26-second-level-requests.md` | Contacts and estimated sales data | X1, X3 | 🟡 | #40; #46 | Built: Day 4 contacts and sales cards; existing-tenant contacts prefilled at second review (Day 5). Left: edge cases, `contacts` eval group, story T4 |
| 27 | `27-reviewer-assistant.md` | Reviewer agent, Yardi suggestions, drafted notes | X2, X4 | ⬜ | #45; part B PR (reminder drafts) | Built at demo depth in #45 (case-page assistant, Yardi **Use**, defers approve/reject) and part B (assistant-drafted tenant reminders on Needs attention). Left: suggestion audit, guard rules, `reviewer` eval group — finishes in Sprint 2 |
| 28 | `28-yardi-handover-l4-gate.md` | Approval to Yardi, L4 KPIs, stories T1–T8 | X1–X9 | 🟡 | #44; #45 (T1, wording) | Built: `send_lead`, re-link validation, `waiting_on_you`, invitations for contacts without accounts, story **T1** to Yardi, approved tracking copy. Left: L4 KPI report, stories T3–T10, retries and operations-flag hardening — **closes L4 gate** in Sprint 2 |
| 29 | `29-event-engine-policy.md` | Event engine, simulated clock, notification policy, opt-out | Y2 | 🟡 | #44 | Built (thin): `SimulatedClock`, dev clock API, tick on advance and background, `NotificationPolicy` (tiers, quiet hours, once per 48 h per case), audited decisions, `/dev` clock controls. Left: engine on `inquiry_events`, throttles, opt-out link, abandoned-draft trigger, persisted clock offset |
| 30 | `30-triggers-attention.md` | Triggers, "Needs attention", drafting agent | Y1, Y3, Y4 | 🟡 | #44; part B PR | Built (thin): stalled review, escalation, unanswered-request triggers; attention API and console; reviewer-assistant drafts for reminders (part B). Left: deterministic draft checks, abandoned-draft and late-duplicate triggers, stories P1–P6, `proactive` eval group |
| 31 | `31-insights-l5-gate.md` | Insight report, L5 KPIs | Y5, Y6 | ⬜ | | Closes the L5 gate |

## 3. Business flow coverage (requirements §7.1)

Summary by workflow. Line-by-line coverage of every statement in §7.1, §7.1.1 and §7.1.2 (rows R1–R81) is in [`docs/specs/workflows-7-1.md`](specs/workflows-7-1.md).

| Workflow | Where it's built | 5-day plan | Status |
| --- | --- | --- | --- |
| §7.1.1 a1 — prospective, self-service: CR check or skip, 12 basic-info fields, one product line and mall, email link and mobile OTP with resend after a set time, documents with their numbers, submit, reference and tracking link | v1; 11c; 17–20 | Days 1–3 | 🟡 (v1 built; link, tracking and document numbers to come) |
| §7.1.1 a2 — prospective, via the call centre: executive raises it; applicant completes from the emailed link (email auto-verified, review basic info, Proceed, OTP, documents, submit) | 21c | Day 5 | 🟡 (demo depth; Playwright `a2-call-centre.spec.ts`, `a2-guest-service.spec.ts`, and `make e2e-demo`) |
| §7.1.2 a1 — existing tenant via Leasing Opportunities: prefilled details and documents, property preselected, verify and edit, submit, My inquiries | 21c | Day 5 | 🟡 |
| §7.1.2 a2 — existing tenant via the call centre: CR exists → ask to sign in, or continue with the record prefilled | 21c | Day 5 | 🟡 (demo depth; Playwright `a2-existing-cr.spec.ts` and `make e2e-demo`) |
| §7.1 — existing tenant on the public page (`existing_tenant_policy`) | 17, 21c | Days 1, 5 | 🟡 |
| b — routing to RLM-Store / RPLM-Media / RPLM-Specialty by unit type and region | 23 | Day 4 | 🟡 (policy routing by unit type and the mall's region; reviewers notified) |
| b — first-level review: re-upload by email link, reject with remarks, approve with Azure AD invitation (only if no account) | 23–25 | Day 4 | 🟡 (console, API and applicant chat built at demo depth) |
| b — automatic contacts request "on contact creation"; qualified as a lead | 23, 25 | Days 4, 5 | ⬜ |
| c — additional contacts (prefilled for existing tenants; reviewer can remove), estimated sales data with notifications both ways | 26, 21c | Days 4, 5 | 🟡 |
| c — re-link company and brand from Yardi matches | 24, 27 | Day 5 | 🟡 (console form and Yardi lookups, #41; reviewer assistant suggestions on Day 5) |
| c — approve (invitations for new contacts, acceptance email, data to Yardi) or reject with email | 28 | Days 4, 5 | ⬜ |
| Tracking link: stage, owner and what's waiting on the applicant | 20, 25 | Days 2, 5 | 🟡 (status page Day 2; case chat from track link and stage/owner on `case_status` card Day 4) |
| Notifications: information vs action required (§7.15) | 18, 23 | Days 2, 4 | ⬜ |
| Audit log of actions by customers and staff (§7.10) | 15, 23 | Sprint 1 | ⬜ |
| Review SLAs (Phase 2) | Demo thresholds in 29–30 | Closing | ⬜ |
| **Out of scope:** Super Admin onboarding of existing tenants (§7.1, user management); profile completion after sign-in; General Inquiries (§7.8.1.1, router redirects); Proposal stage (§7.2); document-content checks | — | — | ➖ |

## 4. Agentic capability coverage (framework §5–§7)

| Level | Capability | Where | Status |
| --- | --- | --- | --- |
| L1 | Task can be completed through a reliable digital form (incl. when the model is down) | Cards and review card (v1); form mode L3 §3.14 (21) | 🟡 |
| L1 | Schema, accessibility, authorisation, persistence, duplicate-submission controls | Validators (v1); axe (11d); mock identities (21c, 24); Postgres (13); idempotent submit (14) | 🟡 |
| L2 | All form paths conversational with no field loss | v1; parity goldens (12) | 🟡 |
| L2 | Clear handoff to the original transaction | 21; call-centre continuation (21c) | ⬜ |
| L3 | 1 Intent detection and routing | 16 (supervisor), 21 (router) | ⬜ |
| L3 | 2 Multi-field extraction | v1; Arabic digits and doubt (Day 3); evidence for derived values on the confirm card and in the audit (Day 3) | 🟡 |
| L3 | 3 Entity resolution | v1 mall and category matching; Arabic mall names and aliases matched (17) | 🟡 |
| L3 | 4 Verified context reuse | v1 CR prefill; follow-on inquiries reuse verified details (Day 3, 21b) | 🟡 |
| L3 | 5 Adaptive slot filling | v1 bundles; documents-complete turn in 11c | 🟡 |
| L3 | 6 Deterministic validation | v1; "confirm only what was shown" in 11c; policy in 17 | 🟡 |
| L3 | 7 Durable drafts and resume | 13, 19 (Day 2: JSON snapshots, resume by link) | 🟡 |
| L3 | 8 Explicit review and consent | v1 | ✅ |
| L3 | 9 Reliable tool and API execution | 14, 18 (Day 2: thin gateway, submit once) | 🟡 |
| L3 | 10 Audit and recovery | 15, 18, 21 (Day 2: audit log v0, faults end in clear notes; Day 3: handoff to the call centre with a case, `handoff_created` audit) | 🟡 |
| L4 | 1 Outcome framing | 25 | ⬜ |
| L4 | 2 Structured context assembly | 24 (case brief) | ⬜ |
| L4 | 3 Grounded derivation and prefill | Day 3 evidence (22), 26 (reuse primary contact), 21c (tenant-record prefill) | ⬜ |
| L4 | 4 Adaptive dialogue | 25, 26 | ⬜ |
| L4 | 5 Bounded read-and-reason tools | 25, 27 | ⬜ |
| L4 | 6 Cross-step continuity | 23, 25; 21c (executive → applicant handover) | ⬜ |
| L4 | 7 Reviewer assistance | 24, 27 | ⬜ |
| L4 | 8 Exception and rework reduction | 25, 26, 21b (duplicates) | ⬜ |
| L4 | 9 Human collaboration (reviewers decide) | 23 (actor checks), 27 | ⬜ |
| L4 | 10 Outcome tracking | 20, 25 | ⬜ |
| L5 | 1 Event and state awareness | 29 | ⬜ |
| L5 | 2 Next-best-action recommendations | 30 | ⬜ |
| L5 | 3 Proactive preparation | 30 | ⬜ |
| L5 | 4 Cross-role coordination | 30 (escalation) | ⬜ |
| L5 | 5 Process optimisation | 31 | ⬜ |
| L5 | 6 Bounded automation | 29 (tiers) | ⬜ |
| L5 | 7 Attention management | 29 (quiet hours, throttles, opt-out) | ⬜ |
| L5 | 8 Feedback and learning | 31 (KPIs) | ⬜ |

## 5. Assumptions and decisions waiting on Cenomi

Nothing is blocked: each item has a working assumption implemented in a mock or the policy file.

| Where | Items |
| --- | --- |
| POC assumptions (25 Oct) | `docs/assumptions.md`; handoff doc §4 |
| M0 | Postgres hosting, retention, payload shape (M0 §13) |
| L3 | Q1–Q8 as assumptions (L3 §7) |
| L4 | A1–A10 (L4 §6) |
| Intake channels | D1–D8 ([intake-channels.md](specs/intake-channels.md) §6), including the `staff` source and signed-in tenants skipping verification |
| L5 | B1–B6 (L5 §6). **B6 extends POC assumption 9** (resume link for an abandoned draft sent without approval) |

## 6. Known issues

| Issue | Resolved in | Status |
| --- | --- | --- |
| Saudi landline rule expects 8 digits after +966; real numbers have 9 | 11c | ✅ |
| `write_fields` lists `mobile`/`landline` twice for `contact_number` | 11c | ✅ |
| `domain/draft_merge.py` unused | 11c | ✅ |
| `docs/eval-notes.md` first entry mentions forced tool choice | 11c | ✅ |
| Document uploads don't trigger an agent turn | 11c | ✅ |
| `OFF` (Office) unit code and `office` in seed data and FAQ | 11c | ✅ |
| Golden rules mention a `submit_inquiry` tool that doesn't exist | 11c | ✅ |
| `confirm_fields` can confirm values the user never saw | 11c | ✅ |
| Documents card has no inputs for VAT ID, National ID, National Address; CR ID not shown | 11c | ✅ |
| §7.1 flow diagrams are embedded at 96 ppi and can't be read; ask Cenomi for the source files | — | ⬜ |
| No way to finish the inquiry when the model is down (L1 baseline) | Day 3 (form mode); hardened in 21 | 🟡 |
| §7.15 notification content and the UX/UI design links aren't available; templates and pages are synthetic | Cenomi input | ⬜ |
| LangGraph warns about deserialising unregistered types from checkpoints. *Resolution (step 13):* register `Source`, `InquiryDraft`, and `DocType` in LangGraph `allowed_msgpack_modules` (or equivalent) with the checkpointer | 13 | ⬜ |
| CI runs only `e2e.yml`; no test and lint workflow | Day 1 harness PR (`ci.yml`) | ✅ |
| `scripts/` not covered by `make check-be` (27 ruff findings across `eval_live.py`, `generate_e2e_scripts.py`, `chat_cli.py`; 2 files unformatted) | 11d (B1) | ⬜ |
| No resend cooldown for OTP or email link | Day 2 backend PR (policy `resend`) | ✅ |
| Status API returns a fixed `under_review` and hard-coded steps | Day 2: stages and owner role, token required; real stages with the lifecycle (Day 4) | 🟡 |
| Doubt detection and capture heuristics are English-only; no Arabic-Indic digits | 21b | ⬜ |
| `EMAIL_LINK_DEMO` defaults to `true` | Before any non-demo deploy | ⬜ |
| `app/agent/e2e_scripts.py` reads scripts from `tests/` | Only matters for a slim image | ⬜ |
| 4 ESLint fast-refresh warnings in `frontend/src/state/chatStore.tsx` | Low priority | ⬜ |
| Live test 14 failed on mobile in CI (WebKit) | PR #13 (read text from the DOM); passed on mobile in the 27 Oct live smoke run | ✅ |

## 7. Test layers

What each layer proves and when it runs: [`docs/specs/testing-strategy.md`](specs/testing-strategy.md) §2 and §4. A step that adds a layer or a suite updates this table.

| Layer | What it covers | Command | In CI | Status today | Notes |
| --- | --- | --- | --- | --- | --- |
| BE | ruff, `mypy --strict`; pytest for domain, services, API, workflow, audit, contracts | `make check-be`, `make test-be` | Every PR (`ci.yml` `backend`) | 🟡 | In CI from Day 1; `scripts/` not linted and no coverage report yet (11d, B1) |
| FE | ESLint, `tsc`, Prettier; Vitest; Playwright against the frontend alone (`VITE_MOCK=1`) | `make check-fe`, `make test-fe`, `make e2e-fe` | Every PR (`ci.yml` `frontend`; `e2e-fe` locally) | 🟡 | ESLint, `tsc`, Prettier and Vitest in CI from Day 1; frontend-only Playwright (`e2e-fe`) doesn't exist yet (11d, B1) |
| INT | Playwright, real frontend + backend, scripted agent, mocks | `make e2e-int` (`make e2e`) | Every PR, locally (CI on demand: `e2e.yml`, suite `scripted`) | ✅ | `@scripted` suites, desktop and mobile. Taken out of per-PR CI on 27 Oct: installing browsers took most of each run |
| DEMO | Full demo-script walkthrough (Day 5 end-of-day check); desktop only | `make e2e-demo`, `make e2e-demo-headed`, `make e2e-demo-step` | Local rehearsal (not part of `e2e-int`) | ✅ | `@demo` suite in `e2e/tests/demo.spec.ts`; same order as [demo-script.md](./demo-script.md) §A3 automation |
| AGENT-DET | Tools, guard, actions, bundles, prompt snapshot, routing, allowlists, scenarios, parity goldens | `make test-agent` | Every PR (inside `test-be`) | 🟡 | `make test-agent` runs `tests/agent`, `tests/scenarios` and the e2e-script tests (Day 1); markers, prompt snapshot and goldens in 11d and 12 |
| AGENT-LIVE | `eval_live.py` scenario groups, ×3 repeats, invariants I1–I7, score vs baseline | `make eval-live` | `workflow_dispatch`; nightly opt-in | 🟡 | Script exists (intake scenarios); no repeats, JSON output or invariant checks yet (11d); baseline in 12 |
| E2E-LIVE | Playwright, real frontend + backend + model; personas and live stories | `make e2e-live` | `workflow_dispatch`; nightly opt-in | 🟡 | `@live` personas: desktop 14/14, mobile 13/14 before #13; invariant checks in 11d |

Coverage (from 11d): `app/domain` — · `app/agent` — · `app` — (floors 95% / 85% / 85%).

