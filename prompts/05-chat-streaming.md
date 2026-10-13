# Step 05 — Chat endpoint, UI actions and streaming

Read first: @docs/spec.md (sections 4, 6, 7) @.cursor/rules/agent.mdc @.cursor/rules/backend.mdc

## Goal
`POST /api/sessions/{id}/chat` takes a message or a UI action, applies actions deterministically, runs one graph turn and streams SSE events.

## Build
1. `app/api/chat.py`:
   - Parse `ChatRequest` (discriminated union on `type`).
   - `message` → `HumanMessage(text)`.
   - `action` → handler in `app/agent/actions.py` per spec section 4 (`select_malls`, `submit_otp`, `resend_otp`, `edit_field`, `confirm_card`, `accept_and_submit`). Each handler validates, updates the draft through `domain/draft_ops`, collects any events it produces (e.g. updated `otp_input`, `review`, `success` cards and a `draft` event), and returns a `[ui_event] …` note as the `HumanMessage` for the graph turn.
   - `accept_and_submit`: set `terms_accepted`, run `can_submit`; when clear, call `SubmitService.submit`, set `reference`, emit the `success` card; otherwise emit the refreshed `review` card with `blockers`.
   - `submit_otp`: the code is checked by `OtpService` and never added to the message history or logs.
   - Hold the per-session lock for the whole turn; a second concurrent request gets 409 `turn_in_progress`.
   - Stream with `sse-starlette` `EventSourceResponse`: first the action's own events, then `run_turn`'s events. Each SSE message has `event: <type>` and `data: <json>`.
   - Per-session rate limit `RATE_LIMIT_SESSION`.
2. Persist the updated draft and `cards_shown` back to the session after the turn (the graph state is the source of truth; keep `SessionStore` in sync).
3. `scripts/chat_cli.py`: a tiny terminal client that creates a session and lets you chat against a running backend, printing events. Useful for prompt tuning.

## Tests (`tests/api/test_chat.py`), using `ScriptedChatModel` injected through the app factory
- A text message streams `token` … `done` with valid JSON in each event.
- `select_malls` writes malls as `user`/confirmed and emits `draft` with `changed_keys: ["malls"]` before the agent's tokens.
- `submit_otp` with a wrong code three times triggers a resend and resets attempts; the code string never appears in the stored message history.
- `accept_and_submit` with blockers returns a review card listing them; with a complete draft it returns a `success` card whose reference matches the pattern.
- A concurrent request returns 409.

## Verify
```
cd backend && uv run pytest -q
# With a real key in backend/.env:
make dev-backend
uv run python scripts/chat_cli.py
```
Try: "Hi, my CR is 1010123456", then answer naturally. Check the tone matches `docs/agent-system-prompt.md`.
