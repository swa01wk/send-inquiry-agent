# Step 11 — Polish, accessibility and demo readiness

Read first: @docs/design-spec.md (sections 7, 8) @.cursor/rules/frontend.mdc @.cursor/rules/backend.mdc

## Goal
Make the POC demo-ready: accessible, responsive, resilient and documented.

## Build
1. Accessibility pass: keyboard-only walkthrough of the whole flow; focus moves to the newest card's first control when a card appears; labels on every input; `aria-live` announcements for new assistant messages; colour contrast check of every text/background pair in `tokens.css` (add a small test computing contrast ratios ≥ 4.5:1 for text tokens on their backgrounds).
2. Responsive pass at 390, 768, 1280 and 1440px: panels stack, chips wrap, mall grid stays 2 columns down to 360px, review rows wrap cleanly.
3. Resilience: SSE disconnect mid-turn → error bubble + Retry that resends the last request; backend restarted → "chat has expired" message + Start again; slow network → typing indicator stays until `done`.
4. Observability: structured JSON logs per request with `session_id`, `phase`, tool names called, latency and token counts (no PII, no OTP, no file names at INFO).
5. Demo aids: `make demo` starts both apps with `OTP_MOCK_CODE=1234`; a "Restart" button in the chat header (demo builds only, `VITE_DEMO=1`); `docs/demo-script.md` with the happy path and three "wow" moments (multi-field capture, Arabic name suggestion + confirm, the draft panel filling live).
6. `README.md` at the repo root: setup, env vars, commands, architecture diagram (Mermaid: frontend → FastAPI → LangGraph agent ↔ OpenAI; tools → mock services/data; guard → domain rules), how to swap mocks for real Cenomi APIs, known limitations.

## Acceptance criteria
- Lighthouse accessibility score ≥ 95 on the page.
- All tests green; `make lint` clean.
- A new developer can run the demo from the README in under 10 minutes.

## Verify
```
make lint && make test && make demo
```
