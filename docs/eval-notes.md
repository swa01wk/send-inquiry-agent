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
| 2026-10-14 | **10/12** (live eval run 1) | Card attach/orphan fix, OTP hint, confirm_card scoping, Review selects, retraction logging, +3 eval scenarios. Failures: **4 many fields** (re-ask brand), **Hesitation** (model called `confirm_fields` on hesitation). |
| 2026-10-14 | **10/12** (live eval run 2) | Same commit; failures: **4 many fields** (bulk capture), **Hesitation** (sales_category confirmed despite doubt). New scenarios **Unknown mall** and **Chat during OTP** passed both runs. |
| 2026-10-14 | **12/12** then **11/12** | Doubt policy + guard bulk capture + brand re-ask. Fixed **4 many fields** and **Hesitation** both runs; one **Unknown mall** flake (model saved a mall id without picker). |
| 2026-10-14 | **12/12** + **11/12** | `mall_match` + guard strip / `update_draft` reject on unknown mall names. **Unknown mall** passes both runs; run 2 missed **C** malls once (unrelated LLM flake). |
| 2026-10-14 | **14/14** (retractions: **2**) | Guard heuristics: no Arabic bulk-data hint; generic “the mall” ignored; brand re-ask only on explicit ask; user/picker malls not cleared. New eval: **Arabic user**, **Generic mall phrase after picking**. |
| 2026-10-14 | **13/14** (retractions: **3**) | Same commit; **Arabic user** missed `brand_name_en` once (model kept Arabic-only brand). **Generic mall phrase after picking** passed both runs. |

## Prompt changes (2026-10-14, fix/conversational-friendliness)

| Change | Reason |
| --- | --- |
| Infer unit_type + sales_category together; map malls by seed id | Scenario C missing `sales_category` / `malls` when model called `get_master_data` alongside `update_draft` |
| confirm_fields on “yes / that’s correct” first in turn | Happy-path company confirmation |
| Extra condensation example (Bean Street @ Riyadh Mall A) | Reinforce save-all-fields on brand/space turn |
| Language line under “How you sound” | Arabic/English mirroring |
| OTP already-sent hint via `cards_shown` | Stop duplicate `send_otp` during OTP wait |
| `confirm_policy` + guard unconfirm on doubt | Hesitation keeps `sales_category` unconfirmed |
| Guard incomplete bulk capture + no “brand name” re-ask | Scenario 4 one-shot save |
| `mall_match` unknown-name guard + tool reject | No guessed mall id for “Red Sea Mall” |

## Failure excerpt (pre-fix run 1)

| Date | Scenario | Check failed | Transcript excerpt | Prompt / code change |
| --- | --- | --- | --- | --- |
| 2026-10-14 | C | all required fields filled | user: kiosk at Riyadh Mall A / bot: “can’t pin that one down… pick it in the mall list” | Mall id + sequential tool node dict `messages` handling |
| 2026-10-14 | Hesitation | sales_category still unconfirmed | user: “Hmm, not sure about the category” / bot carries on without leaving category unconfirmed | Prompt: treat explicit doubt as non-acceptance; do not `confirm_fields` |
| 2026-10-14 | 4 many fields | bulk fields / re-ask brand | varies by run | Prompt + guard: one-shot bulk capture on skip-CR path |
