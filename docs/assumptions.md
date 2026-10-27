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
