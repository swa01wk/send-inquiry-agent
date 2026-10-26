# Improvement specs

These specs take the Send Inquiry agent from the v1 POC (solid L2, partial L3) through the whole inquiry process in requirements v2.1.7.1 §7.1 — from "Send us an inquiry" to a Yardi-ready lead — following the Agent Capability Maturity Framework (L1–L5).

`docs/spec.md` stays the source of truth for the contracts that exist **today**. Each spec here describes a change. When a step lands, fold its contract changes into `docs/spec.md` in the same PR, as `.cursor/rules/project.mdc` requires.

**Scope is locked in [`docs/PRD.md`](../PRD.md) (v1.0, tag `poc-prd-v1.0`).** Changes follow its change-control section.

**The whole lifecycle, with diagrams and its verification against the agent, L1–L5 and these specs, is in [`docs/POC-LIFECYCLE.md`](../POC-LIFECYCLE.md).**

**Progress is tracked in [`docs/STATUS.md`](../STATUS.md):** steps, gates, business-flow coverage, agentic-capability coverage and known issues.

**Delivery order is in [`docs/DELIVERY-PLAN.md`](../DELIVERY-PLAN.md):** Part A, the 5-day plan at demo depth (`prompts/breadth/`); Part B, the full implementation: Sprint 1 (M0 and L3 gates), Sprint 2 (L4 gate), then a closing phase (L5 gate). The step prompts stay the reference for what each piece must finally do; §B0 maps what the 5 days build against each one.

| Spec | Framework stage | Gate | Cursor steps |
| --- | --- | --- | --- |
| [pre-baseline-fixes.md](pre-baseline-fixes.md) | Before B0 | Confirm only what was shown; a turn when documents are complete; no Office product line | `prompts/11c` |
| [testing-strategy.md](testing-strategy.md) | All stages | Six test layers (BE, FE, INT, AGENT-DET, AGENT-LIVE, E2E-LIVE) with one command each, CI, live pass rules and safety invariants | `prompts/11d` |
| [workflows-7-1.md](workflows-7-1.md) | All stages | Traceability: every statement in requirements §7.1, §7.1.1 and §7.1.2 mapped to POC behaviour, spec section and delivery day | — |
| [m0-modular-core.md](m0-modular-core.md) | B0 + M0 | No data lost on restart; a repeat submit returns the same reference; every case has an audit trail; parity suite green | `prompts/12`–`16` |
| [l3-reliable-intake.md](l3-reliable-intake.md) | L3 | Correct routing, validated inputs, resume after interruption, one unambiguous submission, full audit, Arabic parity, acceptance stories, measured KPIs — all against a simulated Cenomi | `prompts/17`–`22` (with `21b`, `21c`) |
| [intake-channels.md](intake-channels.md) | L3 + L4 | Call-centre assisted intake (§7.1.1 a2, §7.1.2 a2) and existing tenants via Leasing Opportunities (§7.1.2 a1); C1–C6 | `prompts/21c` |
| [l4-outcome-assistance.md](l4-outcome-assistance.md) | L4 | The whole §7.1.1 b–c lifecycle runs end to end; reviewers keep every decision; no re-asking; grounded case briefs | `prompts/23`–`28` |
| [l5-governed-proactivity.md](l5-governed-proactivity.md) | L5 | Triggers fire on time and once; every message passes the notification policy; no proactive status change; value measured | `prompts/29`–`31` |

Done before M0 (kept for reference): [ui-bugs.md](ui-bugs.md) (demo-run fixes) and [e2e-playwright.md](e2e-playwright.md) (Playwright `@scripted` and `@live` suites, `make e2e` / `make e2e-live`), from `prompts/11b-ui-bugs-and-e2e.md`.

## Mock-first

Every external Cenomi system — CR registry, email, SMS, the Tenant Admin Platform, Azure AD, Yardi, master data — is simulated behind the same interface its real adapter will implement (L3 §3.1, L4 §3.2). Mocks keep state, return realistic outcomes and fail on demand (`MOCK_FAULTS`). A dev inbox shows every email and SMS, and a reviewer console stands in for the Tenant Admin Platform. A real adapter replaces its mock by configuration once it passes the same contract tests.

## Assumptions these specs build on

The POC assumptions agreed on 25 Oct 2026 (implemented in PR #1):
- Email is verified by link and the mobile by OTP.
- One mall per inquiry.
- International numbers are accepted, with OTP to mobile only.
- An existing CR is pointed to Sign In.
- Optional space fields and the terms checkbox stay.
- No document-content checks.
- External systems sit behind mock adapters until Cenomi provides access.

Each spec ends with the assumptions it adds; `docs/STATUS.md` §5 lists them all.

## Conventions
- **Priorities.** **Must** blocks the gate; **Should** is expected for the gate but can slip with a stated reason; **Could** is optional.
- **Decisions.** Every new dependency, table or endpoint states why it exists.
- **Testability.** Every acceptance criterion names the test that proves it. "Demo works" is never an acceptance criterion.
- **Testing.** Every step follows [testing-strategy.md](testing-strategy.md): `make ci` green, plus the live layers its §4 requires for the change. Each prompt's **Tests** section names its layers.
- **Stories.** Each level ends with acceptance stories run as Playwright `@scripted` tests (L3 §3.13, L4 §3.10, L5 §3.6), so "agentic" is checked by behaviour, not by impression.
- **Tracking.** Every implementation PR updates its row in `docs/STATUS.md`.
