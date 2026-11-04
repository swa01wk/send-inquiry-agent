# POC assumptions

Each open question has an assumption the POC builds on. Integrations sit behind interfaces, so replacing an assumption later is an adapter or config change.

| Area | Assumption |
| --- | --- |
| CR verify | Mocked. `1010123456` → new account with sample company details; `1010222222` → new account with **Fawaz Alhokair Trading Co.**; `1010000000` → existing account; other valid numbers → new, no details. CR format: 10 digits. |
| Existing account | The agent points the user to Sign In; no inquiry is created. |
| CR optional | Skipping is allowed, as today. The agent recommends providing it once. |
| Contact | One number. Saudi: `+9665…` is mobile, other Saudi numbers are landlines. Any other country is accepted with its country code (E.164) and treated as mobile unless the user says it's a landline. Either satisfies the requirement. |
| Verification | Two checks, as in requirements §7.1.1. Email by a one-time link (mocked; with `EMAIL_LINK_DEMO` the card shows an "Open verification link (demo)" button). Mobile by SMS code, mocked as `1234` (`OTP_MOCK_CODE`), 3 attempts then an automatic resend. A landline-only applicant is verified by email alone; a landline never gets an OTP. Changing the email or mobile clears that check. The chat replaces the external page; no cross-session resume. |
| Email | Format check only; no company-domain rule. |
| Arabic brand name | The agent proposes it; the user confirms or edits. |
| Unit type, sales category | Derived from the user's description, mapped to master ids, confirmed by the user. |
| Property fields | Exactly one mall per inquiry (requirements list one "Property/Mall" and route review by unit type and region); naming several makes the agent ask which to start with. Area, rent, rent period and lease optional. Area defaults to 10 – 25,000 sqm. |
| Rent period | Monthly, Yearly. |
| Lease period | 1, 2, 3, 5 years. |
| Consent | Only the review card's checkbox + Submit. Never inferred. |
| Documents | Company Profile and Brand Profile required; CR, VAT, National ID/Iqama, National Address, Article of Association optional. Presence, extension and size (≤ 5 MB) only — no content processing. |
| Storage | Local disk under `UPLOAD_DIR`. |
| Master data | Seeded JSON with sample malls (Riyadh/Jeddah/Dammam "Mall A…"). Replace with real data before any demo to Cenomi stakeholders. |
| Submit | Mocked with the same payload shape as the current form. Reference `GEO-{STR|MED|SPC}-{6 digits}`. |
| Status | Mocked: any submitted reference returns "Under review". |
| Email notifications | Not sent; logged only. |
| Language | English UI; the agent can greet in Arabic. Full Arabic is phase 2. |
| Persona | "Cenomi leasing assistant": warm, professional; small talk and FAQ allowed, always easing back to the inquiry. |
| FAQ | 8–10 placeholder answers, marked `[to be confirmed]` where facts are unknown. |
| Session | Unauthenticated, in memory, 2-hour idle expiry, no cross-session resume. Rate limited. |

## Demo feedback assumptions (agreed 4 Nov 2026)

These come from the 3–4 Nov client demos and our 4 Nov review ([`docs/specs/demo-feedback.md`](specs/demo-feedback.md)). Each row applies from the step named in **Lands in**. Until then, the rows above still describe `main`. When a row lands, its PR removes or rewords the older row it replaces. Questions still open with the client are marked *pending Cenomi*.

| Area | Assumption | Replaces | Lands in |
| --- | --- | --- | --- |
| CR on the public page | The agent asks "Do you have a CR?". **Yes** → Sign in. The public page never asks for, accepts or looks up a CR number. A CR number the applicant types anyway gets the sign-in reply and is never repeated back. **No** → the inquiry continues in chat. | CR verify, Existing account, CR optional | F1 |
| CR without a login | A company with a CR but no Tenant Central login is out of scope for now: Yes always leads to sign-in. *Pending Cenomi* (M2). | — | — |
| Reviewer roles | First-level review is done by the **Lease Admin**. Final review is done by **RLM** (Store) or **RPLM** (Media, Specialty) by product line. Lease Manager is a tenant contact role, not a reviewer. | — | F1 |
| Reviewer entry | Reviewers find new inquiries in the inbox and in their queue after sign-in. There's no notification-agent integration in the POC. | — | — |
| Document content | Content checks run in a separate document review service, behind an interface and mocked until Cenomi gives access. The Send Inquiry Agent never reads document content itself. The service returns structured fields only, never raw document text to the model. | Documents ("no content processing") | F1 (interface), F4 (fields) |
| Company and brand details, no CR | The applicant either types the company and brand details or uploads the company and brand profiles. On upload, the agent fills company name and address (company profile) and brand name and sales category (brand profile), and the applicant confirms each value. Typed values are checked against the profiles once they're uploaded. There's no external registry. | — | F4 |
| Signed-in tenants | Company details are fetched from Yardi by CR (mock) and confirmed by the tenant. Every inquiry is treated as a new brand under the same company, so both profiles are always uploaded. The company profile is checked against the Yardi record, and the brand profile against the brand details. | Existing tenants: documents on file | F5 |
| Document mismatch | A difference between a profile and the applicant's answers warns the applicant in chat and is flagged to the Lease Admin. It doesn't block submit. | — | F4 |
| Document expiry | The document review service extracts an expiry date from the company and brand profiles. The Lease Admin confirms it. **Expired:** the console marks the document and proposes Reject with a re-upload request, and the Lease Admin confirms. **Under 14 days from today:** "Expiring soon", and the Lease Admin decides. **14 days or more:** approvable. Thresholds live in `policy.yaml`. The 3–13 day gap is *pending Cenomi* (M9). | — | F2 |
| Document approval | The Lease Admin approves or rejects each uploaded document, with remarks. First-level approval waits until every required document is approved. A re-uploaded document needs approval again. | — | F2 |
| Contact approval | The Lease Admin approves or rejects each second-level contact the tenant enters. An applicant who answers "Yes, I'm the authorised signatory" needs no separate approval for now, because the email link and OTP already verify them (*pending Cenomi*, M8). Contacts the Lease Admin adds are approved on entry. Final approval needs the required contacts approved, not just present. | — | F2 |
| CR certificate | Stays an optional document, with nothing extracted, until the client confirms whether it's required (*pending Cenomi*, M1). | — | — |
