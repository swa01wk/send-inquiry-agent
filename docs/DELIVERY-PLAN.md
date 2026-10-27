# Delivery plan

**Agreed 26 Oct 2026; revised the same day after reviewing requirements §7.1 line by line ([traceability](specs/workflows-7-1.md)) and the whole lifecycle ([POC lifecycle](POC-LIFECYCLE.md)).** The work runs in two parts:

1. **Part A — the 5-day plan.** Every workflow in requirements §7.1 (prospective and existing tenants, self-service and call-centre assisted, both review levels, handover to Yardi) working end to end at **demo depth**, with the **core capabilities of L3, L4 and L5** each shown working (§A4).
2. **Part B — the full implementation plan.** Two 2-week sprints, then a closing phase, take each piece the 5 days built and finish it to its step prompt (11c–31) and its gate in `docs/specs/`.

Scope is locked in [`docs/PRD.md`](PRD.md) v1.0. Progress is tracked in [`docs/STATUS.md`](STATUS.md) §0.

| Phase | Dates | Goal | Ends with |
| --- | --- | --- | --- |
| **A. 5-day plan** | Tue 27 Oct – Mon 2 Nov | All §7.1 workflows and the L3–L5 core capabilities demoable end to end | Full walkthrough demo, Mon 2 Nov |
| **B1. Sprint 1** | Tue 3 Nov – Mon 16 Nov | Intake POC to gate quality | **M0 and L3 gates**, sprint review Mon 16 Nov |
| **B2. Sprint 2** | Tue 17 Nov – Mon 30 Nov | Lifecycle and intake channels to gate quality | **L4 gate** and the channels gate, sprint review Mon 30 Nov |
| **B3. Closing** | Tue 1 Dec – about Wed 16 Dec | Proactivity to gate quality, production readiness | **L5 gate** |

**Revisions on 26 Oct.**
1. The §7.1 review added the call-centre path (§7.1.1 a2, §7.1.2 a2), the existing-tenant journey (§7.1.2 a1) and six smaller rules to the 5 days.
2. The L3–L5 check then put the missing core capabilities back into the 5 days at demo depth: restart-safe drafts, an audit trail, typed failures, form mode and evidence (L3), and a thin proactive layer (L5). To carry the extra load, **Claude also builds the deterministic frontend pages from Day 3** (§A1); Swaroop keeps the agent, prompts, chat cards and live tuning.

---

# Part A — the 5-day plan

## A1. How the work is split

Two tracks run in parallel every day:

| Track | Who | Owns | Why |
| --- | --- | --- | --- |
| **Backend + deterministic UI** | Claude, as PRs from this project's chat | Services, mocks, state machine, APIs, tokens, workflow, proactive engine, backend tests; **from Day 3, also pages and cards with no model in them**: form mode, reviewer console, tenant portal, "Needs attention", `/dev` landing | Needs no new dependencies (`react-router-dom` arrives on Day 2 from Swaroop); CI (`ci.yml`, from Day 1) runs the backend tests, Vitest and Playwright, because Claude's workspace can't install packages |
| **Agent and conversational UI** | Swaroop, in Cursor | Prompts and agent graphs (intake modes, router, case agent, reviewer assistant), chat cards, chat-side routes, new npm or Python dependencies, live runs and tuning | Needs a machine with package registries and an OpenAI key; prompt quality needs live iteration |

**Rules for working in parallel:**
- Both tracks build to the contracts already in the specs. When a PR changes a contract, it updates `docs/spec.md`.
- Each day's backend PR merges first. The frontend branch then rebases on `main` before its own PR.
- Every PR branches from `main`; nothing is stacked.
- Start each day by asking Claude in the project chat: "Start Day N backend".

## A2. The five days

Each day has one Cursor prompt in `prompts/breadth/`, pointing at the parts of the step prompts it covers. **Demo depth** means the happy path works end to end with scripted and live checks; the gate criteria come in Part B.

| Day | Date | Claude (backend + deterministic UI) | Swaroop (agent + conversational UI) | End-of-day demo |
| --- | --- | --- | --- | --- |
| **1** | Tue 27 Oct | Minimal harness (Make targets, `ci.yml`, PR template). Then the policy file and generated master data, after 11c merges | Step 11c in full, including the document numbers on the documents card | Intake as before, without Office; document numbers on the documents card; review card on document completion; CI green |
| **2** | Wed 28 Oct | Simulated Cenomi (CR registry, faults, notification outbox, dev APIs), signed tokens, verify and resume endpoints, resend cooldown, submit once, submission notifications, tracking API. **L3 core:** restart-safe store (JSON snapshot behind `SessionStore`), audit log v0 (append-only, redacted), thin gateway (timeout + typed failure on every mock call) | `react-router-dom`; `/inquiry/verify`, `/inquiry/status/:ref`, `/dev/inbox`; resume hydration; countdowns; tracking link | Inquiry → email in dev inbox → link → verified → **restart the backend, carry on** → submit → submission email → status page |
| **3** | Thu 29 Oct | Call-centre mock and handoff action, Arabic digits and doubt phrases, follow-on backend, stories S2 and S3. **L3 core:** form mode (backend and its UI: `form_mode` card, editable draft panel, actions without an agent turn); evidence on `update_draft` and on the confirm card | Router (rules + classifier) and redirect replies, handoff card, follow-on divider; prompt asks for evidence on derived values; one live eval and one `@live` smoke | **Self-service intake with every L3 capability**: routing, handoff, Arabic, resume, faults, second mall, evidence, **model down → finish in form mode** |
| **4** | Fri 30 Oct | State machine (all rows, actor checks), case data, review routing, reviewer directory, Azure AD and Yardi mocks, inline effects and templates (incl. the automatic contacts request), review API, case brief, case links, applicant UI actions; audit events for every transition. **Reviewer console UI** (queue, case page with brief and audit timeline, legal actions) | Case agent (prompt, tools, `/inquiry/case`), chat cards (case status, contacts, sales data, re-upload mode), story T2 | Reviewer requests a re-upload → applicant answers in chat → back in review; first approval opens a contacts request; **audit timeline shows every step and actor** |
| **5** | Mon 2 Nov | Yardi handover; re-link actions; `waiting_on_you`; intake-channels backend (`staff` source, assisted mode, `complete` link, Proceed, tenant directory, prefill, contacts prefill and remove, Guest Service role, `redirected` state); `/api/dev/reset`. **L5 core:** simulated clock, triggers (stalled review, escalation, unanswered request), notification policy (tiers, quiet hours, once per period), attention API with accepted and dismissed counts. **UI:** `/dev` landing (personas, Reset, clock buttons), tenant portal, "Needs attention", re-link pickers, "Waiting for you" | Reviewer assistant (brief, Yardi matches, drafted remarks **and drafted reminders** for "Needs attention"); assisted-mode prompt and `/callcentre` chat; existing-tenant prompt; `basic_info_review` card; story T1; demo script; one live eval and one `@live` run | **Full walkthrough** of every §7.1 workflow and the L3–L5 core (§A3, §A4) |

## A3. What the 5 days cover

Every workflow in requirements §7.1 runs end to end. Line-by-line coverage is in [workflows-7-1.md](specs/workflows-7-1.md); the demo walks these paths:

| Workflow | Path in the demo | Day |
| --- | --- | --- |
| §7.1.1 a1 — prospective, self-service | Chat on the sign-in page → CR or skip → basic info → email link and OTP → documents (with numbers) → submit → tracking | 1–3 |
| §7.1.1 a2 — prospective, via the call centre | Executive in `/callcentre` raises it with the agent → link emailed → applicant opens it (email verified) → reviews basic info → **Proceed** → OTP → documents → submit | 5 |
| §7.1.2 a1 — existing tenant, signed in | `/tenant` → Leasing Opportunities → Raise inquiry → prefilled details and property → confirm → submit → My inquiries | 5 |
| §7.1.2 a2 — existing tenant, via the call centre | Executive enters an existing CR → **Continue for them** (or **Ask them to sign in**) → prefilled → link → applicant completes | 5 |
| §7.1 — existing tenant on the public page | Existing CR → Sign in button → Leasing Opportunities (`sign_in`); or prefilled inquiry (`allow_inquiry`) | 5 |
| §7.1.1 b / §7.1.2 b — first-level review | Routed to the right RLM / RPLM queue → re-upload loop, reject with remarks, or approve → Azure AD invitation (only if no account) → automatic contacts request | 4 |
| §7.1.1 c / §7.1.2 c — second-level review | Lead — second review → contacts (prefilled for existing tenants, reviewer can remove one), estimated sales data, Yardi re-link → approve (invitations for new contacts, acceptance email, data to Yardi) or reject | 4–5 |
| Tracking throughout | Status page with stage, owner role and "Waiting for you" | 2, 5 |

**Out of scope by design:** real Cenomi systems (all simulated), Super Admin onboarding of existing tenants (§7.1, user management), profile completion after Azure AD sign-in, General Inquiries after sign-in (§7.8.1.1), the Proposal stage (§7.2) and checking document contents.

## A4. Agentic core in the 5 days (L3–L5)

Every framework capability is shown working in the 5-day demo. **Full** = as the spec describes, hardened later only by tests and gates. **Thin** = the real behaviour on a simpler base, finished in Part B.

| Level | Capability | In the 5 days | Day | Depth | Finished in |
| --- | --- | --- | --- | --- | --- |
| L1–L2 | Complete by form; conversational with no field loss; handoff | Cards and review card; form mode when the model is down; handoff to the call centre | Built, 3 | Thin (form mode) | S1 (story S13) |
| L3 | 1 Intent routing | Rules + classifier; redirects; mid-intake stays in intake | 3 | Thin (30-message set) | S1 (60 messages, ≥ 95%) |
| L3 | 2 Multi-field extraction with provenance | Bundles (built); evidence on derived values, shown on the confirm card | Built, 3 | Full | S1 (tests) |
| L3 | 3 Entity resolution | Malls, categories, Arabic names; Yardi companies and brands | 1, 5 | Full | — |
| L3 | 4 Verified context reuse | CR prefill; follow-on inquiry; tenant-record prefill | Built, 3, 5 | Full | S1 (follow-on from tracking page) |
| L3 | 5 Adaptive slot filling | Bundles; documents-complete turn | Built, 1 | Full | — |
| L3 | 6 Deterministic validation | Validators, policy file, confirm-only-shown, staff values need Proceed | Built, 1, 5 | Full | — |
| L3 | 7 Durable drafts and resume | Resume from the link on any device; **survives a backend restart** (JSON snapshot) | 2 | Thin (file, not Postgres) | S1 (Postgres, lease) |
| L3 | 8 Review and consent | Review card; UI-only consent | Built | Full | — |
| L3 | 9 Reliable execution | Submit once; every mock call has a timeout and a typed failure; faults on demand | 2 | Thin (no retries, no reconciliation) | S1 (gateway, reconciled submit) |
| L3 | 10 Audit and recovery | Audit log v0 (turns, tools, actions, transitions, notifications; redacted); handoff; form mode; never claims success early | 2–4 | Thin (in the snapshot, not a table) | S1 (redaction tests, `inquiry_events`) |
| L4 | 1 Outcome framing | Case assistant: stage, owner, next step | 4 | Full | S2 (guard rules) |
| L4 | 2 Structured context assembly | Grounded case brief | 4 | Full | — |
| L4 | 3 Grounded derivation and prefill | Evidence; tenant-record prefill; "that's me" reuse | 3–5 | Full | — |
| L4 | 4 Adaptive dialogue | One contacts bundle; re-upload asks only for what's requested | 4 | Full | S2 (eval group) |
| L4 | 5 Bounded read tools | Case and reviewer allowlists | 4–5 | Full | — |
| L4 | 6 Cross-step continuity | Executive → applicant; case links reopen the same case; no intake questions after submit | 4–5 | Full | — |
| L4 | 7 Reviewer assistance | Brief, Yardi suggestions, drafted remarks | 5 | Full | S2 (suggestion audit) |
| L4 | 8 Exception and rework reduction | Targeted re-upload; automatic contacts request | 4 | Thin (no duplicate check) | S1 (duplicate check) |
| L4 | 9 Human collaboration | Actor checks; assistant never decides; Use fills, never submits | 4–5 | Full | S2 (audit of suggestions used) |
| L4 | 10 Outcome tracking | Tracking page, "Waiting for you", My inquiries | 2, 5 | Full | — |
| L5 | 1 Event and state awareness | Triggers evaluated on every clock tick over case states | 5 | Thin (case states, not the audit stream) | Closing |
| L5 | 2 Next-best action | "Needs attention" ranked by age against threshold, escalations first | 5 | Full | — |
| L5 | 3 Proactive preparation | Reviewer assistant drafts the reminder for an unanswered request | 5 | Thin (no deterministic draft checks) | Closing |
| L5 | 4 Cross-role coordination | Escalation to the region manager after a second threshold | 5 | Full | — |
| L5 | 5 Process optimisation | Counts of items raised, sent, dismissed by reason | 5 | Thin (no insight report) | Closing |
| L5 | 6 Bounded automation | Tiers: internal flags auto; applicant reminders need approval | 5 | Full | — |
| L5 | 7 Attention management | Quiet hours; once per case per period | 5 | Thin (no throttles or opt-out) | Closing |
| L5 | 8 Feedback and learning | Accepted vs dismissed recorded per item | 5 | Thin (no KPI comparison on/off) | Closing |

**What demo depth still leaves out** (proof and hardening, not capabilities): Postgres, the turn lease and checkpointer; gateway retries and reconciled submit; the effects outbox; golden transcripts, contract tests, frontend-only Playwright, coverage floors and repeated live evals with safety invariants; most acceptance stories (only S1–S3, T1, T2 automated); the duplicate check; the abandoned-draft trigger, throttles, opt-out and the insight report.

## A5. Design choices that keep Part B cheap

- **Store.** The in-memory `SessionStore` writes a JSON snapshot of every inquiry (draft, cards, case data, audit log v0) to `DATA_DIR` after each turn and reloads it at start-up, so a restart loses nothing in a demo. New fields go where M0 §5.1, L4 §3.1 and intake-channels §3.8 put them on `Inquiry`, so step 13 swaps in Postgres without changing callers.
- **Audit log v0.** One `AuditLog.record(inquiry_id, type, actor, payload)` with the M0 §8 event types and its redaction allowlist from Day 2; step 15 moves it to `inquiry_events` and adds the tests.
- **Thin gateway.** Every mock call goes through one wrapper with a timeout and the four error kinds from M0 §7.1; step 14 adds retries, audit of latency and reconciled submit.
- **Proactive engine.** Triggers read case states on each tick of the `Clock`; step 29 moves them onto the audit stream. Reminder text comes from the reviewer assistant; step 30 adds the deterministic draft checks.
- **State machine.** It is the pure `transition()` from M0 §6 from Day 4; step 14 adds the gateway around it.
- **One agent, several modes.** Assisted and existing-tenant intake are prompt variants and tool allowlists of the same intake agent, so step 16's registry registers them as configuration, not copies.
- **One prefill function.** `prefill_from_tenant` serves the executive, the signed-in tenant and the public-page `allow_inquiry` path.
- **Routing.** One `route_message()` function; step 16 moves it into the supervisor.
- **Tokens.** Signed with the standard library (`hmac` + `base64` JSON), so the backend track adds no dependency. Sprint 1 may switch to PyJWT.
- **Effects.** Run inline after each transition, keyed by `(inquiry_id, event_seq, effect)` so they can't double-send; Sprint 2 moves them to the `case_effects` outbox.

---

# Part B — the full implementation plan

## B0. How the 5 days connect to the full plan

The step prompts (`prompts/11c`–`31`) remain the full definition of every piece. The 5 days build a slice of most of them; Part B finishes each one. This table is the connection: for every step, what the 5 days built, and what's left and when it's done.

| Step | Built in the 5 days | Left after the 5 days | Finished in |
| --- | --- | --- | --- |
| 11c Pre-baseline fixes | Day 1, in full (including document numbers) | — | Day 1 |
| 11d Test harness | Day 1: Make targets, `ci.yml`, PR template | Frontend-only Playwright, scenario catalogue, eval repeats and invariants, `@flaky`, prompt snapshot, coverage, `eval-live` CI job | B1 |
| 12 Baseline parity | — | All: goldens recorded from the post-breadth behaviour, frontend fixtures from goldens, live-eval baseline | B1 |
| 13 Durable state | Day 2: restart-safe JSON snapshot behind `SessionStore` (§A5) | Postgres store, turn lease, checkpointer, bounded history, retention | B1 |
| 14 Workflow, gateway, submit | Day 2 submit once and thin gateway (timeouts, error kinds); Day 4 `transition()` | Retries, latency audit, reconciled submit, `InquiryPayload`, `submit_pending` notes | B1 |
| 15 Audit trail | Days 2–4: audit log v0 with redaction allowlist, timeline in the console | `inquiry_events` table, redaction tests, `audit_dump.py`, correlation ids | B1 |
| 16 Supervisor and registry | Day 3 `route_message()` | Supervisor, registry (intake in all three modes, case, reviewer agents), Postgres CI matrix; **closes M0** | B1 |
| 17 Policy and master data | Day 1, nearly in full | Remaining policy-flip tests | B1 |
| 18 Simulated Cenomi | Day 2: scenario data, faults, outbox, dev inbox | Contract tests, mock latency, `sandbox`/`live` stubs | B1 |
| 19 Email link and resume | Day 2: tokens, verify, resume, cooldown | "Continue later", polling on the card, cross-device test | B1 |
| 20 Notifications and status page | Day 2, nearly in full | Retried and audited failed sends (needs 14, 15) | B1 |
| 21 Routing and handoff | Day 3: rules, classifier, redirect, two handoff triggers, form mode | 60-message fixture set at ≥ 95%, the other handoff triggers, story S13 | B1 |
| 21b Arabic, follow-on, duplicates | Day 3: Arabic digits, doubt and capture; follow-on in chat | Duplicate check, follow-on from the tracking page, Arabic golden, `arabic` eval group | B1 |
| 21c Intake channels | Day 5: assisted mode, link and Proceed, tenant portal, prefill, contacts prefill and remove | Stories S9–S12, T10, `channels` eval group, access tests, prompt snapshots for both modes | B1 (S9–S12, so E10 can close L3); B2 (T10, C5) |
| 22 L3 gate | Day 3 evidence for derived values | Stories S4–S8, KPI report; **closes L3 (E1–E10)** | B1 |
| 23 Lifecycle core | Day 4 (in memory, inline effects, automatic contacts request, `has_account`) | Effects outbox, migration, Postgres | B2 |
| 24 Reviewer console | Day 4 queue, case page, actions, audit timeline; Day 5 re-link, channel labels, Remove contact | Request history, reason categories, funnel and pending approvals (Should), form polish | B2 |
| 25 Case assistant | Day 4 case agent and re-upload; Day 5 "Waiting for you", "Lead" wording | Guard rules, expired or closed links, `case` eval group | B2 |
| 26 Contacts and sales data | Day 4; Day 5 existing-tenant prefill | Edge cases, `contacts` eval group, story T4 | B2 |
| 27 Reviewer assistant | Day 5 | Suggestion audit, guard, `reviewer` eval group | B2 |
| 28 Yardi handover, L4 gate | Day 5 handover, story T1 | Retries and operations flag, L4 KPIs, stories T1–T10; **closes L4 and C5** | B2 |
| 29 Event engine and policy | Day 5: clock, notification policy (tiers, quiet hours, once per period), attention API | Engine on the audit stream, throttles, opt-out, audit of every decision, migration | B3 |
| 30 Triggers and attention | Day 5: stalled review, escalation, unanswered-request triggers; "Needs attention"; reminders drafted by the reviewer assistant | Abandoned-draft trigger, late-duplicate trigger, deterministic draft checks, stories P1–P6, `proactive` eval group | B3 |
| 31 Insights, L5 gate | Day 5: accepted and dismissed counts | Insight report, L5 KPIs with proactivity on and off; **closes L5** | B3 |

**Running a step prompt after the 5 days.** In Part B, start each step in Cursor with:

> Read `docs/STATUS.md` (this step's row and §0) and `docs/DELIVERY-PLAN.md` §B0 for what the 5 days already built. Build only what's left for this step, keeping what exists unless the step prompt says otherwise. Then run the step prompt's Tests and Verify.

followed by the step prompt itself.

## B1. Sprint 1 (Tue 3 – Mon 16 Nov): intake POC to gate quality

**Goal:** the M0 gate (G1–G7) and the L3 gate (E1–E10) pass, and all six test layers run. This is Tier A, the POC as quoted, now covering every intake channel.

**First, before step 12:** fix anything the Day 1–5 demos showed was wrong, because step 12 freezes behaviour in the goldens.

| Item | Step | Track |
| --- | --- | --- |
| Rest of the test harness | 11d | Both |
| Parity goldens (including an assisted and an existing-tenant transcript), frontend fixtures, live-eval baseline | 12 | Claude (goldens), Swaroop (live baseline) |
| Postgres store, lease, checkpointer, bounded history, retention | 13 | Claude |
| Gateway and reconciled submit | 14 | Claude |
| Audit trail with redaction (including `staff` actors) | 15 | Claude |
| Supervisor and registry; router and all agent modes move in; Postgres CI matrix | 16 | Swaroop |
| Policy-flip tests | 17 | Claude |
| Contract tests, mock latency, adapter stubs | 18 | Claude |
| "Continue later", polling, cross-device test | 19 | Swaroop |
| Retried and audited notification sends | 20 | Claude |
| Full routing fixture set, remaining handoff triggers | 21 | Swaroop |
| Duplicate check, follow-on from the tracking page, Arabic golden and eval group | 21b | Both |
| Intake channels: stories S9–S12, access tests, `channels` eval group | 21c | Both |
| Form mode hardening (L1 baseline): story S13, recovery back to chat | 21 | Both |
| Stories S4–S8, KPI report, the L3 gate run | 22 | Both |

**Capacity.** About 27 days of work against 20 track-days (the 5 days now start the store, audit, gateway, form mode and evidence). If it runs short, these slip first, in this order: duplicate check (§3.12), coverage floors, the Postgres CI matrix, then the `channels` live-eval group. Form mode doesn't slip: it's the framework's L1 baseline. Each slip is recorded in `docs/STATUS.md` as waived with a reason. The intake channels themselves don't slip: they're a business workflow, not a Should item.

## B2. Sprint 2 (Tue 17 – Mon 30 Nov): lifecycle and channels to gate quality

**Goal:** the L4 gate (X1–X9) and channels row C5.

| Item | Step | Track |
| --- | --- | --- |
| Effects outbox, migration, case data on Postgres | 23 | Claude |
| Console: request history, reason categories, forms | 24 | Claude |
| Case agent guard rules, closed or expired links, `case` eval group | 25 | Swaroop |
| Contacts edge cases (including existing-tenant prefill and removal), `contacts` eval group, stories T4 and T10 | 26, 21c | Swaroop |
| Reviewer assistant: suggestion audit, guard, `reviewer` eval group | 27 | Swaroop |
| Funnel and pending-approvals view in the console (Should, §7.14) | 24 | Claude |
| Yardi retries and operations flag, L4 KPIs, stories T1–T10, the L4 gate run | 28 | Both |

## B3. Closing (Tue 1 Dec – about Wed 16 Dec): proactivity and production readiness

About 12 working days, with a thin L5 already running from Day 5.

| Item | Step | Track |
| --- | --- | --- |
| Event engine on the audit stream, throttles, opt-out, audit of every policy decision, `proactive_items` migration | 29 | Claude |
| Abandoned-draft and late-duplicate triggers, deterministic checks on drafted reminders, stories P1–P6, `proactive` eval group | 30 | Both |
| Insight report, L5 KPIs, the L5 gate run | 31 | Both |
| Production readiness: `EMAIL_LINK_DEMO` off by default, deployment notes, real adapters for any Cenomi system that has given access | — | Both |

## B4. Gate calendar

| Gate | Rows | Target |
| --- | --- | --- |
| Pre-baseline | P1–P5 | Day 1 (Tue 27 Oct) |
| M0 | G1–G7 | Sprint 1, by Fri 13 Nov |
| L3 | E1–E10 | Sprint 1, by Mon 16 Nov |
| Intake channels | C1–C4, C6 with L3; C5 with L4 | Mon 16 Nov; Mon 30 Nov |
| L4 | X1–X9 | Sprint 2, by Mon 30 Nov |
| L5 | Y1–Y6 | Closing, about Wed 16 Dec |

---

## Inputs to ask Cenomi for

These don't block anything (each has an assumption), but they'd make the POC match Cenomi's real process more closely. Full list in [POC lifecycle](POC-LIFECYCLE.md) §7.

1. The §7.1 flow diagrams as source files (the embedded ones can't be read).
2. The notification content and trigger document referenced in §7.15.
3. The UX wireframes and UI designs referenced in the requirements.
4. Whether anyone besides RLM / RPLM verifies leads ("Cenomi Leasing Staff", Regional Sales Manager).
5. Whether the POC UI should be in Arabic (right-to-left).
6. The open questions in each spec (`docs/STATUS.md` §5).

## Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Day 5 is the heaviest (channels, Yardi, reviewer assistant, thin L5) | Day 5 slips | Split across both tracks; if it slips, drop in this order: drafted reminders (template text instead), escalation trigger, reviewer assistant to Sprint 2 — the workflows and the rest of L5 stay in the demo |
| Claude's frontend code is tested only in CI | UI bugs found late | Claude's pages have no model in them and get Vitest and Playwright tests in the same PR; Swaroop reviews them in the browser each evening |
| The 5 days build L4 and the channels before M0, so Sprint 1 restructures code that already works | Rework, regressions | The design choices in §A5 keep interfaces stable; goldens are recorded at the start of Sprint 1, so M0's refactor is checked against them |
| Bugs from the 5 days get frozen into the goldens | Wrong behaviour locked in | Fix the demo findings first in Sprint 1, before step 12 |
| Parallel tracks touch the same contracts | Merge conflicts, broken builds | Backend PR merges first each day; contracts come from the specs; frontend rebases |
| Claude's PRs are tested only in CI, and Playwright doesn't run in CI on PRs | Slower feedback; UI regressions caught late | `ci.yml` (BE, FE) landed on Day 1; small PRs; Swaroop runs `make e2e-int` locally before merging a Claude PR that touches the UI or SSE contracts |
| Live-model behaviour (Arabic, assisted mode, case assistant) needs prompt tuning | Days or sprint items slip | Live runs on Days 3 and 5; tuning time in each sprint |
| Sprint 1 is over capacity (about 27 days of work for 20 track-days) | L3 Should items slip | The slip order in §B1, recorded as waivers |
| The flow diagrams can't be read at their embedded resolution | A step only shown in a diagram is missed | Structure checked against the text ([traceability](specs/workflows-7-1.md)); ask Cenomi for the source diagrams |
| Demos after the 5 days are taken as production-ready | Wrong expectations with Cenomi | Present them as demo depth; the gates in Part B are the quality bar |
| Cenomi answers change an assumption | Rework | Assumptions live in the policy file and mocks; a change is configuration |
