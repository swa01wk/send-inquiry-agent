# Step 07 — Chat UI, store and streaming hook

Read first: @docs/design-spec.md (section 4, 7) @docs/spec.md (sections 6, 7) @design/prototype.dc.html @.cursor/rules/frontend.mdc

## Goal
A working conversation: create a session, send messages, stream replies, show typing, chips and errors. Cards are rendered as placeholders in this step (step 08 builds them).

## Build
1. `state/chatStore.ts`: a reducer + context.
   - State: `sessionId`, `messages: {id, role, text, cardIds[]}[]`, `cards: Record<card_id, UiCard>`, `quickReplies`, `draft`, `phase`, `status: "idle" | "streaming" | "error"`, `error?`, `pendingRetry?`.
   - Actions for every SSE event type, plus `userMessage`, `turnStarted` (clears quick replies), `sessionCreated` and `reset`.
   - `ui_card`: if `card_id` exists, replace its payload in place; otherwise attach it to `message_id`'s message (or the latest assistant message). `quick_replies` cards go to `quickReplies`, not into a message.
2. `api/client.ts` (REST) and `api/stream.ts` (`fetchEventSource` POST to `/chat`, parse each event's JSON, abort on unmount, no automatic retry).
3. `hooks/useChatSession.ts`: creates the session on mount; exposes `sendMessage(text)`, `sendAction(action, payload)`, `uploadDocument(docType, file)`, `removeDocument(docType)`, `retry()`, `restart()`. In `VITE_MOCK=1`, uses `mocks/mockStream.ts`, which replays the prototype's scripted flow with ~700ms delays.
4. Components (`components/chat/`), exactly as design spec section 4:
   - `ChatPanel`, `ChatHeader`, `ProgressStages` (phase → stage mapping);
   - `MessageList` (avatar grouping, auto-scroll on new content, `aria-live`), `UserBubble`, `BotBubble`, `TypingIndicator`;
   - `SuggestionChips`, `Composer` (Enter to send, disabled while streaming);
   - an `ErrorBubble` with Retry; the rate-limit and expired-session messages from section 7.
   - `CardSlot` renders `card_type` as a labelled placeholder box for now.

## Tests (Vitest + RTL)
- Reducer: token accumulation per `message_id`; card insert vs replace by `card_id`; quick replies cleared at turn start; `done` resets status.
- `Composer`: Enter sends; disabled while streaming.
- `MessageList`: avatar shows only on the first bot message of a run.
- `ProgressStages`: correct done/current/upcoming styles per phase.

## Verify
```
cd frontend && npm run test
VITE_MOCK=1 npm run dev     # full scripted conversation without the backend
npm run dev                 # against the real backend (make dev-backend)
```
