# L5 — Governed proactivity

**Status:** proposed · **Depends on:** [L4 outcome assistance](l4-outcome-assistance.md) · **Cursor steps:** `prompts/29`–`31`

## 1. Why

The framework defines L5 as event-driven agents that notice when a case is stuck, prepare the useful next step, and route it to the right owner — under explicit policy, with low alert noise and measured value. Its advice is to start only once L4 runs on real case events and SLAs exist.

Requirements v2.1.7.1 lists SLA definitions under Phase 2, so there are no real review SLAs yet (POC assumption 6). This spec therefore uses **demo thresholds** in the policy file and a **simulated clock**, so the behaviour can be built, tested and shown now, and switched to Cenomi's SLAs by configuration later.

Three rules hold throughout:
- **The agent never decides.** No approval, rejection or request is made proactively.
- **Every outbound message passes the notification policy** (§3.3). Anything beyond pre-approved transactional templates needs a person's approval.
- **Value is measured.** Each proactive action records whether it was accepted, dismissed or ignored, and what happened next.

## 2. Exit gate

All rows are Must.

| # | Criterion | Proved by |
| --- | --- | --- |
| Y1 | Each trigger in §3.2 fires exactly when its condition holds on the simulated clock, once per case per period | `tests/proactive/test_triggers.py` |
| Y2 | No message leaves without passing the notification policy; tier-2 messages wait for approval; quiet hours, throttles and opt-outs are honoured | `tests/proactive/test_policy.py` |
| Y3 | No proactive path can change a case's status | `tests/proactive/test_authority.py` |
| Y4 | Drafted reminders name exactly what's missing, make no promises and contain no data the template doesn't allow | `tests/proactive/test_drafts.py`, live eval "Proactive" scenario |
| Y5 | Effectiveness is reported: actions created, accepted, dismissed and sent; time from reminder to applicant action; stage ages and SLA-threshold breaches | `scripts/kpi_report.py` |
| Y6 | The stories in §3.6 pass as Playwright `@scripted` tests | `make e2e` |

## 3. Work items

### 3.1 Event engine and simulated clock (Must)

- **Events.** The engine reads the audit trail and workflow transitions (`inquiry_events`, M0 §8) in order, plus a periodic tick.
- **Clock.** A `Clock` interface with `SystemClock` and `SimulatedClock`. With `DEV_TOOLS=true`, `POST /api/dev/clock/advance {hours}` moves simulated time forward and runs a tick, so a "three days later" demo takes a click.
- **Triggers as configuration.** `policy.yaml` gains a `proactive:` section: each trigger's condition parameters, thresholds, action, tier and throttle. Nothing is hard-coded.
- **Idempotence.** Each trigger firing is keyed by `(inquiry_id, trigger, period)`, so a restart or a repeated tick doesn't fire twice.

### 3.2 Triggers (Must unless marked)

| Trigger | Condition (defaults are demo values) | Proactive action | Tier |
| --- | --- | --- | --- |
| Stalled review | Case in `first_review` or `second_review` longer than `review_stall_hours` (48) | Flag the case in the owning queue's "Needs attention" view with the case brief; `review_stalled` email to the queue reviewers | 0 (internal) |
| Escalation | Still stalled after `review_escalate_hours` (96) | Flag to the region manager for that role (reviewer directory) | 0 (internal) |
| Pending applicant action | An open request (re-upload, contacts, sales data) unanswered for `tenant_reminder_hours` (72) | The `proactive` agent drafts a reminder naming exactly what's missing; the reviewer approves, edits or dismisses it in the console. The queue sees "Waiting on applicant" | 2 (needs approval), or 1 if the policy marks the reminder template pre-approved |
| Abandoned draft | A draft with the email verified and no activity for `draft_resume_hours` (24), before submit | One resume link to the verified email | 1 (pre-approved, once per draft) |
| Late duplicate (Should) | Two open cases match on mall and CR, or on company and brand, after both were submitted | Flag both to the queue as possible duplicates | 0 |
| Process insight (Should) | Monthly, or on demand in the console | Report: most-requested re-upload documents, rejection reason categories, average time in each stage, reminder effectiveness | 0 (report only) |

### 3.3 Notification policy (Must)

Every proactive message goes through one `NotificationPolicy.check(message, case, now)` before `NotificationService.send`.

| Tier | What | Rule |
| --- | --- | --- |
| 0 | Internal flags and reports to Cenomi staff | Sent automatically; deduplicated per case per period |
| 1 | Transactional messages to the applicant on pre-approved templates (resume link, and reminders only if the policy says so) | Sent automatically within throttles |
| 2 | Any other message to the applicant | Needs a reviewer's approval in the console |

**Throttles and controls:**
- at most one proactive message to an applicant per case per `tenant_proactive_min_hours` (48);
- quiet hours `22:00–08:00` in `Asia/Riyadh` (configurable); messages wait until the window opens;
- every proactive applicant message carries an opt-out link; an opt-out stops proactive messages for that case (transactional messages they trigger themselves still go);
- every decision (sent, held for quiet hours, throttled, awaiting approval, dismissed) is audited.

### 3.4 Console: "Needs attention" (Must)

- A view per reviewer listing proactive items for their queues: what triggered it, the case brief link, the age, and the recommended action.
- Items are ranked by stage age against the threshold, then by kind (escalations first).
- **Approve and send**, **Edit**, or **Dismiss** (with a reason) for drafted reminders; **Open case** and **Dismiss** for flags.
- Dismissing records the reason; a dismissed item doesn't fire again in the same period.

### 3.5 Proactive drafting agent (Must)

- A `proactive` agent in the registry with one job: draft the reminder text from the case brief and the open request, inside a template frame (greeting, what's needed, why in the reviewer's words, the case link, sign-off).
- Deterministic checks on every draft before it reaches the console: it names each open request, contains no promise or timeline, no reviewer name, and only the fields the template allows. A failed check falls back to the plain template text.
- It has no tools that write; its output is a draft.

### 3.6 Acceptance stories (Must; gate Y6)

| # | Story | Proves |
| --- | --- | --- |
| P1 | Advance the clock 49 hours with a case in first review → it appears in "Needs attention" and the queue gets one `review_stalled` email; advancing again in the same period sends nothing new | Stalled review, dedupe (Y1) |
| P2 | A contacts request goes unanswered for 73 hours → a drafted reminder waits in the console → the reviewer edits and sends it → it's in the applicant's dev inbox with the case link → the applicant answers → the KPI records the response time | Pending applicant action, tier 2 (Y2, Y4, Y5) |
| P3 | The reminder would fall at 23:00 Riyadh time → it's held and sent at 08:00 | Quiet hours (Y2) |
| P4 | An applicant verifies their email and leaves → 24 hours later one resume link arrives; nothing more after that | Abandoned draft, once per draft |
| P5 | The applicant opts out from a reminder link → no further proactive messages for that case; their own actions still get transactional messages | Opt-out (Y2) |
| P6 | Any proactive path tries a status change (forced in a test) → rejected and audited | Authority (Y3) |

## 4. Contract changes to fold into `docs/spec.md`

| Area | Change |
| --- | --- |
| Data | `proactive_items` table: `{id, inquiry_id, trigger, period_key, tier, status: open\|sent\|held\|awaiting_approval\|dismissed, draft, reason, created_at, decided_by}`; `Inquiry.proactive_opt_out` |
| Services | `Clock`, `NotificationPolicy`, the event engine |
| REST | `GET /api/review/attention`, `POST /api/review/attention/{id}/{approve\|dismiss}`; dev only: `POST /api/dev/clock/advance`; public `GET /api/optout?t=` (token purpose `optout`) |
| Templates | `review_stalled`, `review_escalated`, `tenant_reminder`, `draft_resume`, `insight_report` |
| Config | policy `proactive:` section; `PROACTIVE_ENABLED`, `QUIET_HOURS`, `PROACTIVE_TZ` |

## 5. Sequencing

1. **Event engine, simulated clock, policy section, notification policy** — step 29.
2. **Triggers, "Needs attention" view and the drafting agent** — step 30.
3. **Insight report, L5 KPIs and the gate** — step 31.

## 6. Assumptions

| # | Assumption |
| --- | --- |
| B1 | Thresholds are demo values in the policy until Cenomi defines SLAs (Phase 2) |
| B2 | Quiet hours follow `Asia/Riyadh` |
| B3 | Proactive messages go by email only; no proactive SMS |
| B4 | Reminders to applicants need a reviewer's approval unless the policy marks the template pre-approved (POC assumption 9) |
| B5 | Region managers in the reviewer directory are the escalation owners |
| B6 | The one resume link for an abandoned draft is treated as pre-approved. This **extends** POC assumption 9, which lists only the OTP, the email link and the submission reference as sent without approval. It needs Cenomi's confirmation; until then the policy can set `draft_resume.tier: 2`, and the item then waits in an operations view instead of sending |
