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
| 2026-10-14 | **9/9** | After `fix/conversational-friendliness` verify pass: prompt tuned for mall ids + paired unit/sales category; sequential tool node fix for `get_master_data` + `update_draft` parallel calls. |
| 2026-10-14 | **8/9** (13 off-topic: “offer to continue” check) | Same prompt; scenario 13 bot omitted “continue/inquiry” wording once — acceptable under target (≤1 fail). |

## Prompt changes (2026-10-14, fix/conversational-friendliness)

| Change | Reason |
| --- | --- |
| Infer unit_type + sales_category together; map malls by seed id | Scenario C missing `sales_category` / `malls` when model called `get_master_data` alongside `update_draft` |
| confirm_fields on “yes / that’s correct” first in turn | Happy-path company confirmation |
| Extra condensation example (Bean Street @ Riyadh Mall A) | Reinforce save-all-fields on brand/space turn |

## Failure excerpt (pre-fix run 1)

| Date | Scenario | Check failed | Transcript excerpt | Prompt / code change |
| --- | --- | --- | --- | --- |
| 2026-10-14 | C | all required fields filled | user: kiosk at Riyadh Mall A / bot: “can’t pin that one down… pick it in the mall list” | Mall id + sequential tool node dict `messages` handling |
