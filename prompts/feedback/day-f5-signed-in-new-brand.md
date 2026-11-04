# Feedback Day F5 (Thu 12 Nov): signed-in tenant, new brand; company and brand codes

Read first: @docs/specs/demo-feedback.md (§2 rows D13–D15, §3.8, §4) @docs/specs/intake-channels.md (§3.4, §3.5) @docs/assumptions.md (Signed-in tenants) @prompts/feedback/day-f4-type-or-upload.md

## Goal
A signed-in tenant raising an inquiry from Leasing Opportunities:
- gets the company details from Yardi by CR, and confirms them;
- gives the new brand by typing it or uploading the brand profile;
- always uploads both profiles, and the company profile is checked against the Yardi record.

After final approval, the company and brand codes show on the case, the status page and the case-status card.

## Backend PR (Claude): lands first; use it, don't rebuild it
- **Yardi lookup by CR.**
  - `YardiService.company_by_cr(cr_number) -> YardiCompany | None`.
  - Mock Yardi companies gain `cr_number`, `address`, `company_code` and brand codes, and are linked to `tenants.json` by CR.
- **Signed-in prefill.**
  - Company name and address are prefilled from Yardi as `verified`, unconfirmed, and shown on `basic_info_review`.
  - Brand fields from the tenant record are no longer prefilled, because this is a new brand. The tenant's existing brands are listed so the agent can check it isn't a repeat.
  - Documents on file aren't reused for the company and brand profiles, so both are required on this path. Other optional documents on file still are.
- **Checks.** The company profile is checked against the Yardi record, with the same `document_checks` and flags as F4.
- **Lead codes.**
  - `send_lead` returns `company_code` and `brand_code`, stored on `YardiLink`.
  - They're shown on the console case page, `InquiryStatusPage` and the `case_status` payload after `sent_to_yardi`.
- **Tests:**
  - `tests/agent/test_signed_in_new_brand.py`;
  - `tests/services/test_yardi.py` (new), covering `company_by_cr`;
  - Playwright `f6-signed-in-new-brand`;
  - `t1-lifecycle-to-yardi` extended to the codes.

## Your track (Cursor): agent and chat
1. **Existing-tenant prompt.**
   - Greet by name and say the company details came from their Cenomi record. Ask them to check the card.
   - Ask what the new brand is. Offer to fill it from the brand profile or have them type it, as in F4.
   - If the brand matches one they already have, ask once whether this inquiry is for that brand or a new one. Never refuse.
   - Explain in one line that both profiles are needed for a new brand.
2. **`case_status` card:** show the codes once they're there ("Company code …, brand code …"). The case agent mentions them only when asked or at the approval message.
3. **Scripted mode and goldens:** `f6-signed-in-new-brand`, with its golden and frontend fixture.
4. **Live eval:** extend the `channels` existing-tenant scenarios to the new-brand flow.

## Tests
- Vitest for the `case_status` codes; `make e2e-fe`.
- `make e2e-int`: `f6-signed-in-new-brand` and `t1-lifecycle-to-yardi` pass; `a1-existing-tenant` passes, updated.
- AGENT-LIVE: `channels` (existing tenant) ×3 within tolerance, and `document_extract` still at 3/3.
- `make golden`: changed goldens are re-recorded with the reason (D15).

## End-of-day check
- [ ] `/tenant` → Leasing Opportunities → Raise inquiry → company from Yardi on the review card → confirm → brand by brand profile → both profiles → submit.
- [ ] Upload a company profile that doesn't match Yardi → warning → submit works → the Lease Admin sees the flag.
- [ ] After the RLM approves: codes on the case page, status page and `case_status` card.
- [ ] `docs/STATUS.md` Feedback F5 ✅ and the slice B gate rows D11–D15 marked; tracker I9, I14 set to Done.
