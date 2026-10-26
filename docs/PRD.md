# Send Inquiry Agent — POC product requirements (PRD v1.0)

**Status: LOCKED** · Version 1.0 · Locked 26 Oct 2026 · Git tag `poc-prd-v1.0` · Owner: Swaroop Shivakumar

This PRD fixes the scope of the Cenomi Send Inquiry Agent POC. The detailed behaviour lives in the specs it points to; together they are the baseline every build step is checked against. Any change after this point follows §11 (change control).

## 1. Problem and objective

Prospective and existing tenants reach Cenomi Tenant Central through a long "Send us an inquiry" form, and everything after submission — two levels of review, re-uploads, contacts, sales data, handover to Yardi — runs on email and manual follow-up.

**Objective.** Replace the form with a friendly, genuinely agentic assistant that:
1. covers the **whole inquiry-to-lead process** in requirements v2.1.7.1 §7.1 — every way in, both review levels and the handover to Yardi;
2. reaches the **Agent Capability Maturity Framework** levels L3 (reliable intake), L4 (outcome assistance for applicants and reviewers) and L5 (governed proactivity), proven by behaviour, not demos;
3. runs entirely against **simulated Cenomi systems**, so nothing waits on Cenomi access, and each simulation can be replaced by the real system by configuration.

The client's first priority is conversational friendliness: the agent helps people fill the inquiry rather than asking for every field one at a time.

## 2. Users

| User | Needs |
| --- | --- |
| Prospective tenant (primary contact) | Raise an inquiry in a few messages; verify contact; upload documents; track it; answer review requests without starting over |
| Existing tenant | Raise an inquiry from Leasing Opportunities with known details prefilled; see all their inquiries |
| Call-centre executive (Customer Relations) and mall Guest Service desk | Raise an inquiry for a caller or visitor and hand it to them to complete |
| RLM-Store, RPLM-Media, RPLM-Specialty | Verify inquiries in their queue at two levels, with a grounded summary and help preparing requests; keep every decision |

## 3. Scope

### 3.1 In scope

| Area | What the POC delivers | Spec |
| --- | --- | --- |
| Intake, self-service (§7.1.1 a1) | CR check or skip; 12 basic-info fields collected in bundles; derived values confirmed only after being shown; one product line (Store, Media, Specialty) and one mall; international phone numbers; Arabic | `docs/spec.md`; [pre-baseline-fixes](specs/pre-baseline-fixes.md); [L3](specs/l3-reliable-intake.md) |
| Verification | Email by link (the click verifies), mobile by OTP, resend after a set time; resume from the link on any device | L3 §3.2–3.3 |
| Documents | Company and Brand Profile required; CR, VAT, National ID, National Address optional, with their numbers; presence, type and size only | Pre-baseline F2, F5 |
| Submit and tracking | Review and consent; one reference per inquiry; reference by email and SMS; private tracking page | L3 §3.4; [M0](specs/m0-modular-core.md) §7 |
| Call-centre and Guest Service intake (§7.1.1 a2, §7.1.2 a2) | Staff raise the inquiry with the agent; the applicant completes it from a link (email verified, review, Proceed, OTP, documents, submit); existing CR → ask to sign in or continue with prefill | [Intake channels](specs/intake-channels.md) §3.1–3.3 |
| Existing tenants (§7.1.2 a1, §7.1) | Sign in; Leasing Opportunities; prefilled details, documents and property; My inquiries; public-page sign-in path | Intake channels §3.4–3.6 |
| Routing, handoff, recovery | Intent routing; handoff to the call centre; fault handling; form mode when the model is down | L3 §3.5, §3.6, §3.14 |
| First-level review (§7.1.1 b) | Routing by product line and region; reviewer console with a grounded case brief; re-upload loop; reject with remarks; approve with Azure AD invitation (only if no account) and an automatic contacts request; "lead" | [L4](specs/l4-outcome-assistance.md) §3.1–3.6 |
| Second-level review (§7.1.1 c, §7.1.2 c) | Contacts (prefilled for existing tenants; reviewer can remove); estimated sales data; Yardi company and brand re-link; approve (invitations with roles, acceptance email, lead to Yardi) or reject | L4 §3.3–3.7; Intake channels §3.7 |
| Applicant case assistant and reviewer assistant | Explains status and requests, collects answers, never re-asks; reviewer assistant suggests and drafts but never decides | L4 §3.5–3.6 |
| Proactivity (L5) | Stalled-review and pending-action triggers on a simulated clock; reminders under a notification policy (tiers, quiet hours, throttles, opt-out); "Needs attention"; insights | [L5](specs/l5-governed-proactivity.md) |
| Simulated Cenomi | CR registry, email and SMS (dev inbox), Tenant Admin Platform (reviewer and call-centre consoles), Tenant Central sign-in, Azure AD, Yardi, master data with Arabic names; fault injection | L3 §3.1, §3.8; L4 §3.2; Intake channels §3.4 |
| Reliability and audit | Durable store, state machine, gateway, idempotent submit, redacted audit trail, supervisor and agent registry | M0 |

### 3.2 Out of scope

Real Cenomi systems (all simulated until access is granted); Super Admin user management and onboarding of existing tenants by invitation; profile completion after Azure AD sign-in; tenant–staff messaging; General Inquiries (routed away); the Proposal stage (§7.2) onward; reading document contents; a right-to-left Arabic UI (the agent replies in Arabic; see §10).

## 4. The process

The full lifecycle, with diagrams and stage-by-stage behaviour, is in [`docs/POC-LIFECYCLE.md`](POC-LIFECYCLE.md). Every statement of requirements §7.1, §7.1.1 and §7.1.2, plus the related roles and admin-platform sections (R1–R90), is traced in [`docs/specs/workflows-7-1.md`](specs/workflows-7-1.md).

## 5. Agentic requirements

| Level | Requirement | Spec |
| --- | --- | --- |
| L1–L2 | The inquiry can always be completed through cards and a form, including when the model is down; every form path works conversationally; clear handoff to a person | L3 §3.6, §3.14 |
| L3 | Intent routing; multi-field extraction with evidence; entity resolution; verified context reuse; adaptive slot filling; deterministic validation; durable drafts and resume; explicit consent; reliable, idempotent execution; audit and recovery | L3, M0 |
| L4 | Outcome framing; grounded case briefs; prefill from verified sources; minimal questions; bounded read tools; continuity across roles and sessions; reviewer assistance; targeted rework; reviewers keep every decision; outcome tracking | L4, Intake channels |
| L5 | Event awareness; next-best actions; prepared reminders; escalation; process insights; risk-tiered automation; attention management; measured value | L5 |

## 6. Rules that may not be broken

1. The model acts only through tools; it never writes state. Business rules live in code and the policy file, not the prompt.
2. Every field records its source (`user`, `derived`, `verified`, `default`, `staff`) and whether it's confirmed. Derived, verified and staff-entered values are confirmed by the applicant before submit.
3. Consent, OTP codes and link tokens never pass through the model. Submit is a deterministic UI action.
4. Documents are checked for presence, type and size only.
5. External systems sit behind service interfaces with mocks.
6. Reviewers make every decision. No agent or proactive path changes a case's status.
7. Contract changes update `docs/spec.md` in the same PR.

## 7. Non-functional requirements

| Area | Requirement | Spec |
| --- | --- | --- |
| Testing | Six layers — backend, frontend (incl. frontend-only Playwright), integration Playwright, deterministic agent, live agent evaluation, live end-to-end Playwright — with safety invariants as hard failures | [Testing strategy](specs/testing-strategy.md) |
| Privacy | Redacted audit trail; signed, scoped links; no data by reference alone; access per persona | M0 §8; L3 §3.2; L4 §3.9; Intake channels C6 |
| Languages | English and Arabic conversations, Arabic digits, Arabic mall names | L3 §3.10 |
| Accessibility | Keyboard use, contrast, touch targets; axe checks | Testing strategy §2.2 |
| Operability | One-command demo; persona landing page and reset; KPI reports | Delivery plan Day 5; L3 §6 |

## 8. Acceptance

The POC is accepted gate by gate. Each gate row names the test that proves it.

| Gate | Rows | Target |
| --- | --- | --- |
| Pre-baseline | P1–P5 | 27 Oct |
| M0 modular core | G1–G7 | 13 Nov |
| L3 reliable intake (incl. intake channels) | E1–E10 (C1–C4, C6) | 16 Nov |
| L4 outcome assistance | X1–X9, C5 | 30 Nov |
| L5 governed proactivity | Y1–Y6 | ~16 Dec |

A conversational demo alone never passes a gate.

## 9. Delivery

[`docs/DELIVERY-PLAN.md`](DELIVERY-PLAN.md), tracked in [`docs/STATUS.md`](STATUS.md).

| Phase | Dates | Outcome |
| --- | --- | --- |
| 5-day plan | 27 Oct – 2 Nov | Every §7.1 workflow demoable end to end (demo depth) |
| Sprint 1 | 3 – 16 Nov | M0 and L3 gates: the intake POC at gate quality |
| Sprint 2 | 17 – 30 Nov | L4 gate: the review lifecycle at gate quality |
| Closing | 1 – ~16 Dec | L5 gate; production readiness |

## 10. Assumptions and open questions

The POC builds on working assumptions, each implemented in the policy file or a mock so a different answer is a configuration change: POC assumptions 1–9 (`docs/assumptions.md`), L3 Q1–Q8, intake channels D1–D9, L4 A1–A10, L5 B1–B6 (all listed in `docs/STATUS.md` §5).

Questions for Cenomi ([POC lifecycle](POC-LIFECYCLE.md) §7): the flow diagrams as source files; the §7.15 notification document; the UX and UI designs; whether anyone besides RLM / RPLM verifies leads; whether the POC UI must be right-to-left Arabic; the existing-tenant policy on the public page.

## 11. Change control

From this version on:
- **Scope changes** (adding, removing or changing anything in §3, §5, §6 or §8) are proposed as a PR that edits this PRD and the affected spec together, adds a line to the change log below, and bumps the version (1.1, 1.2, …). The PR says what it costs in days and which phase absorbs it.
- **Clarifications** that don't change scope (wording, examples, test names) can be made in the specs without a version bump.
- **Cenomi answers** that confirm an assumption are recorded in `docs/assumptions.md`; answers that change one are a scope change.
- Implementation PRs build to the locked specs. If a step finds a spec is wrong, it stops and raises a change rather than building something different.

### Change log

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 26 Oct 2026 | Locked: PRs #14–#18 (lifecycle specs, testing strategy, delivery plan, §7.1 traceability, intake channels, lifecycle review) |
