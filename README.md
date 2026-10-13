# Send Inquiry Agent — Cursor build kit

A chat-driven replacement for the Cenomi Tenant Central "Send Inquiry" form.
Stack: React (Vite, TypeScript) · FastAPI · LangGraph · OpenAI.

This kit gives Cursor everything it needs to build the POC step by step.

## What's inside

| Path | What it is |
| --- | --- |
| `.cursor/rules/*.mdc` | Project rules Cursor loads automatically (always-on context + per-folder rules) |
| `docs/spec.md` | **Source of truth**: data model, validation, tools, API, SSE events, card payloads |
| `docs/design-spec.md` | Visual design: tokens, layout, every component and its states, key copy |
| `docs/agent-system-prompt.md` | The agent's persona and rules (goes into the backend as-is) |
| `docs/assumptions.md` | POC assumptions (mocks, OTP code, reference format, …) |
| `design/prototype.dc.html` | The clickable prototype's markup and copy — a visual reference, not runnable as-is |
| `prompts/00…11-*.md` | Composer prompts, one per build step, in order |

## How to use it

1. Clone this repo: `git clone git@github.com:swa01wk/send-inquiry-agent.git`.
2. Open the folder in Cursor. The rules in `.cursor/rules/` load on their own.
3. For each prompt file, in order:
   1. Open a **new** Agent chat and pick the Composer model.
   2. Paste the prompt file's content and send it. Prompts already `@`-reference the docs they need.
   3. Let it finish, then run the **Verify** steps at the bottom of the prompt.
   4. Commit (`git commit -m "step NN: …"`) before moving on.
4. For prompts **04** (agent) and **08** (cards), ask for a plan first and approve it before it writes code, since these are the biggest steps.

## Build order

| # | Prompt | Result |
| --- | --- | --- |
| 00 | Bootstrap | Monorepo, Docker Compose, tooling, env |
| 01 | Domain model | `InquiryDraft`, provenance, validation, `can_submit` + tests |
| 02 | Data and mocks | Master data, FAQ, mock CR / OTP / storage / submit adapters |
| 03 | REST API | Sessions, uploads, master data, draft, status endpoints + tests |
| 04 | Agent | LangGraph state, tools, guard node, graph, system prompt |
| 05 | Chat streaming | `/chat` SSE endpoint, UI actions, event stream + tests |
| 06 | Frontend shell | Vite app, design tokens, page layout |
| 07 | Chat UI | Messages, typing, chips, composer, SSE hook |
| 08 | Rich cards | Confirm, malls, OTP, documents, review, success |
| 09 | Draft panel | Live draft with source badges, auto-scroll, checks |
| 10 | Integration | End-to-end flow + the 15 test scenarios |
| 11 | Polish | Accessibility, responsive, errors, README, demo script |

## Tips for working with Composer

- One prompt per chat keeps context clean. If a chat drifts, start a new one and say "continue step NN".
- When it guesses at a contract, point it back to `@docs/spec.md`; that file wins every disagreement.
- Ask it to run the tests it wrote. Every prompt ends with commands to check.
- Keep the mock services; swapping in real Cenomi APIs later only touches `backend/app/services/`.
