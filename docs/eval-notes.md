# Live evaluation notes (`scripts/eval_live.py`)

Run manually when tuning the agent prompt (not CI):

```bash
cd backend && uv run python scripts/eval_live.py
```

Requires `OPENAI_API_KEY` and `OPENAI_MODEL`. Target: all scenarios but at most one passing on two consecutive runs. Scenario **C** measures condensation: brief, natural answers must fill the inquiry in ≤ 4 typed turns with at most two questions per reply.

## Template for failures

| Date | Scenario | Check failed | Transcript excerpt | Prompt / code change |
| --- | --- | --- | --- | --- |
| _example_ | 5 unit type | confirmed | user: "…" / bot: "…" | _e.g. clarify confirm_fields after correction_ |

## Runs

| Date | Result | Notes |
| --- | --- | --- |
| 2026-10-14 | **8/8** (multiple runs; one run 7/8) | Prompt “Tool use (critical)”; graph `invoke_tool_choice` forces `update_draft` / `skip_cr` / `verify_cr` when appropriate; eval auto-confirm only on user “yes/correct”. |
| _pending_ | _re-run after `fix/conversational-friendliness`_ | Forced tool choice removed (guard now retries a missed save instead); prompt rewritten around question bundles and confirm-by-summary; temperature 0.6. |
