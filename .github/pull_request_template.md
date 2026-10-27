## Summary

<!-- What this PR does and why. Name the step or day (e.g. "Step 17", "Breadth Day 2, backend track") and link the spec section it builds. -->

## Scope check

- [ ] Builds to the locked specs (`docs/PRD.md` v1.0). If a spec turned out to be wrong, this PR raises a change instead of building something different (PRD §11).
- [ ] Contract changes (models, tools, actions, API, SSE events, cards, config, commands) are in `docs/spec.md` in this PR — or there are none.
- [ ] Golden rules hold: the model acts only through tools; sources and confirmation are recorded; no codes, tokens or consent through the model; documents checked for presence, type and size only; mocks behind interfaces; reviewers make every decision.

## Testing

Layers and when each must run: `docs/specs/testing-strategy.md` §2 and §4. CI runs BE and FE on every PR; run the Playwright layers locally (`make e2e-int`) and report them here.

| Layer | Command | Result | Notes (what ran, what didn't and why) |
| --- | --- | --- | --- |
| BE — backend checks and tests | `make check-be`, `make test-be` | ✅ / ❌ / not run | |
| FE — frontend checks and unit tests | `make check-fe`, `make test-fe` | ✅ / ❌ / not run | |
| INT — frontend + backend Playwright (scripted) | `make e2e-int` (local) | ✅ / ❌ / not run | Pass count per project, e.g. desktop 23/23, mobile 23/23 |
| AGENT-DET — agent, deterministic | `make test-agent` | ✅ / ❌ / not run | |
| AGENT-LIVE — live evaluation | `make eval-live` | ✅ / ❌ / not required | Required when the prompt, tools, guard, router, notes or graph change (§4) |
| E2E-LIVE — Playwright with the real model | `make e2e-live` | ✅ / ❌ / not required | Smoke or full run as §4 requires |

<!-- When a live layer was required, paste the score vs baseline (AGENT-LIVE) or the pass count per project (E2E-LIVE), and confirm no safety invariant (I1–I7) failed. -->

## Tracking

- [ ] `docs/STATUS.md` updated (step row, §0 day tracker, gates, known issues, test layers as relevant)
