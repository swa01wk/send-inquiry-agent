# Implementation status

The single place to see what's built, what's next and how the agent maps to the business flow. **Every implementation PR updates its row here**, and each gate step records its gate result (`.cursor/rules/project.mdc`).

**Objective.** Align the Send Inquiry Agent with the inquiry business process in requirements v2.1.7.1 §7.1 — from "Send us an inquiry" to a Yardi-ready lead — and make it genuinely agentic per the Agent Capability Maturity Framework (L3 → L4 → L5). Every external Cenomi system is simulated until Cenomi gives access.

**Scope:** locked in [`docs/PRD.md`](PRD.md) v1.0 (tag `poc-prd-v1.0`); changes follow PRD §11.

**Lifecycle:** the whole process with diagrams, verified against the agent, the framework (L1–L5) and the specs: [`docs/POC-LIFECYCLE.md`](POC-LIFECYCLE.md).

**Testing:** every step follows [`docs/specs/testing-strategy.md`](specs/testing-strategy.md); §7 below shows the state of each layer.

**Status values:** ✅ Done · 🟡 In progress, or built at demo depth during the breadth days · ⬜ Not started · ⛔ Blocked · ➖ Waived (with reason)

**Last updated:** 27 Oct 2026 · Day 1 policy PR (step 17)

## 0. Delivery plan

[`docs/DELIVERY-PLAN.md`](DELIVERY-PLAN.md) (§A4 lists every L3–L5 capability in the 5 days and its depth): Part A is the 5-day plan (every level at demo depth; day prompts in `prompts/breadth/`). Part B is the full implementation plan: two 2-week sprints and a short closing phase finish each step to its gate. §B0 there maps every step to what the 5 days built and what's left. In §2 below, 🟡 on a step means it was built at demo depth.

| Phase | Dates | Goal | Backend PR (Claude) | Frontend and agent PR (Swaroop) | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Day 1 | Tue 27 Oct | Foundation: 11c, harness, policy and master data | #24 harness; #26 card fix; policy PR (step 17) | #25 (11c) | ✅ | Done when the policy PR merges |
| Day 2 | Wed 28 Oct | Simulated Cenomi, verification by link, resume, submit once, tracking; L3 core: restart-safe store, audit log v0, thin gateway | | | ⬜ | |
| Day 3 | Thu 29 Oct | Routing, handoff, Arabic, follow-on; L3 core: form mode, evidence — every L3 capability at demo depth | | | ⬜ | |
| Day 4 | Fri 30 Oct | Review lifecycle, reviewer console with audit timeline, case assistant — L4 core | | | ⬜ | |
| Day 5 | Mon 2 Nov | Yardi handover, reviewer assistant, intake channels; L5 core: clock, triggers, notification policy, "Needs attention", drafted reminders; demo | | | ⬜ | |
| Sprint 1 | 3–16 Nov | M0 and L3 gates (incl. E10, intake channels); full test harness | | | ⬜ | |
| Sprint 2 | 17–30 Nov | L4 gate; channels row C5 | | | ⬜ | |
| Closing | 1 Dec – ~16 Dec | L5 to gate quality (thin L5 runs from Day 5); production readiness | | | ⬜ | |

## 1. Gates

| Gate | Spec | Rows | Status | Result |
| --- | --- | --- | --- | --- |
| Pre-baseline | [pre-baseline-fixes.md](specs/pre-baseline-fixes.md) §2 | P1–P5 | 🟡 | P1–P3, P5 proven in CI (#25, #26). P4: CI green; eval run 1 18/20, `@live` smoke 26/28 (06 WhatsApp and 22 model variance); eval run 2 to record in `docs/eval-notes.md` |
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
| 13 | `13-durable-state.md` | Inquiry store (memory, Postgres), turn lease, checkpointer, bounded history, retention | G2 | ⬜ | | Register `Source`, `InquiryDraft`, `DocType` for checkpoint deserialisation |
| 14 | `14-workflow-gateway-submit.md` | State machine (L4 rows defined), tool gateway, idempotent submit | G3, G5, G6 | ⬜ | | |
| 15 | `15-audit-trail.md` | Redacted, append-only audit trail | G4 | ⬜ | | |
| 16 | `16-supervisor-registry.md` | Supervisor, agent registry, `status` agent, Postgres CI matrix | G1, G7 | ⬜ | | Closes the M0 gate |
| 17 | `17-policy-config.md` | Policy file; generated master data with regions and Arabic names | E2 | 🟡 | Day 1 policy PR | Built: `policy.yaml` read by validators, `can_submit`, cards, `verify_cr`; "Rules in force" prompt block; 20 malls with Arabic names and regions; `MasterDataSource`; flip tests. Left: verification-channel flips (19), resend limits read (19), duplicate and follow-on read (21b), `allow_inquiry` tenant prefill (21c) |
| 18 | `18-integration-adapters.md` | Simulated Cenomi: mocks, scenario data, faults, notification outbox, dev inbox | E4, E7 | ⬜ | | Adds `react-router-dom` |
| 19 | `19-email-link-resume.md` | Email-link verification, cross-device resume, resend limits | E3 | ⬜ | | |
| 20 | `20-status-page-notifications.md` | Submission email and SMS, tokenised status page | E4, E5 | ⬜ | | |
| 21 | `21-routing-handoff.md` | Intent router, redirect agent, human handoff, form mode when the model is down | E1 | ⬜ | | |
| 21b | `21b-arabic-follow-on-duplicates.md` | Arabic safety nets; follow-on inquiries; duplicate check | E8 | ⬜ | | |
| 21c | `21c-intake-channels.md` | Call-centre assisted intake (§7.1.1 a2, §7.1.2 a2); existing tenants via Leasing Opportunities (§7.1.2 a1); public-page sign-in path (§7.1); `staff` source; contacts prefill and remove | E10, C1–C6 | ⬜ | | Added after the §7.1 review |
| 22 | `22-l3-gate.md` | Stories S1–S13, KPI report, the L3 gate run (evidence built on Day 3) | E1–E10 | ⬜ | | Closes the L3 gate |
| 23 | `23-lifecycle-core.md` | Case data, live L4 transitions, review routing, effects, Azure AD and Yardi mocks | X1, X2, X5, X7 | ⬜ | | |
| 24 | `24-reviewer-console.md` | Review API, mock sign-in, queue and case pages, case brief | X4, X6 | ⬜ | | |
| 25 | `25-case-assistant.md` | Case links, `case` agent, re-upload loop, outcome framing, full status page | X1, X3 | ⬜ | | |
| 26 | `26-second-level-requests.md` | Contacts and estimated sales data | X1, X3 | ⬜ | | |
| 27 | `27-reviewer-assistant.md` | Reviewer agent, Yardi suggestions, drafted notes | X2, X4 | ⬜ | | |
| 28 | `28-yardi-handover-l4-gate.md` | Approval to Yardi, L4 KPIs, stories T1–T8 | X1–X9 | ⬜ | | Closes the L4 gate |
| 29 | `29-event-engine-policy.md` | Event engine, simulated clock, notification policy, opt-out | Y2 | ⬜ | | |
| 30 | `30-triggers-attention.md` | Triggers, "Needs attention", drafting agent | Y1, Y3, Y4 | ⬜ | | |
| 31 | `31-insights-l5-gate.md` | Insight report, L5 KPIs | Y5, Y6 | ⬜ | | Closes the L5 gate |

## 3. Business flow coverage (requirements §7.1)

Summary by workflow. Line-by-line coverage of every statement in §7.1, §7.1.1 and §7.1.2 (rows R1–R81) is in [`docs/specs/workflows-7-1.md`](specs/workflows-7-1.md).

| Workflow | Where it's built | 5-day plan | Status |
| --- | --- | --- | --- |
| §7.1.1 a1 — prospective, self-service: CR check or skip, 12 basic-info fields, one product line and mall, email link and mobile OTP with resend after a set time, documents with their numbers, submit, reference and tracking link | v1; 11c; 17–20 | Days 1–3 | 🟡 (v1 built; link, tracking and document numbers to come) |
| §7.1.1 a2 — prospective, via the call centre: executive raises it; applicant completes from the emailed link (email auto-verified, review basic info, Proceed, OTP, documents, submit) | 21c | Day 5 | ⬜ |
| §7.1.2 a1 — existing tenant via Leasing Opportunities: prefilled details and documents, property preselected, verify and edit, submit, My inquiries | 21c | Day 5 | ⬜ |
| §7.1.2 a2 — existing tenant via the call centre: CR exists → ask to sign in, or continue with the record prefilled | 21c | Day 5 | ⬜ |
| §7.1 — existing tenant on the public page (`existing_tenant_policy`) | 17, 21c | Days 1, 5 | 🟡 |
| b — routing to RLM-Store / RPLM-Media / RPLM-Specialty by unit type and region | 23 | Day 4 | ⬜ |
| b — first-level review: re-upload by email link, reject with remarks, approve with Azure AD invitation (only if no account) | 23–25 | Day 4 | ⬜ |
| b — automatic contacts request "on contact creation"; qualified as a lead | 23, 25 | Days 4, 5 | ⬜ |
| c — additional contacts (prefilled for existing tenants; reviewer can remove), estimated sales data with notifications both ways | 26, 21c | Days 4, 5 | ⬜ |
| c — re-link company and brand from Yardi matches | 24, 27 | Day 5 | ⬜ |
| c — approve (invitations for new contacts, acceptance email, data to Yardi) or reject with email | 28 | Days 4, 5 | ⬜ |
| Tracking link: stage, owner and what's waiting on the applicant | 20, 25 | Days 2, 5 | ⬜ |
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
| L3 | 2 Multi-field extraction | v1; Arabic in 21b; evidence in 22 | 🟡 |
| L3 | 3 Entity resolution | v1 mall and category matching; Arabic mall names and aliases matched (17) | 🟡 |
| L3 | 4 Verified context reuse | v1 CR prefill; follow-on inquiries in 21b | 🟡 |
| L3 | 5 Adaptive slot filling | v1 bundles; documents-complete turn in 11c | 🟡 |
| L3 | 6 Deterministic validation | v1; "confirm only what was shown" in 11c; policy in 17 | 🟡 |
| L3 | 7 Durable drafts and resume | 13, 19 | ⬜ |
| L3 | 8 Explicit review and consent | v1 | ✅ |
| L3 | 9 Reliable tool and API execution | 14, 18 | ⬜ |
| L3 | 10 Audit and recovery | 15, 18, 21 | ⬜ |
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
| No way to finish the inquiry when the model is down (L1 baseline) | Day 3 (form mode); hardened in 21 | ⬜ |
| §7.15 notification content and the UX/UI design links aren't available; templates and pages are synthetic | Cenomi input | ⬜ |
| LangGraph warns about deserialising unregistered types from checkpoints | 13 | ⬜ |
| CI runs only `e2e.yml`; no test and lint workflow | Day 1 harness PR (`ci.yml`) | ✅ |
| `scripts/` not covered by `make check-be` (27 ruff findings across `eval_live.py`, `generate_e2e_scripts.py`, `chat_cli.py`; 2 files unformatted) | 11d (B1) | ⬜ |
| No resend cooldown for OTP or email link | 19 | ⬜ |
| Status API returns a fixed `under_review` and hard-coded steps | 20 | ⬜ |
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
| AGENT-DET | Tools, guard, actions, bundles, prompt snapshot, routing, allowlists, scenarios, parity goldens | `make test-agent` | Every PR (inside `test-be`) | 🟡 | `make test-agent` runs `tests/agent`, `tests/scenarios` and the e2e-script tests (Day 1); markers, prompt snapshot and goldens in 11d and 12 |
| AGENT-LIVE | `eval_live.py` scenario groups, ×3 repeats, invariants I1–I7, score vs baseline | `make eval-live` | `workflow_dispatch`; nightly opt-in | 🟡 | Script exists (intake scenarios); no repeats, JSON output or invariant checks yet (11d); baseline in 12 |
| E2E-LIVE | Playwright, real frontend + backend + model; personas and live stories | `make e2e-live` | `workflow_dispatch`; nightly opt-in | 🟡 | `@live` personas: desktop 14/14, mobile 13/14 before #13; invariant checks in 11d |

Coverage (from 11d): `app/domain` — · `app/agent` — · `app` — (floors 95% / 85% / 85%).

