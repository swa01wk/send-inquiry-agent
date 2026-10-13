# Step 04 — LangGraph agent

Read first: @docs/spec.md (sections 3, 4, 5) @docs/agent-system-prompt.md @.cursor/rules/agent.mdc @.cursor/rules/backend.mdc

**Start in plan mode:** propose the module layout, state schema, each tool's signature and the graph wiring, and wait for approval before writing code.

## Goal
Build the agent graph: state, tools, guard node, prompt assembly and a model factory that tests can replace with a scripted fake.

## Build (`app/agent/`)
1. `state.py`: `AgentState(TypedDict)` with `messages` (`add_messages`), `session_id`, `draft: InquiryDraft`, `phase`, `cards_shown: list[str]`, `guard_retries: int`.
2. `model.py`: `get_chat_model()` → `ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0.3, streaming=True)`. `ScriptedChatModel` for tests: given a list of steps (text and/or tool calls), returns them in order and supports `bind_tools`.
3. Copy the static prompt (the text between the first two `---` lines of `docs/agent-system-prompt.md`) into `app/agent/system_prompt.md`, so the backend doesn't depend on `docs/`. `prompts.py` loads it once at start-up and appends `prompt_summary(draft)` as the dynamic block each turn. Returns a `SystemMessage`.
4. `tools.py`: every tool in spec section 3 with exactly those names and arguments.
   - Use `InjectedState` and `InjectedToolCallId`; return `Command(update={"draft": …, "messages": [ToolMessage(...)]})`.
   - Reuse `domain/` for all validation and `api/cards.py` for card payloads.
   - Emit `draft` and `ui_card` events with `get_stream_writer()` (`{"type": "draft", "data": …}` / `{"type": "ui_card", "data": …}`); compute `changed_keys` from the keys the tool wrote.
   - `update_draft` rejects attempts to write protected keys or `verified`/`default` sources with a clear tool error.
5. `guard.py`: the deterministic guard in spec section 5 (phase, missing phase cards, false-submission check with at most one retry, existing-account check).
6. `graph.py`: the wiring in `.cursor/rules/agent.mdc`, compiled with `MemorySaver`; `build_graph(model_factory=get_chat_model)`.
7. `events.py`: `run_turn(graph, session, user_input: HumanMessage) -> AsyncIterator[SseEvent]`. Streams with `stream_mode=["messages", "custom"]`: assistant text → `token` (stable `message_id` per assistant message), custom → `ui_card`/`draft`, then `done {phase}`. Exceptions → `error`.

## Tests (`tests/agent/`) — all with `ScriptedChatModel`, no network
- Each tool: happy path and a precondition failure (e.g. `send_otp` without email, `show_review` with blockers, `confirm_fields` on an already-confirmed key, `update_draft` writing `terms_accepted`).
- `verify_cr` with the existing CR sets phase `existing_account`, and the guard keeps the reply pointing to Sign In.
- Guard: a scripted reply "Your inquiry has been submitted!" without a reference triggers exactly one retry.
- `run_turn` yields `token` events, then `ui_card`/`draft`, then `done`, in that order for a scripted tool-calling turn.

## Acceptance criteria
- No tool can set `terms_accepted`, `otp_verified`, `reference` or `confirmed=True` on a derived value through `update_draft`.
- `pytest tests/agent` is green without `OPENAI_API_KEY` set.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/agent -q
```
