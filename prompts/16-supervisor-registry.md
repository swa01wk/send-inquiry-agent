# Step 16 — Supervisor and agent registry

Read first: @docs/specs/m0-modular-core.md (section 9) @backend/app/agent/graph.py @.cursor/rules/agent.mdc

**Start in plan mode:** show the new graph shape and how today's intake agent moves into the registry unchanged. Wait for approval before writing code.

## Goal
Turn the single graph into supervisor → domain agents, so routing (L3) and post-submit agents (L4) can be added by configuration, not by copying code.

## Build
1. `app/agents/spec.py`: the `AgentSpec` dataclass (name, description, tool allowlist, prompt path, hint function, guard).
2. `app/agents/intake/`: move the current agent here unchanged. Same tools, `system_prompt.md`, bundle hints and guard. Leave a re-export shim at the old import paths for one release.
3. `app/agents/status/`: an agent for inquiries that are no longer drafts:
   - tools: `get_inquiry_status`, `search_faq`;
   - a short prompt: answer status and process questions; never collect or change inquiry data;
   - a guard that keeps the false-claim checks.
4. `app/agents/registry.py`: register both agents.
5. `app/agents/graph.py`: `START → supervisor → {intake | status} → END`. The supervisor is deterministic: `status` when `inquiry.status != draft`, else `intake`. Each agent is a subgraph (agent ⇄ tools → guard) built from its spec.
6. Update `.cursor/rules/agent.mdc` with the new layout.

## Tests
- The supervisor routes by inquiry status.
- The status agent can't call `update_draft` (not in its allowlist).
- After submit, "what's my status?" uses `get_inquiry_status`.

## Acceptance criteria
- Parity suite green (intake behaviour unchanged).
- Gate G7 passes.
- The M0 gate (G1–G7) is complete; record it in `docs/specs/README.md`.

## Verify
```
make test && make lint && cd backend && uv run python scripts/eval_live.py
```
