# POC assumptions

Each open question has an assumption the POC builds on. Integrations sit behind interfaces, so replacing an assumption later is an adapter or config change.

| Area | Assumption |
| --- | --- |
| CR verify | Mocked. `1010123456` → new account with sample company details; `1010000000` → existing account; other valid numbers → new, no details. CR format: 10 digits. |
| Existing account | The agent points the user to Sign In; no inquiry is created. |
| CR optional | Skipping is allowed, as today. The agent recommends providing it once. |
| Contact | One number: `+9665…` is mobile, anything else is a landline. Either satisfies the requirement. |
| OTP | Mocked, code `1234` (`OTP_MOCK_CODE`). One code covers phone and email. 3 attempts, then an automatic resend. |
| Email | Format check only; no company-domain rule. |
| Arabic brand name | The agent proposes it; the user confirms or edits. |
| Unit type, sales category | Derived from the user's description, mapped to master ids, confirmed by the user. |
| Property fields | Malls required; area, rent, rent period and lease optional. Area defaults to 10 – 25,000 sqm. |
| Rent period | Monthly, Yearly. |
| Lease period | 1, 2, 3, 5 years. |
| Consent | Only the review card's checkbox + Submit. Never inferred. |
| Documents | Company Profile and Brand Profile required; CR, VAT, National ID/Iqama, National Address, Article of Association optional. Presence, extension and size (≤ 5 MB) only — no content processing. |
| Storage | Local disk under `UPLOAD_DIR`. |
| Master data | Seeded JSON with sample malls (Riyadh/Jeddah/Dammam "Mall A…"). Replace with real data before any demo to Cenomi stakeholders. |
| Submit | Mocked with the same payload shape as the current form. Reference `GEO-{STR|MED|SPC|OFF}-{6 digits}`. |
| Status | Mocked: any submitted reference returns "Under review". |
| Email notifications | Not sent; logged only. |
| Language | English UI; the agent can greet in Arabic. Full Arabic is phase 2. |
| Persona | "Cenomi leasing assistant": warm, professional; small talk and FAQ allowed, always easing back to the inquiry. |
| FAQ | 8–10 placeholder answers, marked `[to be confirmed]` where facts are unknown. |
| Session | Unauthenticated, in memory, 2-hour idle expiry, no cross-session resume. Rate limited. |
