# Breadth Day 5 (Mon 2 Nov) — Yardi handover, intake channels, reviewer assistant, thin L5, demo

Read first: @docs/DELIVERY-PLAN.md (§A2, §A3, §A4, §A5) @docs/specs/intake-channels.md @docs/specs/workflows-7-1.md @docs/specs/l4-outcome-assistance.md (sections 3.6, 3.7, 3.8, 3.10) @docs/specs/l5-governed-proactivity.md (sections 3.1–3.5) @prompts/21c-intake-channels.md @prompts/27-reviewer-assistant.md @prompts/28-yardi-handover-l4-gate.md @prompts/30-triggers-attention.md

## Goal
Every workflow in requirements §7.1 and the core of every maturity level runs end to end: the lifecycle reaches Yardi, a call-centre executive or the Guest Service desk can raise an inquiry, an existing tenant can raise one from Leasing Opportunities, reviewers get an assistant, and stuck cases surface on their own under a notification policy. The whole thing is rehearsed as one demo.

## Claude's PRs (backend + deterministic UI — don't build these)
**Lifecycle**
- `waiting_on_you` in `GET /api/inquiries/{reference}?t=` from the case's open requests, each with its case link; second review labelled "Lead — second review".
- Re-link actions (`company_relinked`, `brand_relinked`) checked against the Yardi mock; the brief shows the linked ids.
- On `approved`: invitations for additional contacts without an account (`has_account`), with their roles; `inquiry_accepted`; `YardiService.send_lead(LeadPayload, idempotency_key=f"lead:{inquiry_id}")` → `sent_to_yardi`, or `yardi_failed` with a retry.

**Intake channels** (`docs/specs/intake-channels.md` §3)
- `Source.staff`; `Inquiry.channel`, `created_by`, `tenant_id`; staff roles `customer_care` and `guest_service`.
- `TenantDirectory` and `OpportunityCatalogue` mocks; `prefill_from_tenant()`.
- Assisted mode backend: tool allowlist (no verification, documents or review tools; plus `send_application_link`), `staff` writes, `existing_cr_choice` card and action, `send_application_link`, `complete` token, `complete_application` template, handoff cases listed.
- Completing from the link: purpose `complete` verifies the email and resumes; `basic_info_review` card payload; `proceed_basic_info`.
- Existing-tenant mode: `/api/tenant/*`; prefill and preselected property; `signed_in_skips_verification`.
- Public page: `sign_in_prompt` card for `existing_tenant_policy: sign_in`; prefill and `basic_info_review` for `allow_inquiry`; "ask them to sign in" and the public path set `redirected`.
- Contacts prefilled at second review for existing tenants; `remove_contact` console action.

**L5 core** (`docs/specs/l5-governed-proactivity.md` §3.1–3.4, thin)
- `Clock` with `SimulatedClock`; `POST /api/dev/clock/advance {hours}`; a tick evaluates triggers over case states.
- Triggers: **stalled review** past `review_stall_hours` (48) → internal flag + `review_stalled` to the queue; **escalation** past `review_escalate_hours` (96) → flag to the region manager; **unanswered request** (re-upload, contacts or sales data) past `tenant_reminder_hours` (72) → a reminder item awaiting approval. Each fires once per case per period.
- `NotificationPolicy.check`: tier 0 (internal) sends; tier 2 (applicant reminders) needs approval; quiet hours `22:00–08:00 Asia/Riyadh` hold a send until morning. Every decision in the audit log.
- `GET /api/review/attention` (ranked by age against threshold, escalations first), `POST …/{id}/approve` (optional edited text) and `/dismiss` (reason); counts of raised, sent and dismissed (by reason).
- Tests: each trigger at its threshold and not before; once per period; tiers; quiet hours across midnight; no proactive path calls `transition()`.

**Demo operability**
- `POST /api/dev/reset` (sessions, cases, outbox, invitations, clock, snapshot) and reload of the mock world.
- `make demo` turns on `DEV_TOOLS`, `REVIEWER_CONSOLE`, `CALLCENTRE_CONSOLE`, `TENANT_PORTAL`, `PROACTIVE_ENABLED`.

**Deterministic UI**
- `/dev` landing: one link per persona — applicant chat, call centre, guest service, tenant portal (each mock tenant), reviewer console (each queue), dev inbox — plus **Reset demo** and **Advance clock** (+24 h, +48 h, to morning).
- Tenant portal: `/tenant` (mock sign-in), `/tenant/opportunities` (filters; **Raise inquiry** opens the chat in existing-tenant mode), `/tenant/inquiries` (My inquiries).
- Console: **re-link pickers** (company by first word, active only; brands of that company), channel labels, **Remove** on prefilled contacts, **"Needs attention"** view (trigger, age, the item; Approve and send / Edit / Dismiss with reason) with a badge count.
- Status page: **"Waiting for you"** with a button to each case link.
- Vitest and Playwright for each page.

## Your track (Cursor) — agent and chat
1. **Reviewer assistant** on the console's case page: agent with tools `get_case_brief`, `search_yardi_companies`, `list_company_brands`, `draft_reviewer_note`; `POST /api/review/cases/{id}/assistant` (SSE); `reviewer_suggestion` cards whose **Use** fills the action form or the re-link pickers (never submits); asked to approve or reject, it says the decision is the reviewer's.
2. **L5 proactive preparation:** for an "unanswered request" item, the reviewer assistant drafts the reminder (`draft_reviewer_note` with kind `tenant_reminder`): names exactly what's missing, the reviewer's reason, the case link; no promises, no reviewer names. The draft fills the item's text for the reviewer to approve, edit or dismiss.
3. **Assisted-mode prompt** and `/callcentre` chat (`VITE_CALLCENTRE_CONSOLE=1`): mock staff sign-in; New inquiry opens the chat in assisted mode; talks to the executive about "the caller", same bundles, short replies; never asks for verification, documents or consent; `existing_cr_choice` and `send_link` cards; handoff cases open the same inquiry.
4. **Existing-tenant prompt:** greet by name; one confirm card for the prefilled details; ask only which brand (if several) and optional space; offer the documents on file.
5. **Chat cards:** `basic_info_review` (Edit per field, **Proceed**), `sign_in_prompt`; the "From the call centre" source badge.
6. Status page and case agent: "Approved — your details are with the leasing team for a proposal" only after `sent_to_yardi`.
7. Playwright `@scripted` story **T1** (the full lifecycle to Yardi).
8. **Demo script:** extend `docs/demo-script.md` with the walkthrough in §A3 and the L3–L5 moments in §A4 (restart, form mode, audit timeline, clock advance, reminder).
9. Live: `scripts/eval_live.py` once; one `@live` run; try assisted mode with a dictated caller by hand.

## End-of-day demo check (5 days done)
**Workflows**
- [ ] §7.1.1 a1 self-service, §7.1.1 a2 call centre (and the Guest Service desk), §7.1.2 a1 existing tenant, §7.1.2 a2 with an existing CR, §7.1 public-page sign-in — each end to end.
- [ ] First approval opens a contacts request automatically; existing tenants' contacts are prefilled and a reviewer can remove one; final approval invites only people without an account; the lead reaches Yardi; the status page shows "Lead — second review" and "Waiting for you".

**Agentic core**
- [ ] L3: restart mid-inquiry and carry on; model down → finish in form mode; evidence on derived values; audit timeline complete.
- [ ] L4: no intake question after submit; the reviewer assistant suggests a Yardi match for Bean Street Trading Co. and **Use** fills the pickers; it never decides.
- [ ] L5: advance the clock 49 h → the stalled case is in "Needs attention" and the queue got one email; +48 h more → escalated to the region manager; a contacts request unanswered for 73 h → a drafted reminder waits for approval → approve → in the applicant's inbox once; a reminder due at 23:00 Riyadh time is held until 08:00.
- [ ] From `/dev`, every persona opens in one click; **Reset demo** starts clean.
- [ ] `docs/STATUS.md` §0: 5-day plan ✅; rows 21c, 24–30 🟡. Write down what slipped, for Sprint 1 planning.
