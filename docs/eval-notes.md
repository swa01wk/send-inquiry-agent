# Live evaluation notes (`scripts/eval_live.py`)

Run manually when tuning the agent prompt (not CI):

```bash
cd backend && uv run python scripts/eval_live.py
```

Requires `OPENAI_API_KEY` and `OPENAI_MODEL`. Target: **≥ 8/8** scenario checks passing on two consecutive runs.

## Template for failures

| Date | Scenario | Check failed | Transcript excerpt | Prompt / code change |
| --- | --- | --- | --- | --- |
| _example_ | 5 unit type | confirmed | user: "…" / bot: "…" | _e.g. clarify confirm_fields after correction_ |

## Runs

| Date | Result | Notes |
| --- | --- | --- |
| 2026-10-14 | **8/8** (multiple runs; one run 7/8) | Prompt “Tool use (critical)”; graph `invoke_tool_choice` forces `update_draft` / `skip_cr` / `verify_cr` when appropriate; eval auto-confirm only on user “yes/correct”. |
