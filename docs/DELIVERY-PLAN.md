# Delivery plan

**Agreed 26 Oct 2026.** The work runs in two parts:

1. **Part A — the 5-day plan.** Every level (L3, L4, L5) working end to end at **demo depth**, so the whole business flow can be shown in one walkthrough.
2. **Part B — the full implementation plan.** Two 2-week sprints, then a short closing phase, take each piece the 5 days built and finish it to its step prompt (11c–31) and its gate in `docs/specs/`.

Progress is tracked in [`docs/STATUS.md`](STATUS.md) §0.

| Phase | Dates | Goal | Ends with |
| --- | --- | --- | --- |
| **A. 5-day plan** | Tue 27 Oct – Mon 2 Nov | Every level demoable end to end | Full walkthrough demo, Mon 2 Nov |
| **B1. Sprint 1** | Tue 3 Nov – Mon 16 Nov | Intake POC to gate quality | **M0 and L3 gates**, sprint review Mon 16 Nov |
| **B2. Sprint 2** | Tue 17 Nov – Mon 30 Nov | Lifecycle to gate quality | **L4 gate**, plus L5 governance (Y2, Y3); sprint review Mon 30 Nov |
| **B3. Closing** | Tue 1 Dec – about Wed 9 Dec | Proactivity to gate quality, production readiness | **L5 gate** |

---

# Part A — the 5-day plan

## A1. How the work is split

Two tracks run in parallel every day:

| Track | Who | Owns | Why |
| --- | --- | --- | --- |
| **Backend** | Claude, as PRs from this project's chat | Services, mocks, state machine, APIs, tokens, workflow, backend tests | Needs no new dependencies; CI (`ci.yml`, from Day 1) runs the tests, because Claude's workspace can't install packages |
| **Frontend and agent** | Swaroop, in Cursor | Pages, cards, routes, new npm or Python dependencies, prompts, agent graphs, live runs | Needs a machine with package registries and an OpenAI key |

**Rules for working in parallel:**
- Both tracks build to the contracts already in the specs. When a PR changes a contract, it updates `docs/spec.md`.
- Each day's backend PR merges first. The frontend branch then rebases on `main` before its own PR.
- Every PR branches from `main`; nothing is stacked.
- Start each day by asking Claude in the project chat: "Start Day N backend".

## A2. The five days

Each day has one Cursor prompt in `prompts/breadth/`, pointing at the parts of the step prompts it covers. **Demo depth** means the happy path works end to end with scripted and live checks; the gate criteria come in Part B.

| Day | Date | Backend (Claude) | Frontend and agent (Swaroop) | End-of-day demo |
| --- | --- | --- | --- | --- |
| **1** | Tue 27 Oct | Minimal harness (Make targets, `ci.yml`, PR template). Then the policy file and generated master data, after 11c merges | Step 11c in full | Intake as before, without Office; review card on document completion; CI green |
| **2** | Wed 28 Oct | Simulated Cenomi (CR registry, faults, notification outbox, dev APIs), signed tokens, verify and resume endpoints, resend cooldown, submit once, submission notifications, tracking API | `react-router-dom`; `/inquiry/verify`, `/inquiry/status/:ref`, `/dev/inbox`; resume hydration; countdowns; tracking link | Inquiry → email in dev inbox → link → verified → submit → submission email → status page |
| **3** | Thu 29 Oct | Call-centre mock and handoff action, Arabic digits and doubt phrases, follow-on backend, scripted stories S2 and S3 | Router (rules + classifier) and redirect replies, handoff card, follow-on divider, prompt updates; one live eval and one `@live` smoke | **L3 at demo depth**: routing, handoff, Arabic, resume, faults, second mall |
| **4** | Fri 30 Oct | State machine (all rows, actor checks), case data, review routing, reviewer directory, Azure AD and Yardi mocks, inline effects and templates, review API, case brief, case links, applicant UI actions | Reviewer console (queue, case page, actions), case page, case agent, new cards (case status, contacts, sales data, re-upload mode) | Reviewer requests a re-upload → applicant answers in chat → back in review; contacts collected |
| **5** | Mon 2 Nov | Approval effects and Yardi handover; `waiting_on_you` from open requests; simulated clock, stalled-review and pending-action triggers, notification policy (tiers, quiet hours), attention API | Reviewer assistant panel; **re-link company and brand** in the console; "Waiting for you" on the status page; "Needs attention" view; story T1; demo script; one live eval and one `@live` run | **Full walkthrough:** intake → both reviews (with a Yardi re-link) → Yardi, a stalled-case alert, an approved reminder |

## A3. What the 5 days cover

Every core function of the §7.1 business flow is built:

| Business flow (requirements §7.1) | Day |
| --- | --- |
| CR check (skip; existing CR → Sign In) | Existing, policy flag Day 1 |
| 12 basic-info fields in bundles, derived values confirmed only once shown | Existing, fix Day 1 |
| One mall per inquiry; international phones; Arabic | Existing; Arabic safety nets Day 3 |
| Email verified by link, mobile by OTP, resend after a set time | Day 2 |
| Complete the application from the emailed link | Day 2 |
| Required and optional documents | Existing; completion turn Day 1 |
| Reference shown and sent by email and SMS with a tracking link | Day 2 |
| Call-centre path (a2) | Day 3 (handoff case) |
| Routing to RLM-Store / RPLM-Media / RPLM-Specialty by unit type and region | Day 4 |
| First level: re-upload, reject with remarks, approve with Azure AD invitation | Day 4 |
| Second level: contacts, estimated sales data, approve or reject | Day 4 |
| Second level: re-link company and brand from Yardi matches | Day 5 |
| Final approval → contact invitations, acceptance email, data to Yardi | Day 5 |
| Tracking: stage, owner and anything waiting on the applicant | Day 2, "Waiting for you" Day 5 |
| Information and action-required notifications (§7.15) | Days 2, 4, 5 |

**Out of scope by design:** real Cenomi systems (all simulated), the existing-tenant prefilled flow (§7.1.2), General Inquiries after sign-in (§7.8.1.1), profile completion after Azure AD sign-in, the Proposal stage (§7.2), and checking document contents.

## A4. What demo depth leaves out

These are about reliability and proof, not missing functions; Part B adds them:
- **Durability:** state stays in memory, so a backend restart loses drafts and cases.
- **Proof:** the parity goldens, the full audit trail, contract tests, frontend-only Playwright, coverage floors, repeated live evals with safety invariants, and most acceptance stories (only S1–S3, T1 and T2 are automated).
- **Robustness:** the gateway's timeouts, retries and error types; reconciled submit; the effects outbox.
- **Should items:** the duplicate check and evidence for derived values.
- **L5 depth:** the drafting agent, escalation, the abandoned-draft trigger, opt-out, throttles and insights.

## A5. Design choices that keep Part B cheap

- **Store.** State stays in the in-memory `SessionStore`, but new fields go where M0 §5.1 and L4 §3.1 put them on `Inquiry`, so step 13 swaps the store without changing callers.
- **State machine.** It is the pure `transition()` from M0 §6 from Day 4; step 14 adds the gateway around it.
- **Routing.** One `route_message()` function; step 16 moves it into the supervisor.
- **Tokens.** Signed with the standard library (`hmac` + `base64` JSON), so the backend track adds no dependency. Sprint 1 may switch to PyJWT.
- **Effects.** Run inline after each transition, keyed by `(inquiry_id, event_seq, effect)` so they can't double-send; Sprint 2 moves them to the `case_effects` outbox.
- **L5 reminders.** Template text; the LLM drafting agent comes in B3.

---

# Part B — the full implementation plan

## B0. How the 5 days connect to the full plan

The step prompts (`prompts/11c`–`31`) remain the full definition of every piece. The 5 days build a slice of most of them; Part B finishes each one. This table is the connection: for every step, what the 5 days built, and what's left and when it's done.

| Step | Built in the 5 days | Left after the 5 days | Finished in |
| --- | --- | --- | --- |
| 11c Pre-baseline fixes | Day 1, in full | — | Day 1 |
| 11d Test harness | Day 1: Make targets, `ci.yml`, PR template | Frontend-only Playwright, scenario catalogue, eval repeats and invariants, `@flaky`, prompt snapshot, coverage, `eval-live` CI job | B1 |
| 12 Baseline parity | — | All: goldens recorded from the post-breadth behaviour, frontend fixtures from goldens, live-eval baseline | B1 |
| 13 Durable state | Inquiry fields kept in memory (§A5) | Postgres store, turn lease, checkpointer, bounded history, retention | B1 |
| 14 Workflow, gateway, submit | Day 2 submit once; Day 4 `transition()` | Gateway (timeouts, retries, error types), reconciled submit, `InquiryPayload`, `submit_pending` notes | B1 |
| 15 Audit trail | — | All | B1 |
| 16 Supervisor and registry | Day 3 `route_message()` | Supervisor, registry (intake, case, reviewer agents move in), Postgres CI matrix; **closes M0** | B1 |
| 17 Policy and master data | Day 1, nearly in full | Remaining policy-flip tests | B1 |
| 18 Simulated Cenomi | Day 2: scenario data, faults, outbox, dev inbox | Contract tests, mock latency, `sandbox`/`live` stubs | B1 |
| 19 Email link and resume | Day 2: tokens, verify, resume, cooldown | "Continue later", polling on the card, cross-device test | B1 |
| 20 Notifications and status page | Day 2, nearly in full | Retried and audited failed sends (needs 14, 15) | B1 |
| 21 Routing and handoff | Day 3: rules, classifier, redirect, two handoff triggers | 60-message fixture set at ≥ 95%, the other handoff triggers, audit events | B1 |
| 21b Arabic, follow-on, duplicates | Day 3: Arabic digits, doubt and capture; follow-on in chat | Duplicate check, follow-on from the tracking page, Arabic golden, `arabic` eval group | B1 |
| 22 L3 gate | — | Evidence for derived values, stories S4–S8, KPI report; **closes L3** | B1 |
| 23 Lifecycle core | Day 4 (in memory, inline effects) | Effects outbox, migration, Postgres | B2 |
| 24 Reviewer console | Day 4 basic; Day 5 re-link | Audit timeline, request history, reason categories, form polish | B2 |
| 25 Case assistant | Day 4 case agent and re-upload; Day 5 "Waiting for you" | Guard rules, expired or closed links, `case` eval group | B2 |
| 26 Contacts and sales data | Day 4 | Edge cases, `contacts` eval group, story T4 | B2 |
| 27 Reviewer assistant | Day 5 | Suggestion audit, guard, `reviewer` eval group | B2 |
| 28 Yardi handover, L4 gate | Day 5 handover, story T1 | Retries and operations flag, L4 KPIs, stories T1–T8; **closes L4** | B2 |
| 29 Event engine and policy | Day 5: clock, tiers, quiet hours | Opt-out, throttles, audit of every decision (B2); engine on the audit stream, migration (B3) | B2, B3 |
| 30 Triggers and attention | Day 5: two triggers, attention view, template reminders | Authority test (B2); escalation, abandoned draft, drafting agent, stories P1–P6 (B3) | B2, B3 |
| 31 Insights, L5 gate | — | All; **closes L5** | B3 |

**Running a step prompt after the 5 days.** In Part B, start each step in Cursor with:

> Read `docs/STATUS.md` (this step's row and §0) and `docs/DELIVERY-PLAN.md` §B0 for what the 5 days already built. Build only what's left for this step, keeping what exists unless the step prompt says otherwise. Then run the step prompt's Tests and Verify.

followed by the step prompt itself.

## B1. Sprint 1 (Tue 3 – Mon 16 Nov): intake POC to gate quality

**Goal:** the M0 gate (G1–G7) and the L3 gate (E1–E9) pass, and all six test layers run. This is Tier A, the POC as quoted.

**First, before step 12:** fix anything the Day 1–5 demos showed was wrong, because step 12 freezes behaviour in the goldens.

| Item | Step | Track |
| --- | --- | --- |
| Rest of the test harness | 11d | Both |
| Parity goldens, frontend fixtures, live-eval baseline | 12 | Claude (goldens), Swaroop (live baseline) |
| Postgres store, lease, checkpointer, bounded history, retention | 13 | Claude |
| Gateway and reconciled submit | 14 | Claude |
| Audit trail with redaction | 15 | Claude |
| Supervisor and registry; router and agents move in; Postgres CI matrix | 16 | Swaroop |
| Policy-flip tests | 17 | Claude |
| Contract tests, mock latency, adapter stubs | 18 | Claude |
| "Continue later", polling, cross-device test | 19 | Swaroop |
| Retried and audited notification sends | 20 | Claude |
| Full routing fixture set, remaining handoff triggers | 21 | Swaroop |
| Duplicate check, follow-on from the tracking page, Arabic golden and eval group | 21b | Both |
| Evidence, stories S4–S8, KPI report, the L3 gate run | 22 | Both |

**Capacity.** About 26 days of work against 20 track-days. If it runs short, these slip first, in this order: evidence (§3.9), duplicate check (§3.12), coverage floors, then the Postgres CI matrix. Each slip is recorded in `docs/STATUS.md` as waived with a reason.

## B2. Sprint 2 (Tue 17 – Mon 30 Nov): lifecycle to gate quality

**Goal:** the L4 gate (X1–X9). For L5, the governance rules hold: Y2 (notification policy) and Y3 (no proactive status change).

| Item | Step | Track |
| --- | --- | --- |
| Effects outbox, migration, case data on Postgres | 23 | Claude |
| Console: audit timeline, request history, reason categories, forms | 24 | Swaroop |
| Case agent guard rules, closed or expired links, `case` eval group | 25 | Swaroop |
| Contacts edge cases, `contacts` eval group, story T4 | 26 | Swaroop |
| Reviewer assistant: suggestion audit, guard, `reviewer` eval group | 27 | Swaroop |
| Yardi retries and operations flag, L4 KPIs, stories T1–T8, the L4 gate run | 28 | Both |
| Notification policy: opt-out, throttles, audit of every decision | 29 (part) | Claude |
| Authority test: no proactive path changes a case | 30 (part) | Claude |

## B3. Closing (Tue 1 Dec – about Wed 9 Dec): proactivity to gate quality

About 7 working days.

| Item | Step | Track |
| --- | --- | --- |
| Event engine on the audit stream, `proactive_items` migration | 29 (rest) | Claude |
| Escalation, abandoned-draft trigger, drafting agent with deterministic checks, stories P1–P6, `proactive` eval group | 30 (rest) | Both |
| Insight report, L5 KPIs, the L5 gate run | 31 | Both |
| Production readiness: `EMAIL_LINK_DEMO` off by default, deployment notes, real adapters for any Cenomi system that has given access | — | Both |

## B4. Gate calendar

| Gate | Rows | Target |
| --- | --- | --- |
| Pre-baseline | P1–P4 | Day 1 (Tue 27 Oct) |
| M0 | G1–G7 | Sprint 1, by Fri 13 Nov |
| L3 | E1–E9 | Sprint 1, by Mon 16 Nov |
| L4 | X1–X9 | Sprint 2, by Mon 30 Nov |
| L5 | Y1–Y6 | Closing, about Wed 9 Dec |

---

## Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Days 4–5 are the heaviest (console, case agent, reviewer assistant) | L5 slips | L5 is the first thing to drop from the 5 days; it moves to Sprint 2 |
| The 5 days build L4 and L5 before M0, so Sprint 1 restructures code that already works | Rework, regressions | The design choices in §A5 keep interfaces stable; goldens are recorded at the start of Sprint 1, so M0's refactor is checked against them |
| Bugs from the 5 days get frozen into the goldens | Wrong behaviour locked in | Fix the demo findings first in Sprint 1, before step 12 |
| Parallel tracks touch the same contracts | Merge conflicts, broken builds | Backend PR merges first each day; contracts come from the specs; frontend rebases |
| Claude's PRs are tested only in CI | Slower feedback | `ci.yml` lands first on Day 1; small PRs |
| Live-model behaviour (Arabic, case assistant) needs prompt tuning | Days or sprint items slip | Live runs on Days 3 and 5; tuning time in each sprint |
| Sprint 1 is over capacity (about 26 days of work for 20 track-days) | L3 Should items slip | The slip order in §B1, recorded as waivers |
| Demos after the 5 days are taken as production-ready | Wrong expectations with Cenomi | Present them as demo depth; the gates in Part B are the quality bar |
| Cenomi answers change an assumption | Rework | Assumptions live in the policy file and mocks; a change is configuration |
