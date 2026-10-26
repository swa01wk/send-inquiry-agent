# Delivery plan: 5-day breadth build, then two 2-week sprints

**Agreed 26 Oct 2026.** First, every level (L3, L4, L5) working end to end at **demo depth** in 5 days. Then two sprints harden it to the gates in `docs/specs/`. Progress is tracked in [`docs/STATUS.md`](STATUS.md) §0.

| Phase | Dates | Goal | Review |
| --- | --- | --- | --- |
| **Breadth** | Tue 27 Oct – Mon 2 Nov (5 working days) | Every level demoable end to end: intake → two review levels → Yardi, plus a thin proactive layer | Demo, Mon 2 Nov |
| **Sprint 1** | Tue 3 Nov – Mon 16 Nov | **Intake POC to gate quality:** the M0 gate and the L3 gate, and the full test harness | Sprint review, Mon 16 Nov |
| **Sprint 2** | Tue 17 Nov – Mon 30 Nov | **Lifecycle to gate quality:** the L4 gate, and L5's governance rules | Sprint review, Mon 30 Nov |

## 1. How the work is split

Two tracks run in parallel every day:

| Track | Who | Owns | Why |
| --- | --- | --- | --- |
| **Backend** | Claude, as PRs from this project's chat | Services, mocks, state machine, APIs, tokens, workflow, backend tests | No new dependencies needed; CI (`ci.yml`, from Day 1) runs the tests, because Claude's workspace can't install packages |
| **Frontend and agent** | Swaroop, in Cursor | Pages, cards, routes, new npm or Python dependencies, prompts, agent graphs, live runs | Needs a working machine with registries and an OpenAI key |

**Rules for working in parallel:**
- Both tracks build to the contracts already in the specs. When a PR changes a contract, it updates `docs/spec.md`.
- Each day's backend PR is merged first. The frontend branch then rebases on `main` before its own PR.
- Every PR branches from `main`; nothing is stacked.
- Start each day by asking Claude in the project chat: "Start Day N backend".

## 2. Breadth: 5 days at demo depth

Each day has one Cursor prompt in `prompts/breadth/`, and each prompt points at the parts of the step prompts (11c–31) it covers. **Demo depth** means it works end to end with scripted and live checks on the happy path, but the gate criteria are deferred to the sprints.

| Day | Date | Backend (Claude) | Frontend and agent (Swaroop) | End-of-day demo |
| --- | --- | --- | --- | --- |
| **1** | Tue 27 Oct | Minimal harness: Make targets, `ci.yml`, PR template. Then the policy file and generated master data (after 11c merges) | Step 11c in full | Intake as before, without Office; review card on document completion; CI green |
| **2** | Wed 28 Oct | Simulated Cenomi (CR registry, faults, notification outbox, dev APIs), signed tokens, verify and resume endpoints, resend cooldown, submit once, submission notifications, tracking API | `react-router-dom`; `/inquiry/verify`, `/inquiry/status/:ref`, `/dev/inbox`; resume hydration; countdowns; tracking link | Inquiry → email in dev inbox → link → verified → submit → submission email → status page |
| **3** | Thu 29 Oct | Call-centre mock and handoff action, Arabic digits and doubt phrases, follow-on inquiry backend, scripted stories S2 and S3 | Router (rules + classifier) and redirect replies, handoff card, follow-on divider, prompt updates; one live eval and one `@live` smoke | **L3 at demo depth**: routing, handoff, Arabic, resume, faults, second mall |
| **4** | Fri 30 Oct | State machine (all rows, actor checks), case data, review routing, reviewer directory, Azure AD and Yardi mocks, inline effects and templates, review API, case brief, case links, applicant UI actions | Reviewer console (queue, case page, actions), case page, case agent (prompt and tools), new cards (case status, contacts, sales data, re-upload mode) | Reviewer requests a re-upload → applicant answers in chat → back in review |
| **5** | Mon 2 Nov | Approval effects and Yardi handover; simulated clock, stalled-review and pending-action triggers, notification policy (tiers, quiet hours), attention API | Reviewer assistant panel, "Needs attention" view, scripted story T1, demo script, one live eval and one `@live` run | **Full walkthrough:** intake → both reviews → Yardi, a stalled-case alert, an approved reminder |

**Cut from breadth, done in the sprints:** Postgres durability, the parity goldens, the full audit trail, the gateway's retries and error types, contract tests, frontend-only Playwright, coverage floors, repeated live evals with invariants, the supervisor and registry, duplicate check, evidence for derived values, KPI reports, most acceptance stories, the L5 drafting agent and insights.

**Breadth design choices that keep the sprints cheap:**
- **Store.** State stays in the in-memory `SessionStore`. New fields go where M0 §5.1 and L4 §3.1 put them on `Inquiry`, so step 13 swaps the store without changing callers.
- **State machine.** It is the pure `transition()` from M0 §6 from the start; step 14 adds the gateway around it.
- **Routing.** The router is one `route_message()` function; step 16 moves it into the supervisor.
- **Tokens.** Signed with the standard library (`hmac` + `base64` JSON), so the backend track adds no dependency. Sprint 1 may switch to PyJWT.
- **Effects.** Run inline after each transition, keyed by `(inquiry_id, event_seq, effect)` so they can't double-send; Sprint 2 moves them to the `case_effects` outbox.
- **L5 drafts.** Reminders use template text; the LLM drafting agent comes in Sprint 2 or later.

## 3. Sprint 1 (3–16 Nov): intake POC to gate quality

**Goal:** the M0 gate (G1–G7) and the L3 gate (E1–E9) pass, and all six test layers run. This is Tier A, the POC as quoted.

| Item | From | Track |
| --- | --- | --- |
| Rest of the test harness: frontend-only Playwright, scenario catalogue, eval repeats and safety invariants, `@flaky`, coverage | 11d | Both |
| Baseline parity goldens from the breadth behaviour; frontend fixtures from goldens; live-eval baseline | 12 | Claude (goldens), Swaroop (live baseline) |
| Durable store on Postgres, turn lease, checkpointer, bounded history, retention | 13 | Claude |
| Gateway (timeouts, retries, error types), reconciled submit | 14 | Claude |
| Audit trail with redaction | 15 | Claude |
| Supervisor and registry; move the router in; Postgres CI matrix | 16 | Swaroop |
| Contract tests, mock latency | 18 (rest) | Claude |
| "Continue later" link, polling on the verification card, cross-device test | 19 (rest) | Swaroop |
| Duplicate check; follow-on from the tracking page | 21b (rest) | Claude |
| Evidence for derived values, stories S4–S8, KPI report, the L3 gate run | 22 | Both |

**Capacity.** About 26 days of work against 20 track-days. If it runs short, these slip first, in this order: evidence (§3.9), duplicate check (§3.12), coverage floors, then the Postgres CI matrix. Each slip is recorded in `docs/STATUS.md` as waived with a reason.

## 4. Sprint 2 (17–30 Nov): lifecycle to gate quality

**Goal:** the L4 gate (X1–X9). For L5, the governance rules hold: Y2 (notification policy) and Y3 (no proactive status change).

| Item | From | Track |
| --- | --- | --- |
| Effects outbox, Alembic migration, document history, reviewer actor checks on Postgres | 23 (rest) | Claude |
| Console: audit timeline, request history, legal-action forms, reason categories | 24 (rest) | Swaroop |
| Case agent guard rules, closed or expired links, full status page | 25 (rest) | Swaroop |
| Contacts edge cases, the contacts live-eval group | 26 (rest) | Swaroop |
| Reviewer assistant: drafted notes into forms, suggestion audit, the reviewer live-eval group | 27 (rest) | Swaroop |
| Yardi retries and operations flag, L4 KPIs, stories T1–T8, the L4 gate run | 28 | Both |
| Notification policy: opt-out, throttles, audit of every decision; the authority test | 29, 30 (part) | Claude |

**Deferred after 30 Nov:** the rest of the L5 gate (Y1, Y4–Y6), the drafting agent, late-duplicate trigger, insight report (31), and sandbox adapters when Cenomi grants access.

## 5. Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Days 4–5 are the heaviest (console, case agent, reviewer assistant) | L5 slips | L5 is the first thing to drop from breadth; it moves to Sprint 2 |
| Parallel tracks touch the same contracts | Merge conflicts, broken builds | Backend PR merges first each day; contracts come from the specs; frontend rebases |
| Claude's PRs are tested only in CI | Slower feedback | `ci.yml` lands first on Day 1; small PRs |
| Live-model behaviour (Arabic, case assistant) needs prompt tuning | Days or sprint items slip | Live runs are planned on Days 3 and 5; tuning time is in each sprint |
| Breadth code is restructured by M0 in Sprint 1 | Rework | The design choices in §2 keep interfaces stable; the parity suite catches behaviour changes |
| Cenomi answers change an assumption | Rework | Assumptions sit in the policy file and mocks; a change is configuration |
