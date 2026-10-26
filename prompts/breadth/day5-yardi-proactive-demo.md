# Breadth Day 5 (Mon 2 Nov) — Yardi handover, reviewer assistant, thin L5, demo

Read first: @docs/DELIVERY-PLAN.md (section 2) @docs/specs/l4-outcome-assistance.md (sections 3.6, 3.7, 3.10) @docs/specs/l5-governed-proactivity.md (sections 3.1–3.4) @prompts/27-reviewer-assistant.md @prompts/28-yardi-handover-l4-gate.md @prompts/30-triggers-attention.md

## Goal
The lifecycle reaches Yardi, reviewers get an assistant, stuck cases surface on their own, and the whole thing is rehearsed as one demo.

## Backend track (Claude's PR — don't build these)
- On `approved`: invitations for additional contacts, `inquiry_accepted`, `YardiService.send_lead(LeadPayload, idempotency_key=f"lead:{inquiry_id}")` → `sent_to_yardi`, or `yardi_failed` with a retry.
- `Clock` with `SimulatedClock`; `POST /api/dev/clock/advance {hours}` (dev tools).
- Triggers (in memory): stalled review past `review_stall_hours`; pending applicant action past `tenant_reminder_hours`. Each creates a proactive item once per case per period.
- `NotificationPolicy.check`: tiers 0–2 and quiet hours (L5 §3.3). Reminders to applicants are tier 2 (need approval) and use the `tenant_reminder` template text.
- `GET /api/review/attention`, `POST /api/review/attention/{id}/approve|dismiss`.
- Tests for the triggers, policy tiers and quiet hours, and that no proactive path calls `transition()`.

## Your track (Cursor)
1. **Reviewer assistant** in the console's case page:
   - agent with tools `get_case_brief`, `search_yardi_companies`, `list_company_brands`, `draft_reviewer_note`;
   - `POST /api/review/cases/{id}/assistant` (SSE);
   - `reviewer_suggestion` cards whose **Use** fills the action form (never submits);
   - asked to approve or reject, it says the decision is the reviewer's.
2. **"Needs attention"** view in the console: items with trigger, age and the drafted reminder; **Approve and send**, **Edit**, **Dismiss** (reason).
3. Status page and case agent: "Approved — your details are with the leasing team for a proposal" only after `sent_to_yardi`.
4. Playwright `@scripted` story **T1** (the full lifecycle to Yardi).
5. **Demo script:** extend `docs/demo-script.md` with the full walkthrough (intake → dev inbox → status page → reviewer console → re-upload → contacts → approval → Yardi → advance the clock → stalled-case alert → approved reminder).
6. Live: `scripts/eval_live.py` once; one `@live` run.

## End-of-day demo check (breadth done)
- [ ] The full walkthrough in `docs/demo-script.md` runs without a restart.
- [ ] Advancing the clock 49 hours shows the stalled case in "Needs attention"; 73 hours after a contacts request, a reminder waits for approval and lands in the inbox once approved.
- [ ] The reviewer assistant suggests a Yardi match for Bean Street Trading Co. and drafts re-upload remarks.
- [ ] `docs/STATUS.md` §0: Breadth ✅; rows 27–30 🟡. Write down what slipped, for Sprint 1 planning.
