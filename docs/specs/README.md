# Improvement specs

These specs take the Send Inquiry agent from the v1 POC (solid L2, partial L3) to reliable L3 intake, following the Agent Capability Maturity Framework (L1–L5) and the Cenomi requirements document v2.1.7.1 (§7.1).

`docs/spec.md` stays the source of truth for the contracts that exist **today**. Each spec here describes a change. When a step lands, fold its contract changes into `docs/spec.md` in the same PR, as `.cursor/rules/project.mdc` requires.

| Spec | Framework stage | Gate | Cursor steps |
| --- | --- | --- | --- |
| [m0-modular-core.md](m0-modular-core.md) | B0 + M0 | No data lost on restart; a repeat submit returns the same reference; every case has an audit trail; parity suite green | `prompts/12`–`16` |
| [l3-reliable-intake.md](l3-reliable-intake.md) | L3 | Correct routing, validated inputs, resume after interruption, one unambiguous submission, full audit, measured KPIs | `prompts/17`–`22` |

Done before M0 (kept for reference): [ui-bugs.md](ui-bugs.md) (demo-run fixes) and [e2e-playwright.md](e2e-playwright.md) (Playwright `@scripted` and `@live` suites, `make e2e` / `make e2e-live`), from `prompts/11b-ui-bugs-and-e2e.md`.

Later specs, written once these land: L4 outcome assistance (case assistant, reviewer assistant) and L5 governed proactivity.

## Assumptions these specs build on

The POC assumptions agreed on 25 Oct 2026 (implemented in PR #1):
- Email is verified by link and the mobile by OTP.
- One mall per inquiry.
- International numbers are accepted, with OTP to mobile only.
- An existing CR is pointed to Sign In.
- Optional space fields and the terms checkbox stay.
- No document-content checks.
- External systems sit behind mock adapters until Cenomi provides access.

Each open question for Cenomi is listed at the end of the spec it affects.

## Conventions
- **Priorities.** **Must** blocks the gate; **Should** is expected for the gate but can slip with a stated reason; **Could** is optional.
- **Decisions.** Every new dependency, table or endpoint states why it exists.
- **Testability.** Every acceptance criterion names the test that proves it. "Demo works" is never an acceptance criterion.
