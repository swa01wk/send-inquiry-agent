# Implementation status

The single place to see what's built, what's next and how the agent maps to the business flow. **Every implementation PR updates its row here**, and each gate step records its gate result (`.cursor/rules/project.mdc`).

**Objective.** Align the Send Inquiry Agent with the inquiry business process in requirements v2.1.7.1 §7.1 — from "Send us an inquiry" to a Yardi-ready lead — and make it genuinely agentic per the Agent Capability Maturity Framework (L3 → L4 → L5). Every external Cenomi system is simulated until Cenomi gives access.

**Status values:** ✅ Done · 🟡 In progress · ⬜ Not started · ⛔ Blocked · ➖ Waived (with reason)

**Last updated:** 26 Oct 2026 · `main` at `afa0ddd` (PR #13)

## 1. Gates

| Gate | Spec | Rows | Status | Result |
| --- | --- | --- | --- | --- |
| Pre-baseline | [pre-baseline-fixes.md](specs/pre-baseline-fixes.md) §2 | P1–P4 | ⬜ | — |
| M0 modular core | [m0-modular-core.md](specs/m0-modular-core.md) §2 | G1–G7 | ⬜ | — |
| L3 reliable intake | [l3-reliable-intake.md](specs/l3-reliable-intake.md) §2 | E1–E9 | ⬜ | — |
| L4 outcome assistance | [l4-outcome-assistance.md](specs/l4-outcome-assistance.md) §2 | X1–X9 | ⬜ | — |
| L5 governed proactivity | [l5-governed-proactivity.md](specs/l5-governed-proactivity.md) §2 | Y1–Y6 | ⬜ | — |

## 2. Steps

Each step is one Cursor prompt in `prompts/` and normally one PR.

| Step | Prompt | Delivers | Gate rows | Status | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 00–11, 11b | `00`–`11b` | v1 POC, POC assumptions, UI fixes, Playwright suites | — | ✅ | #1–#13 | Live e2e: desktop 14/14; mobile test 14 fix in #13, needs a live run to confirm |
| 11c | `11c-pre-baseline-fixes.md` | Confirm only what was shown; turn on documents complete; Office removed; landline and `written_keys` fixes | P1–P4 | ⬜ | | Must land before step 12 |
| 12 | `12-baseline-parity.md` | Golden transcripts, `make golden`, live-eval baseline | G1 | ⬜ | | |
| 13 | `13-durable-state.md` | Inquiry store (memory, Postgres), turn lease, checkpointer, bounded history, retention | G2 | ⬜ | | Register `Source`, `InquiryDraft`, `DocType` for checkpoint deserialisation |
| 14 | `14-workflow-gateway-submit.md` | State machine (L4 rows defined), tool gateway, idempotent submit | G3, G5, G6 | ⬜ | | |
| 15 | `15-audit-trail.md` | Redacted, append-only audit trail | G4 | ⬜ | | |
| 16 | `16-supervisor-registry.md` | Supervisor, agent registry, `status` agent, CI test and lint workflow | G1, G7 | ⬜ | | Closes the M0 gate |
| 17 | `17-policy-config.md` | Policy file; generated master data with regions and Arabic names | E2 | ⬜ | | |
| 18 | `18-integration-adapters.md` | Simulated Cenomi: mocks, scenario data, faults, notification outbox, dev inbox | E4, E7 | ⬜ | | Adds `react-router-dom` |
| 19 | `19-email-link-resume.md` | Email-link verification, cross-device resume, resend limits | E3 | ⬜ | | |
| 20 | `20-status-page-notifications.md` | Submission email and SMS, tokenised status page | E4, E5 | ⬜ | | |
| 21 | `21-routing-handoff.md` | Intent router, redirect agent, human handoff | E1 | ⬜ | | |
| 21b | `21b-arabic-follow-on-duplicates.md` | Arabic safety nets; follow-on inquiries; duplicate check | E8 | ⬜ | | |
| 22 | `22-l3-gate.md` | Evidence for derived values, stories S1–S8, KPI report | E1–E9 | ⬜ | | Closes the L3 gate |
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

| Requirement | Where it's built | Status |
| --- | --- | --- |
| "Send us an inquiry" on the sign-in page, for one product line at a property (§7.1.1 a1) | v1 intake | ✅ |
| CR check, optional and skippable; existing CR → Sign In (§7.1.1 a1, a2) | v1; policy flag in 17 | ✅ / ⬜ flag |
| Basic info, 12 fields; mobile and landline mutually exclusive, with country codes | v1, PR #1; landline fix in 11c | ✅ |
| Product lines Store, Media, Specialty only (§1) | 11c | ⬜ |
| Email verified by link; mobile by OTP; resend after a set time | v1 (in chat); real link and resume in 19; cooldown in 19 | 🟡 |
| Complete the application from the emailed link (external page) | 19 (resume on any device) | ⬜ |
| Documents: Brand Profile and Company Profile required; CR, VAT, National ID, National Address optional | v1; turn on completion in 11c | ✅ |
| Alphanumeric reference on screen, shared by email or SMS with a tracking link | v1 reference; notifications and tracking page in 20 | 🟡 |
| Call-centre path (§7.1.1 a2): the executive continues the same inquiry | Handoff case in 21 | ⬜ |
| Routing to RLM-Store / RPLM-Media / RPLM-Specialty by unit type and region (§7.1.1 b) | 23 | ⬜ |
| First-level review: re-upload request by email link, reject with remarks, approve (§7.1.1 b) | 23–25 | ⬜ |
| Approval → Azure AD account and invitation (§7.1.1 b) | 23 (mock) | ⬜ |
| Second level: additional contacts (Authorized Signatory and Billing Contact required) (§7.1.1 c) | 26 | ⬜ |
| Second level: estimated sales data; reviewer notified on upload (§7.1.1 c) | 26 | ⬜ |
| Second level: re-link company and brand from Yardi matches (§7.1.1 c) | 24, 27 | ⬜ |
| Final approval → invitations for contacts, acceptance email, data sent to Yardi (§7.1.1 c) | 28 | ⬜ |
| Notifications: information vs action required (§7.15) | Templates in 18, 23 | ⬜ |
| Audit log of actions by customers and staff (§7.10) | 15, extended in 23 | ⬜ |
| Existing tenants raise inquiries via Leasing Opportunities after sign-in (§7.1.2) | Out of scope; router redirects (21) | ⬜ |
| General Inquiries are a separate service request after sign-in (§7.8.1.1) | Out of scope; router redirects (21) | ⬜ |
| Review SLAs (Phase 2) | Demo thresholds in 29–30 | ⬜ |

## 4. Agentic capability coverage (framework §5–§7)

| Level | Capability | Where | Status |
| --- | --- | --- | --- |
| L3 | 1 Intent detection and routing | 16 (supervisor), 21 (router) | ⬜ |
| L3 | 2 Multi-field extraction | v1; Arabic in 21b; evidence in 22 | 🟡 |
| L3 | 3 Entity resolution | v1 mall and category matching; Arabic names in 17 | 🟡 |
| L3 | 4 Verified context reuse | v1 CR prefill; follow-on inquiries in 21b | 🟡 |
| L3 | 5 Adaptive slot filling | v1 bundles; documents-complete turn in 11c | 🟡 |
| L3 | 6 Deterministic validation | v1; "confirm only what was shown" in 11c; policy in 17 | 🟡 |
| L3 | 7 Durable drafts and resume | 13, 19 | ⬜ |
| L3 | 8 Explicit review and consent | v1 | ✅ |
| L3 | 9 Reliable tool and API execution | 14, 18 | ⬜ |
| L3 | 10 Audit and recovery | 15, 18, 21 | ⬜ |
| L4 | 1 Outcome framing | 25 | ⬜ |
| L4 | 2 Structured context assembly | 24 (case brief) | ⬜ |
| L4 | 3 Grounded derivation and prefill | 22 (evidence), 26 (reuse primary contact) | ⬜ |
| L4 | 4 Adaptive dialogue | 25, 26 | ⬜ |
| L4 | 5 Bounded read-and-reason tools | 25, 27 | ⬜ |
| L4 | 6 Cross-step continuity | 23, 25 | ⬜ |
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
| L4 | A1–A9 (L4 §6) |
| L5 | B1–B6 (L5 §6). **B6 extends POC assumption 9** (resume link for an abandoned draft sent without approval) |

## 6. Known issues

| Issue | Resolved in | Status |
| --- | --- | --- |
| Saudi landline rule expects 8 digits after +966; real numbers have 9 | 11c | ⬜ |
| `write_fields` lists `mobile`/`landline` twice for `contact_number` | 11c | ⬜ |
| `domain/draft_merge.py` unused | 11c | ⬜ |
| `docs/eval-notes.md` first entry mentions forced tool choice | 11c | ⬜ |
| Document uploads don't trigger an agent turn | 11c | ⬜ |
| `OFF` (Office) unit code and `office` in seed data and FAQ | 11c | ⬜ |
| Golden rules mention a `submit_inquiry` tool that doesn't exist | 11c | ⬜ |
| `confirm_fields` can confirm values the user never saw | 11c | ⬜ |
| LangGraph warns about deserialising unregistered types from checkpoints | 13 | ⬜ |
| CI runs only `e2e.yml`; no test and lint workflow | 16 | ⬜ |
| `scripts/` not covered by `make lint` (7 E501 lines in `generate_e2e_scripts.py`) | 16 | ⬜ |
| No resend cooldown for OTP or email link | 19 | ⬜ |
| Status API returns a fixed `under_review` and hard-coded steps | 20 | ⬜ |
| Doubt detection and capture heuristics are English-only; no Arabic-Indic digits | 21b | ⬜ |
| `EMAIL_LINK_DEMO` defaults to `true` | Before any non-demo deploy | ⬜ |
| `app/agent/e2e_scripts.py` reads scripts from `tests/` | Only matters for a slim image | ⬜ |
| 4 ESLint fast-refresh warnings in `frontend/src/state/chatStore.tsx` | Low priority | ⬜ |
| Live test 14 failed on mobile in CI (WebKit) | PR #13 (read text from the DOM); confirm with a live run | 🟡 |
