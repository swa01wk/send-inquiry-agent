# Breadth Day 5 (Mon 2 Nov) — Yardi handover, reviewer assistant, intake channels, demo

Read first: @docs/DELIVERY-PLAN.md (§A2, §A3, §A5) @docs/specs/intake-channels.md @docs/specs/workflows-7-1.md @docs/specs/l4-outcome-assistance.md (sections 3.6, 3.7, 3.8, 3.10) @prompts/21c-intake-channels.md @prompts/27-reviewer-assistant.md @prompts/28-yardi-handover-l4-gate.md

## Goal
Every workflow in requirements §7.1 runs end to end: the lifecycle reaches Yardi, reviewers get an assistant, a call-centre executive can raise an inquiry for a caller, and an existing tenant can raise one from Leasing Opportunities. The whole thing is rehearsed as one demo.

## Backend track (Claude's PR — don't build these)
**Lifecycle**
- `waiting_on_you` in `GET /api/inquiries/{reference}?t=` filled from the case's open requests, each with its case link; second review labelled "Lead — second review".
- Re-link actions in the review API (`company_relinked`, `brand_relinked`) checked against the Yardi mock; the brief shows the linked ids.
- On `approved`: invitations for additional contacts who have no account (`has_account`), `inquiry_accepted`, `YardiService.send_lead(LeadPayload, idempotency_key=f"lead:{inquiry_id}")` → `sent_to_yardi`, or `yardi_failed` with a retry.

**Intake channels** (`docs/specs/intake-channels.md` §3)
- `Source.staff` (unconfirmed until the applicant confirms); `Inquiry.channel`, `created_by`, `tenant_id`.
- `TenantDirectory` and `OpportunityCatalogue` mocks (`data/mock_world/tenants.json`, `opportunities.json`); `prefill_from_tenant()`.
- Assisted mode: tool allowlist (no verification, documents or review tools; plus `send_application_link`), `staff` writes, `existing_cr_choice` card and action, `send_application_link` action, `complete` token, `complete_application` template, handoff cases listed.
- Completing from the link: purpose `complete` verifies the email and resumes; `basic_info_review` card; `proceed_basic_info`.
- Existing-tenant mode: `/api/tenant/me`, `opportunities`, `inquiries` (list and create from an opportunity); prefill and preselected property; `signed_in_skips_verification`.
- Public page: `sign_in_prompt` card for `existing_tenant_policy: sign_in`; prefill and `basic_info_review` for `allow_inquiry`.
- Lifecycle for existing tenants: contacts prefilled at second review; `remove_contact` console action.
- `/api/callcentre/*` and `/api/tenant/*` behind `CALLCENTRE_CONSOLE` and `TENANT_PORTAL` (mock only).
- Unit tests for the `staff` rule, Proceed, prefill, `has_account` and access.

## Your track (Cursor)
1. **Reviewer assistant** in the console's case page:
   - agent with tools `get_case_brief`, `search_yardi_companies`, `list_company_brands`, `draft_reviewer_note`;
   - `POST /api/review/cases/{id}/assistant` (SSE);
   - `reviewer_suggestion` cards whose **Use** fills the action form (never submits);
   - asked to approve or reject, it says the decision is the reviewer's.
2. **Re-link in the console** (§7.1.1 c): in second review, a company picker (Yardi search by the first word of the company name, active companies only) and a brand picker (that company's brands); the assistant's suggestion **Use** fills these pickers. Also: the channel label on cases, and **Remove** on prefilled contacts.
3. **"Waiting for you"** on `/inquiry/status/:reference`: each open request with a button to its case link.
4. **Call-centre console** `/callcentre` (`VITE_CALLCENTRE_CONSOLE=1`): mock executive sign-in; **New inquiry** opens the chat in assisted mode; the `existing_cr_choice` and `send_link` cards; a list of handoff cases that opens the same inquiry.
5. **Assisted-mode prompt** for the intake agent: talks to the executive about "the caller", same bundles, short replies; never asks for verification, documents or consent; offers **Send application link** once the basic info is complete.
6. **Tenant portal** `/tenant` (`VITE_TENANT_PORTAL=1`): mock tenant sign-in; `/tenant/opportunities` (filter by city and product line; **Raise inquiry** opens the chat in existing-tenant mode); `/tenant/inquiries` (My inquiries).
7. **Existing-tenant prompt**: greet by name; one confirm card for the prefilled details; ask only which brand (if several) and optional space; offer the documents on file.
8. **Cards**: `basic_info_review` (Edit per field, **Proceed**), `sign_in_prompt`; the "From the call centre" source badge.
9. Status page and case agent: "Approved — your details are with the leasing team for a proposal" only after `sent_to_yardi`.
10. Playwright `@scripted` story **T1** (the full lifecycle to Yardi). Stories S9–S12 come in Sprint 1.
11. **Demo script:** extend `docs/demo-script.md` with the walkthrough in §A3 of the delivery plan (all five intake paths and both review levels).
12. Live: `scripts/eval_live.py` once; one `@live` run; try assisted mode with a dictated caller by hand.

## End-of-day demo check (5 days done)
- [ ] **§7.1.1 a1:** the self-service walkthrough runs without a restart.
- [ ] **§7.1.1 a2:** an executive raises an inquiry in `/callcentre` → the applicant opens the link from the dev inbox → email verified → reviews the basic info (with "From the call centre" badges) → **Proceed** → OTP → documents → submit.
- [ ] **§7.1.2 a2:** with CR `1010000000`, the executive gets both choices; **Continue for them** prefills the tenant record.
- [ ] **§7.1.2 a1:** a signed-in tenant raises an inquiry from Leasing Opportunities with everything prefilled, no email link or OTP, and sees it in My inquiries.
- [ ] **§7.1:** on the public chat, CR `1010000000` shows a Sign in button that lands on Leasing Opportunities.
- [ ] **Review:** first-level approval opens a contacts request automatically; an existing tenant's contacts are prefilled and a reviewer can remove one; final approval invites only people without an account; the lead reaches Yardi; the status page shows "Lead — second review" and "Waiting for you".
- [ ] The reviewer assistant suggests a Yardi match for Bean Street Trading Co.; **Use** fills the re-link pickers; it drafts re-upload remarks.
- [ ] `docs/STATUS.md` §0: 5-day plan ✅; rows 21c, 24–28 🟡. Write down what slipped, for Sprint 1 planning.
