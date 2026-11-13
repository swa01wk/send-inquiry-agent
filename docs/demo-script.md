# Demo script — Send Inquiry Agent, re-demo Tue 10 Nov 2026

**Audience:** Muzammil (Cenomi). **Length:** about 25 minutes, plus questions. **Order:** the 10 Nov script in [demo feedback](specs/demo-feedback.md) §3.6 and the R5 day prompt. Each beat names the feedback it answers (F = client feedback, I = our improvement), so Muzammil can tick them off as you go. The checklist at the end maps every feedback point to its beat.

**Rehearse:**
- `make e2e-demo` runs this script end to end, scripted. Use `make e2e-demo-headed` to watch it, or `make e2e-demo-step` to step through it.
- For the restart beat on Postgres, run `make demo` in one terminal, then `make e2e-demo-stack` in another.
- Desktop only; not part of `make e2e-int`.

---

## Before the call (10 minutes)

1. Run `make demo`. It uses Postgres, mock integrations, the SMS code **1234**, an email link button, and every console.
2. Open **http://localhost:5173/dev** and press **Reset demo**. This clears everything and seeds three cases:
   - **Case A**, first review: an expired profile, a profile expiring soon, and a profile check.
   - **Case B**, second review: the billing contact is waiting for approval.
   - **Case C**: approved and sent to Yardi.

   "Demo cases" on `/dev` links each case "as Lease Admin" and "as RLM".
3. **Profile files.** The mock document review reads fields **by file name**; any other name gives no fields. Copy these from `e2e/fixtures/files/` to a folder on the desktop:

| File | What the mock reads |
| --- | --- |
| `company_profile_match.pdf` | Bean Street Trading Co., King Fahd Road, Al Olaya, Riyadh |
| `brand_profile_match.pdf` | Bean Street, café |
| `company_profile_mismatch.pdf` | Bean Street **Holding Company** (differs) |
| `new_brand_profile.pdf` | Oasis Bakehouse, café (R4) |
| `oasis_company_profile_mismatch.pdf` | Oasis Coffee **Trading Establishment** (differs from the Cenomi record) |
| `brand_profile.pdf`, `company_profile.pdf` | nothing (plain uploads) |

4. Open these tabs, each in its own browser window or profile so the sign-ins don't mix:
   - the applicant: **http://localhost:5173**;
   - the Lease Admin and the RLM: from `/dev` (reviewer links, or "Demo cases").
5. Send Muzammil the three-lane flow (`docs/POC-LIFECYCLE.md` §2.4) and the updated design doc (F14, F15).

**If the model is slow on the day:** form mode finishes the intake without it (story S13). Set `FORM_MODE=true` and restart the backend; the chat shows the form-mode card and every step still works.

---

## Run of show

| # | Who | Beat | Feedback |
| --- | --- | --- | --- |
| 0 | Presenter | `/dev`: personas, Reset demo, the seeded cases | I6 |
| 1 | Applicant | Turn by turn: CR? **No** → upload the profiles → confirm → email link + code → submit | F1, F5, F6, I15, I19 |
| 2 | Lease Admin | "Inquiry for approval" email → case → expiry → approve one profile, reject one → **Request re-upload** | F7, F8, I13, I18 |
| 3 | Applicant | Case link → re-upload → **Resubmit** | F16 |
| 4 | Lease Admin | The new file needs approval again → approve → **Approve first level** | F8, F16, I4 |
| 5 | Applicant | "Are you the authorised signatory?" → **Yes** → billing contact | F19, I16 |
| 6 | Lease Admin | Reject the billing contact → the applicant fixes it → approve | F12, F16, F18, I5 |
| 7 | Presenter | *(optional)* restart the backend, reload: nothing lost | I6 |
| 8 | RLM | **Approve** → sent to Yardi | F8 (levels), I8 |
| 9 | Applicant | Tracking page shows the outcome | — |
| 10 | Applicant + Lease Admin | Typed company, mismatching profile → one-sentence warning → the flag in the brief | F6, I19 |
| 11 | Tenant + Lease Admin | CR? **Yes** → sign in → Leasing Opportunities → new brand: company from Yardi, both profiles, checked against the record | F2, F3, I3, I9 |
| 12 | Lease Admin | Seeded Case A: expired and expiring soon | F8, I18 |
| 13 | Applicant | *(optional, "power user")* everything in one message | I15 |

---

## The beats

### 0. `/dev` (I6)
Show **Demo cases** (A, B, C) and the persona links. Say: every flow today runs on Postgres, and reset puts the demo back exactly here.

### 1. Applicant, turn by turn (F1, F5, F6, I15, I19)
Applicant tab, **http://localhost:5173**. Keep the draft panel open.

| Step | Do | Point out |
| --- | --- | --- |
| a | Type `Hi, I'd like to lease a space` | The welcome, then the card **Does your company have a CR?** |
| b | Press **No, we don't** | The public page never asks for, looks up or repeats a CR number (F1) |
| c | The agent offers **I'll type them** / **I'll upload the profiles**. Press **I'll upload the profiles** | One line, no push either way (F6, I19) |
| d | Answer its questions one at a time, e.g. `A specialty coffee kiosk at Riyadh Mall A`, then `Sara Ali, sara@beanstreet.example, 0501234567` | One question at a time, not a form (F5); it doesn't ask for the company or brand, because the profiles will give them |
| e | Confirm the unit type and category on the card | Values the agent worked out are confirmed by the applicant |
| f | On the verification card: **Open verification link (demo)**, then code **1234** | Verification stays in the chat (accepted on 3 Nov) |
| g | On the documents card, upload `company_profile_match.pdf` | The confirm card shows the company name and address **from: Company Profile, company_profile_match.pdf** |
| h | **Looks right**. Upload `brand_profile_match.pdf` → **Looks right**. Give the Arabic brand name if asked (`بين ستريت`) | Nothing filled from a document is used until the applicant confirms it |
| i | Review card → tick the terms → **Submit inquiry** | The reference **GEO-…**; submit is a button, never the model |

### 2. Lease Admin: the approval email (F7, F8, I13, I18)
`/dev/inbox` → the newest **Inquiry for approval: Bean Street at Riyadh Mall A (GEO-…)** → its link opens the case, signed in as the Lease Admin.

- **Case brief** and **First review**. **Approve first level** is disabled until every document is approved (F8).
- Each profile shows its expiry: **Valid until …** (I18). Approve the **Company Profile**.
- **Brand Profile:** remarks `The logo page is missing` → **Reject** → **Request re-upload**. The stage reads *waiting for re-upload*.

### 3. Applicant re-uploads (F16)
`/dev/inbox` → `reupload_request` to `sara@beanstreet.example` → open the case link.
- The upload card asks only for the Brand Profile and shows the remarks.
- Upload `brand_profile.pdf` → **Resubmit**. The status card reads **First review**.

### 4. Lease Admin approves again (F8, F16, I4)
Reload the case.
- The new Brand Profile is back to **Waiting for a decision**; the Company Profile keeps its approval (F16).
- Approve it → **Approve first level** → **Lead — second review**.
- The timeline shows *Document rejected: brand profile*.

### 5. Applicant: the signatory question (F19, I16)
`/dev/inbox` → `contacts_request` → case link.
- The case chat asks **Are you the authorised signatory for your company?**
- Press **Yes, I'm the authorised signatory**.
- Give a billing contact, e.g. `Billing is Omar Saleh, omar@beanstreet.example, +966551234567` → **Send contacts**.
- One question replaces the contact form (F19). The signatory is already verified by the email link and code.

### 6. Lease Admin: contact approval (F12, F16, F18, I5)
Reload the case.
- **Authorized Signatory: Approved**; **Billing Contact: Waiting for approval**.
- Remarks `Use the finance mailbox` → **Reject**. The applicant gets a new `contacts_request` with the remarks, fixes the email in the case chat → **Send contacts**.
- Back in the console: **Approve** the billing contact. Every contact is approved individually, and a resubmitted one is approved again (F16).

### 7. *(Optional)* Restart (I6)
In a terminal: `docker compose -f docker-compose.yml -f docker-compose.demo.yml restart backend`. Wait about 10 seconds, then reload every tab. The case, its decisions and the chats are all there.

### 8. RLM: final approval (F8, I8)
On `/dev` → the reviewer list (or "Demo cases") → the RLM, or open the case with `?as=` the RLM.
- The RLM sees the document and contact decisions read-only.
- Press **Approve** → **Approved and sent to Yardi**.
- `/dev/inbox` shows `inquiry_accepted` to Sara, and Tenant Central invitations for the contacts without an account.

### 9. Tracking
Open the tracking link from Sara's submission email. It reads *Approved — your details are with the leasing team for a proposal*.

### 10. Typed company and a profile check (F6, I19)
Applicant tab → **Restart** (chat header) → `Hi, I'd like to lease a space` → **No, we don't** → **I'll type them**.
1. Type `My Coffee Shop LLC, Olaya Street, Riyadh`, then the brand, space and contact as in beat 1.
2. After verification, upload `company_profile_mismatch.pdf`. The agent says in one sentence that the profile shows a different company name and asks which to keep.
3. Reply `Keep my company name`. Upload `brand_profile_match.pdf` → submit. A difference never blocks submit.
4. In the Lease Admin tab, open the new case. The brief lists the **profile check** (company name: typed vs Company Profile).

### 11. Signed in: a new brand (F2, F3, I3, I9)
Applicant tab → **Restart** → **Yes, we have a CR** → **Sign in to Tenant Central** → sign in as **Oasis Coffee Company — Layla Hassan**. This lands on **Leasing Opportunities** (F2).
1. **Raise inquiry** on **OPP-101** (Riyadh Mall A). There's no brand picker: every inquiry raised here is for a new brand.
2. The greeting says the company details come from **your Cenomi record**. The card shows Oasis Coffee Company, filled from Yardi by CR and marked verified (F3). Press **Proceed**.
3. `I'll upload the Brand Profile` → the documents card asks for **both** profiles, even though Oasis sent them before.
4. Upload `new_brand_profile.pdf` → confirm **Oasis Bakehouse** → give the Arabic name `مخبز الواحة`.
5. Upload `oasis_company_profile_mismatch.pdf`. The agent says the profile differs from **the Cenomi record**. Reply `Keep the record's name` → **Submit inquiry**.
6. In the Lease Admin tab, the new case's brief flags the company name against the record.

### 12. Seeded Case A: expiry (F8, I18)
On `/dev` → **Demo cases** → Case A **as Lease Admin**.
- Company Profile: **Expired on …**. **Approve** is disabled and **Reject** comes with the remarks proposed. Nothing is approved or rejected automatically.
- Brand Profile: **Expiring soon**. The Lease Admin decides.
- The brief also shows the profile check (company name).

*Short on time?* Case B "as Lease Admin" shows the contact approval (beat 6) in one click, and Case C shows a case sent to Yardi.

### 13. *(Optional)* Power user (I15)
Applicant tab → **Restart** → **No, we don't** → **I'll type them**, then paste one message:
`Acme Trading LLC, King Abdullah Road, Riyadh. Bean Street (بين ستريت) specialty café at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567.`
The agent fills everything it can and asks only for what's left.

---

## Feedback checklist (for Muzammil)

| Feedback | What we show | Beat |
| --- | --- | --- |
| F1 — no CR lookup on the public page | CR question; a typed CR number gets the sign-in reply and isn't stored | 1, 11 |
| F2 — Yes → sign in → land where the inquiry is raised | Sign-in card → Leasing Opportunities | 11 |
| F3 — don't ask registered companies for what Cenomi holds | Company from Yardi by CR; new brand with both profiles | 11 |
| F5 — don't open with one all-fields message | Turn-by-turn opening; the paste is optional | 1, 13 |
| F6 — check documents against the answers | Fill from profiles with evidence; mismatch warning and brief flag | 1, 10, 11 |
| F7 — the reviewer starts from an "inquiry for approval" notification | `review_assigned` email opens the case | 2 |
| F8 — approve documents before the first level | Per-document approval; first level waits for it; expiry | 2, 4, 12 |
| F12, F18 — contacts approved individually | Per-contact approval with remarks | 6 |
| F14, F15 — three-lane flow; approvals in the design doc | Shared before the call | Before the call |
| F16 — re-uploads and resubmitted contacts need approval again | Brand Profile and billing contact decided again | 4, 6 |
| F19 — "Are you the authorised signatory?" | Signatory card instead of a contact form | 5 |

Not in this round (agreed 4 Nov): F4 request access, F9 UAT walkthrough, F10 the real document review agent, F11 lead codes, F20 CR certificate.

---

## Personas and links

| Persona | URL |
| --- | --- |
| Demo hub | http://localhost:5173/dev |
| Applicant chat | http://localhost:5173 |
| Tenant Central | http://localhost:5173/tenant (or the tenant links on `/dev`) |
| Dev inbox | http://localhost:5173/dev/inbox |
| Reviewer queue / case | http://localhost:5173/review, or a case link from an email |
| Needs attention | http://localhost:5173/review/attention |
| Call centre / Guest Service | http://localhost:5173/callcentre |
| Applicant case link | From an email in the dev inbox → `/inquiry/case?t=…` |
| Tracking | `/inquiry/status/{reference}?t=…` from the submission email |

**Automated (`make e2e-demo`):** `e2e/tests/demo.spec.ts` ("Demo script — 10 Nov") runs beats 0–6 and 8–12 in order after `POST /api/dev/reset`, with outbox checks on `review_assigned`, `reupload_request`, `contacts_request` and `inquiry_accepted`. The scripted run skips the restart beat, because Playwright owns that backend. `make e2e-demo-stack` runs the restart on the Docker stack: Case B's billing contact is approved, the backend restarts, the page reloads with nothing lost, and the RLM approves to Yardi.

---

## Appendix — flows from the 3 Nov demo (still working)

These aren't in the 10 Nov run of show but still work if Muzammil asks. Each has its own Playwright story in `make e2e-int`.

### Call centre and Guest Service (§7.1.1 a2)

Use **http://localhost:5173/callcentre** or open staff from **/dev** (**Sami Al Anazi** for the call centre; **Dana Al Rashid** for Guest Service). Mock sign-in if prompted (`?as=customer-care-1` or pick a row on **/dev**).

1. Click **New inquiry** — chat opens in **assisted mode** (badge: from the call centre / Guest Service).
2. Dictate the caller in three short messages (same as scripted e2e `a2-call-centre`):
   - `Skip the CR for now`
   - `Bean Street Trading Co., Olaya Street Riyadh — coffee kiosk at Riyadh Mall A, brand Bean Street`
   - `Sara Ali, sara@beanstreet.example, 0501234567`  
   (Same bundles as self-service; the agent talks about “the caller”, never asks for verification, documents or consent on this side.)
3. When details are ready, use the **Send application link** card → check **/dev/inbox** for `complete_application` to `sara@beanstreet.example`.
4. **Existing CR (§7.1.2 a2):** one message such as  
   `The caller gave CR 1010000000 for a specialty kiosk at Riyadh Mall A`  
   → **Check contact** card: enter the caller's email.
   - `layla.hassan@oasiscoffee.example` (has a login) — **Inform** card with the words to say → **Email sign-in link** → `sign_in_link` in **/dev/inbox**; **Send application link** must **not** appear.
   - Any new email (e.g. `huda.saleh@oasiscoffee.example`) — captured fresh, nothing prefilled from the tenant record → send link → applicant completes as below.

Handoff cases from self-service appear under **Open handoffs** on the same page; open one to continue the inquiry as staff.

**Guest Service:** same staff turns as the call centre; the applicant chat may say the **Guest Service desk** started the inquiry. On the **reviewer case** page the channel reads **Started by Guest Service**.

---

### Applicant completes an assisted link (§7.1.1 a2)

1. From **/dev/inbox**, open the **complete_application** email → **Open link** (demo) or follow `/inquiry/verify?t=…`.
2. New applicant session: email is already verified; **basic info review** card lists staff-entered fields — **Edit** optional → **Proceed**.
3. SMS code **1234** on the verification card.
4. Upload **Company Profile** and **Brand Profile** → review card → terms → **Submit**.
5. On the reviewer case page, channel shows **Started by Guest Service** for Guest Service–raised inquiries and **Started by the call centre** for call-centre ones.

---

### §A4 — Agentic core (L3–L5 moments)

Each beat maps to [DELIVERY-PLAN.md](./DELIVERY-PLAN.md) §A4. Automated twins: Playwright `@scripted` stories cited below.

#### L3 — Reliable intake

| Capability | How to show it | Notes |
| --- | --- | --- |
| Self-service intake | Beat 1 + [demo-queries.md](./demo-queries.md) | Routing, bundles, evidence, guardrails |
| **Restart mid-inquiry** | With `DATA_DIR` set: start CR + one bundle message → **restart the backend** (same browser tab, same session) → send the next message; draft and transcript continue | Day 2; no Playwright shortcut in repo — manual or API test `test_backend_restart_mid_inquiry_continues` |
| **Form mode (model down)** | Set `FORM_MODE=true`, restart backend, new session: fixed bubble + **form mode** card; fill fields, mall picker, verification, documents, review → submit. Send a chat message after submit: assistant “welcome back” and form mode clears | Story **S13** (`llm:unavailable:2` in scripted e2e); live demo uses `FORM_MODE` |
| Audit (intake) | After any session with `DEV_TOOLS`: `GET /api/dev/audit/{session_id}` — redacted turns, tools, `form_mode_entered`, submit | Case page timeline merges session + case ids after submit |

**Quick alternates (1 minute each):**

- **FAQ:** “What documents do I need to upload?”
- **Existing account:** CR `1010000000` → Sign In guidance, no submit.
- **Resilience:** Stop the backend mid-reply → **Retry**; restart backend and send a message → **Start again** when the session expires.

#### L4 — Outcome assistance

| Capability | How to show it | Notes |
| --- | --- | --- |
| **Re-upload loop (T2)** | Submit Bean Street inquiry → reviewer opens case → **Request re-upload** (e.g. Brand Profile + remarks) → applicant opens **case link** from dev inbox → upload card in **reupload** mode (only requested docs) → resubmit → reviewer timeline shows *Documents resubmitted* | Story **T2** |
| **Contacts + final approval → Yardi (T1)** | After an **existing-tenant** submit: reviewer **Approve first level** → **Lead — second review**; optional **Remove** on a prefilled contact → `contacts_request` email → applicant case chat supplies signatory + billing (e.g. Omar) → **Submit contacts** → **Approve** → **Approved and sent to Yardi**; `azure_ad_invitation` only for contacts **without** an account (Layla skipped, Omar invited). Automated demo uses Oasis + **OPP-101**; story **T1** uses the Bean Street self-service path | Story **T1**; full Yardi beat in `make e2e-demo` |
| **Reviewer assistant — Yardi match** | On **second review**: **Reviewer assistant** → *Find the Yardi company for Bean Street Trading.* → suggestion → **Use** sets company picker **YC-1001** → **Link company** → reload if needed → **Approve**. Assistant never submits; scripted via `e2eScenario=r1-yardi-suggest` in automation | Vitest fixture: `Bean Street Trading Co. (id YC-1001)` |
| **Audit timeline** | Same case page: **Audit timeline** lists intake + case transitions, requests, notifications (routing/tool noise hidden) | Built Day 4; includes post-submit and review events |

Case chat after submit: no intake re-asks; only open requests (re-upload, contacts) drive the dialogue.

#### L5 — Governed proactivity

| Capability | How to show it | Notes |
| --- | --- | --- |
| Stalled review → queue email | Fresh self-service submit → leave in first review → **/dev** → **+48 h** → one `review_stalled` email; reviewer queue **Needs attention** badge **1** | Threshold 48 h (`review_stall_hours`) |
| Escalation → region manager | Same case → **+48 h** again → `review_escalated`; region manager **Needs attention** shows escalation | 96 h total (`review_escalate_hours`) |
| Unanswered request → drafted reminder | Same case → **Approve first level** → **+48 h** then **+24 h** (no auto-send yet) → **Needs attention** → **Draft with assistant** → **Use draft** on the reminder → **Approve and send** | Tier 2; scripted `e2eScenario=r2-tenant-reminder` in automation |
| Quiet hours (Riyadh) | After **Approve and send** at **23:00** local → **held until** morning; **To morning (08:00)** → exactly **one** `applicant_reminder` in the inbox | Policy `22:00–08:00 Asia/Riyadh` |
| `/dev` landing | Personas, demo cases, **Reset demo**, clock buttons (+24 h, +48 h, **To morning**) | Beat 0 |

---

### Reviewer console cheat sheet (T1 / T2)

1. **http://localhost:5173/review** → pick reviewer (mock sign-in) → open **GEO-…** from the queue or from `review_assigned` / request emails in **/dev/inbox**.
2. Read the **case brief** (deterministic, no model).
3. **First review:** re-upload **or** **Approve first level**.
4. **Lead — second review:** wait for contacts fulfillment (applicant case link) → set Yardi re-link if needed (assistant **Use** optional) → **Approve**.
5. End on **Audit timeline** and applicant **/inquiry/status/…** for the Yardi handover message.

---
