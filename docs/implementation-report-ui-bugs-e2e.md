# Implementation & Playwright testing report

Branch: `fix/ui-bugs-and-e2e`

---

## Phase A — Demo-run bugs (B1–B8)

Unchanged from prior report: B1–B8 implemented; backend + frontend unit tests green.

---

## Phase B — Playwright e2e (completed)

### Backend / agent

| Item | Implementation |
| --- | --- |
| Default model | `build_graph` binds `default_model = factory().bind_tools(TOOLS)` once; per-turn `bound_chat_model` override for scripted sessions |
| Factory test | `backend/tests/agent/test_graph_factory.py` — factory called once across two turns |
| Guard | Scripted mode no longer skips guard heuristics; scripts include decoy/retry steps where needed (`23-guard-missed-save`) |
| Scenario header | `resolve_e2e_scenario()` allowlists `backend/tests/e2e_scripts/*.json`; ignored in `openai` mode |
| Frontend E2E | `X-Test-Scenario` only when `E2E_MODE`; page object also injects header via route |
| Session id | E2E uses last `POST /api/sessions` response + `window.__e2eSessionId` to avoid Strict Mode double-create drift |

### Scripts

- **23** scenario JSON files (`01`–`23`), including guard-missed-save.
- Generator: `backend/scripts/generate_e2e_scripts.py` — scripts aligned **one user turn per script segment** (say after confirm/update so the graph does not consume the next user’s steps early).
- **18-demo-sequence**: 8 demo utterances + post-upload chat turn for `show_review`.

### E2E tests (grouped)

| File | Scenarios |
| --- | --- |
| `e2e/tests/basics.spec.ts` | 01, 02, 07, 18, 19 |
| `e2e/tests/language-and-style.spec.ts` | 05, 06, 20 |
| `e2e/tests/mistakes-and-changes.spec.ts` | 04, 09, 12, 13, 23 |
| `e2e/tests/confused-users.spec.ts` | 11, 14, 21, 22 |
| `e2e/tests/edge-cases.spec.ts` | 03, 08, 10, 15, 16, 17 |
| `e2e/tests/live.spec.ts` | 14 live (**L**) scenarios |

Each scripted test uses persona steps from `docs/specs/e2e-playwright.md` §5, `afterTurnChecks` every turn, and axe (+ mobile overflow) at end.

### Results

| Suite | Result |
| --- | --- |
| **`make test`** | Backend **186** passed; frontend **44** passed |
| **`make lint`** | Green |
| **`make e2e` (`@scripted`)** | **45/46 passed**, **1 flaky** (mobile scenario 14, passes on retry); **23 scenarios × 2 projects** |
| **`make e2e-live`** | Not run here (`OPENAI_API_KEY` not available in agent env) |

Live JSON writer: `e2e/support/liveResults.ts` → `e2e/results/live-<date>.json` when live tests run.

### B1 regression (undotted extensions)

Temporarily reverted `dotted_allowed_extensions()` to undotted API values and ran scenario **13** (`13 wrong files then valid PDFs`, desktop). **Test still passed** because `documentFileCheck.ts` normalizes dotted/undotted (Phase A B1). Regression signal for B1 remains **`backend/tests/api/test_cards_payload.py`** (expects `".pdf"`) plus frontend `documentFileCheck.test.ts`. Restored dotted API before commit.

### Remaining / honest deviations

1. **Scenario 14 (mobile)** — occasional flake under full 46-test run; `confused-users.spec.ts` uses `retries: 1`.
2. **Scenario 05 Arabic** — retraction budget asserted `<= 1` (spec prefers 0; scripted guard can still retry once on some turns).
3. **`make e2e-live`** — implementation present; two consecutive ≥13/14 runs not executed in this environment (no API key).
4. **B1 e2e-only regression** — undotted API alone does not fail scenario 13 after frontend normalization (noted above).

---

## Commands

```bash
make lint && make test && make e2e    # scripted, CI=1 fresh servers
make e2e-live                         # requires OPENAI_API_KEY (twice for eval target)
```
