# Demo script — Send Inquiry Agent on the flow v2 order

**Audience:** Muzammil (Cenomi). **Length:** about 30 minutes, plus questions. **Order:** flow v2 ([spec](specs/flow-v2-alignment.md), day F5): the public intake in the app's section order, the first level with a re-upload, the second level with Forecasted Sales Data and contacts, a registered CR, and the call centre. Each beat names its scenario (S1–S24, CC1–CC3 in [`docs/flow-v2/scenarios.json`](flow-v2/scenarios.json)) and the 4 Nov feedback it still answers (F = client feedback, I = our improvement). The checklist at the end maps both to the beats. What to type, line by line, is in [demo-queries.md](demo-queries.md).

**Rehearse:**
- `make e2e-demo` runs this script end to end, scripted (`e2e/tests/demo.spec.ts`). Use `make e2e-demo-headed` to watch it, or `make e2e-demo-step` to step through it.
- For the restart beat on Postgres, run `make demo` in one terminal, then `make e2e-demo-stack` in another.
- Desktop only; not part of `make e2e-int`.

---

## Before the call (10 minutes)

1. Run `make demo`. It uses Postgres, mock integrations, the SMS code **1234**, an email link button, and every console. The flow v2 intake is on (`flow_v2_intake.enabled` in `backend/app/policy/policy.yaml`).
2. Open **http://localhost:5173/dev** and press **Reset demo**. This clears everything and seeds three cases:
   - **Case A**, first review: an expired profile, a profile expiring soon, and a profile check.
   - **Case B**, Lead Approved with its contacts in, waiting for the final **Approve Lead**.
   - **Case C**: approved and sent to Yardi.

   "Demo cases" on `/dev` links each case "as Leasing Admin" and "as RLM" (the Regional Sales Manager).
3. **Files.** The mock document review reads fields and expiry **by file name**. Copy these from `e2e/fixtures/files/` to a folder on the desktop:

| File | What the mock reads |
| --- | --- |
| `company_profile.pdf`, `brand_profile.pdf` | nothing to fill; valid for a year (plain uploads) |
| any file with `expired` or `soon` in its name | a profile expired 30 days ago, or expiring in 7 days |
| any PDF or spreadsheet | Forecasted Sales Data (beat 6) |

4. Open these tabs, each in its own browser window or profile so the sign-ins don't mix:
   - the applicant: **http://localhost:5173**;
   - the Leasing Admin and the Regional Sales Manager: from `/dev` (reviewer links, or "Demo cases");
   - the call centre: **Sami Al Anazi** on `/dev`, then **http://localhost:5173/callcentre**.
5. Send Muzammil the flow (`docs/POC-LIFECYCLE.md` §2.1–§2.4) and the scenario page ([Prospective Tenant Journey v2](https://claude.ai/artifact/Kkt57H5ZLgu2mBbG7nZRi6)).

**If the model is slow on the day:** form mode finishes the intake without it (story S13). Set `FORM_MODE=true` and restart the backend; the chat shows the form-mode card and every step still works.

---

## Run of show

| # | Who | Beat | Scenario | Feedback |
| --- | --- | --- | --- | --- |
| 0 | Presenter | `/dev`: personas, Reset demo, the seeded cases | — | I6 |
| 1 | Applicant | Company Registration: **Skip** → **Office** → what you sell → basic info → email link + code → two malls → terms → documents → submit | S1, S10, S12 | F1, F5, I15 |
| 2 | Leasing Admin | "Inquiry for approval" email → case → expiry → approve one profile, reject the other → **Request re-upload** | S18 | F7, F8, I13, I18 |
| 3 | Applicant | Case link → "what do you need from me?" → re-upload → **Resubmit** | S18 | F16 |
| 4 | Leasing Admin | The new file needs a decision again → approve → **Approve first level** → *Tenant Qualified* | S18, S20 | F8, F16, I4 |
| 5 | Regional Sales Manager | Assign the unit → *(optional)* ask the reviewer assistant → **Request Forecasted Sales Data** | S21 | — |
| 6 | Applicant | Case link → upload the Forecasted Sales Data → **Send** | S21 | — |
| 7 | Regional Sales Manager | **Approve Lead?** → **Yes, approve lead** → *Lead Approved* | S21, S23 | — |
| 8 | Applicant | "Are you the authorised signatory?" → **Yes** → billing contact → **Send contacts** | S24 | F19, I16 |
| 9 | Presenter | *(optional)* restart the backend, reload: nothing lost | — | I6 |
| 10 | Regional Sales Manager | **Approve Lead** → *Approved and sent to Yardi* | S23 | F8 (levels), I8 |
| 11 | Applicant | Tracking page shows the outcome | — | — |
| 12 | Tenant | A registered CR → "Customer already registered. Please login" → sign in → Leasing Opportunities | S3 | F1, F2, F3 |
| 13 | Call centre | Existing CR, existing contact → **Inform** → **Email sign-in link** | CC1 | — |
| 14 | Leasing Admin | Seeded Case A: expired and expiring soon | — | F8, I18 |

---

## The beats

### 0. `/dev` (I6)
Show **Demo cases** (A, B, C) and the persona links. Say: every flow today runs on Postgres, and reset puts the demo back exactly here.

### 1. Applicant: the public page in the app's order (S1, S10, S12; F1, F5)
Applicant tab, **http://localhost:5173**. Keep the draft panel open. The chat follows the app's sections: Company Registration, unit type and category, basic info, verification, property details, terms, documents.

| Step | Do | Point out |
| --- | --- | --- |
| a | The welcome asks for the **Company Registration**. Press **Skip** → **Yes, continue without it** | The public page never looks up or repeats a CR without the card (F1) |
| b | It asks **Store or Office?** Press **Office** (or type `an office`) | One question at a time, not a form (F5) |
| c | `we sell specialty coffee and pastries` → **Looks right** on the card | The category is worked out from the answer and confirmed by the applicant |
| d | Basic info in one line: `Sara Ali, Bean Street Trading Co., King Fahd Road Al Olaya Riyadh, brand Bean Street / بين ستريت, sara@beanstreet.example, 0501234567` → **Looks right** | It saves only what was typed; anything it worked out waits for a confirm |
| e | On the verification card: **Open verification link (demo)**, then code **1234** | Verification comes straight after basic info, as in the app |
| f | `Riyadh Mall A and Jeddah Mall A, around 40 sqm` → **Looks right** | Two malls in two regions are fine (up to five); routing follows the first mall |
| g | Tick the terms, then upload `company_profile.pdf` and `brand_profile.pdf` on the documents card | Terms come before documents (flow v2) |
| h | Review card → **Submit inquiry** | The reference **GEO-OFF-…**; submit is a button, never the model |

### 2. Leasing Admin: the approval email (S18; F7, F8, I13, I18)
`/dev/inbox` → the newest **Inquiry for approval … (GEO-…)** → its link opens the case, signed in as the Leasing Admin.

- **Case brief** and the stage *With the Leasing Admin*. **Approve first level** is disabled until every document is approved (F8).
- Each profile shows its expiry: **Valid until …** (I18). Approve the **Company Profile**.
- **Brand Profile:** remarks `Logo page missing` → **Reject** → **Request re-upload**. The stage reads *waiting for re-upload*.

### 3. Applicant re-uploads (S18; F16)
`/dev/inbox` → `reupload_request` to `sara@beanstreet.example` → open the case link.
- The upload card asks only for the Brand Profile and shows the remark.
- Ask `what do you need from me?` The case chat names only the rejected document and the remark, never the reviewer.
- Upload `brand_profile.pdf` → **Resubmit**. The status card reads *With the Leasing Admin*.

### 4. Leasing Admin approves again (S18, S20; F8, F16, I4)
Reload the case.
- The new Brand Profile is back to **Waiting for a decision**; the Company Profile keeps its approval (F16).
- Approve it → **Approve first level**. The stage reads **Tenant Qualified**, and the timeline shows *Document rejected: brand profile*.

### 5. Regional Sales Manager: unit and Forecasted Sales Data (S21)
On `/dev` → the reviewer list → the Regional Sales Manager, or open the case with `?as=`.
- **Approve Lead?** lists what's missing: *Assign the unit first*.
- **Assign the unit**: the mall (Riyadh Mall A, the first one), unit `G-014`, area `95` → **Assign unit**.
- *(Optional, E2)* In the **Reviewer assistant**, ask `Should I ask this applicant for forecasted sales data?` It gives the facts and the rule, and leaves the decision to the RSM; it never sends the request.
- Note `Monthly, first year.` → **Request Forecasted Sales Data**. **Approve Lead?** now waits: *Forecasted Sales Data not received yet*.

### 6. Applicant: Forecasted Sales Data (S21)
`/dev/inbox` → `sales_data_request` → case link → `here it is` → the upload card → upload any PDF or spreadsheet → **Send**.

If nothing arrives for 72 hours, the RSM's **Needs attention** gets a drafted reminder (`/dev` → **+72 h**); nothing is sent without the RSM.

### 7. Regional Sales Manager: Approve Lead? = Yes (S21, S23)
Reload the case → **Yes, approve lead**. The stage reads **Lead Approved**; the final **Approve Lead** stays disabled until the mandatory contacts are in. There's no reject after this point (M26).

### 8. Applicant: the signatory question (S24; F19, I16)
`/dev/inbox` → `contacts_request` → case link.
- The case chat asks **Are you the authorised signatory for your company?** → **Yes, I'm the authorised signatory**.
- Give a billing contact, e.g. `Billing is Omar Saleh, omar@beanstreet.example, +966551234567` → **Send contacts**.
- One question replaces the contact form (F19). Contacts aren't approved one by one in flow v2 (M15, M26): the RSM checks them before the final approval.

### 9. *(Optional)* Restart (I6)
In a terminal: `docker compose -f docker-compose.yml -f docker-compose.demo.yml restart backend`. Wait about 10 seconds, then reload every tab. The case, its decisions and the chats are all there.

### 10. Regional Sales Manager: Approve Lead → Yardi (S23; F8, I8)
Reload the case → **Approve Lead** → **Approved and sent to Yardi**. `/dev/inbox` shows `inquiry_accepted` to Sara, and Tenant Central invitations for the contacts without an account.

### 11. Tracking
Open the tracking link from Sara's submission email. It reads *Approved — your details are with the leasing team for a proposal*.

### 12. A registered CR → sign in → Leasing Opportunities (S3, M13; F1, F2, F3)
Applicant tab → **Restart** (chat header).
1. On the Company Registration card, type `1010000000` → **Verify**. The chat says **Customer already registered. Please login** with the sign-in card, and asks for nothing else (F3: a registered company isn't asked again for what Cenomi holds).
2. **Sign in to Tenant Central** → **Oasis Coffee Company — Layla Hassan**. This lands on **Leasing Opportunities** (F2), where the chart ends (connector A). There is no **Raise inquiry**: raising an inquiry from Tenant Central isn't on the client-approved chart.

### 13. Call centre: the caller already has a login (CC1)
Call-centre tab (**Sami Al Anazi**) → **New inquiry**.
1. `The caller's CR number is 1010000000.` The **Check contact** card asks only for the caller's email.
2. `layla.hassan@oasiscoffee.example` → **Check contact**. The **Inform** card gives the words to say: the caller already has a Tenant Central login.
3. **Email sign-in link**. `/dev/inbox` shows `sign_in_link` to Layla. No inquiry is created, and **Send application link** doesn't appear.

A new email instead (`huda.saleh@oasiscoffee.example`) is captured fresh, with nothing prefilled from the tenant record (CC2); see the appendix.

### 14. Seeded Case A: expiry (F8, I18)
On `/dev` → **Demo cases** → Case A **as Leasing Admin**.
- Company Profile: **Expired on …**. **Approve** is disabled and **Reject** comes with the remarks proposed. Nothing is approved or rejected automatically.
- Brand Profile: **Expiring soon**. The Leasing Admin decides.
- The brief also shows the profile check (company name).

*Short on time?* Case B "as RLM" shows the final **Approve Lead** (beat 10) in one click, and Case C shows a case sent to Yardi.

---

## Feedback checklist (for Muzammil)

| Feedback or decision | What we show | Beat |
| --- | --- | --- |
| F1 — no CR lookup without the applicant's say-so | Company Registration card: Skip, or a CR checked once with the sign-in reply | 1, 12 |
| F2 — registered → sign in → land where the inquiry is raised | Sign-in card → Leasing Opportunities | 12 |
| F3 — don't ask registered companies for what Cenomi holds | A registered CR is sent to sign in and asked for nothing else | 12 |
| F5 — don't open with one all-fields message | The app's sections, one question at a time | 1 |
| F6 — check documents against the answers | Case A's profile check | 14 |
| F7 — the reviewer starts from an "inquiry for approval" notification | `review_assigned` email opens the case | 2 |
| F8 — approve documents before the first level; levels | Per-document approval; first level waits for it; expiry; Approve Lead? then Approve Lead | 2, 4, 7, 10, 14 |
| F16 — re-uploads need approval again | The new Brand Profile is decided again | 4 |
| F19 — "Are you the authorised signatory?" | Signatory card instead of a contact form | 8 |
| M15, M26 — no per-contact approval; no reject after Approve Lead? = Yes | Contacts checked before the final Approve Lead | 7, 8, 10 |
| M16 — call centre: existing contact → Inform; new contact → fresh capture | Check contact → Inform → Email sign-in link | 13 |
| M25 — several malls in one inquiry | Two malls, two regions | 1 |
| E2 — reviewer assistant on Forecasted Sales Data | Facts and the rule; the RSM decides | 5 |

Replaced in flow v2: F12 and F18 (per-contact approval, M15) and the "Does your company have a CR?" card (now the Company Registration card). Not in this round (agreed 4 Nov): F4 request access, F9 UAT walkthrough, F10 the real document review agent, F11 lead codes, F20 CR certificate.

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

**Automated (`make e2e-demo`):** `e2e/tests/demo.spec.ts` ("Demo script — flow v2") runs beats 0–8 and 10–14 in order after `POST /api/dev/reset`. Beat 1 is the catalogue's `demo` path (`docs/flow-v2/scenarios.json`, script `flow-v2-demo`, also run by AGENT-DET); beats 3, 6 and 8 use the S18, S21 and S24 case scripts; beats 12 and 13 run the catalogue's S3 and CC1. It checks the chart path after beats 1, 10 and 13, and the outbox for `review_assigned`, `reupload_request`, `sales_data_request`, `contacts_request`, `inquiry_accepted` and `sign_in_link`. The scripted run skips the restart beat, because Playwright owns that backend. `make e2e-demo-stack` runs the restart on the Docker stack: Case B is Lead Approved, the backend restarts, the page reloads with nothing lost, and the RSM approves to Yardi.

---

## Appendix — other flows (still working)

These aren't in the run of show but work if Muzammil asks. Each has its own Playwright story in `make e2e-int`.

### Call centre: a new contact or a new CR (CC2, CC3; §7.1.1 a2)

On **http://localhost:5173/callcentre** (**Sami Al Anazi** for the call centre; **Dana Al Rashid** for Guest Service):

1. **New inquiry** opens the chat in **assisted mode** (badge: from the call centre / Guest Service).
2. **CC2, existing CR, new contact:** `The caller's CR number is 1010000000.` → **Check contact** with `huda.saleh@oasiscoffee.example`. The caller is captured fresh, in the app's order, with nothing prefilled from the tenant record.
3. **CC3, new CR:** skip the CR and dictate the caller section by section (e.g. `Bean Street Trading Co., Olaya Street Riyadh — coffee kiosk at Riyadh Mall A, brand Bean Street`, then `Sara Ali, sara@beanstreet.example, 0501234567`). The agent talks to the executive, never names verification, codes or documents, and confirms what staff typed.
4. When the basic info is complete, the **Send application link** card appears → `complete_application` in **/dev/inbox**.

Handoff cases from self-service appear under **Open handoffs** on the same page. On the reviewer case page the channel reads **Started by the call centre** or **Started by Guest Service**.

### Applicant completes an assisted link

1. From **/dev/inbox**, open the **complete_application** email → **Open link** (demo).
2. The email is already verified; the **basic info review** card lists the staff-entered fields → **Edit** if needed → **Proceed**.
3. SMS code **1234**, then the rest of the sections, the documents and **Submit**.

### Other public-page paths

| Path | How | Scenario |
| --- | --- | --- |
| Upload the profiles instead of typing | Choose to upload on basic info; the confirm cards show *from: Company Profile …* | S13 |
| Wrong file type or too large | Upload a `.exe`, or a file over the limit | S14 |
| Same CR and mall as an open inquiry | A duplicate warning on the case; submit still goes through | S15 |
| A side question mid-flow | `how long does the review take?` — answered, then back to the section | S16 |
| Submit fails | The inquiry stays pending with its one reference, and nothing claims success; the retry submits it | S17 |
| Not qualified / Lead rejected | Reject at the first level, or **Approve Lead?** = No | S19, S22 |

### §A4 — Agentic core (L3–L5 moments)

Each beat maps to [DELIVERY-PLAN.md](./DELIVERY-PLAN.md) §A4.

#### L3 — Reliable intake

| Capability | How to show it | Notes |
| --- | --- | --- |
| Self-service intake | Beat 1 + [demo-queries.md](./demo-queries.md) | Sections, evidence, guardrails |
| **Restart mid-inquiry** | With `DATA_DIR` set: start one section → **restart the backend** (same tab) → send the next message; draft and transcript continue | API test `test_backend_restart_mid_inquiry_continues` |
| **Form mode (model down)** | `FORM_MODE=true`, restart the backend, new session: the form-mode card; fill the fields, verification, documents, review → submit | Story **S13**; scripted `llm:unavailable:2` |
| Audit (intake) | With `DEV_TOOLS`: `GET /api/dev/audit/{session_id}`, and `GET /api/dev/flow/{id}` for the chart steps | The case timeline merges session and case ids after submit |

#### L4 — Outcome assistance

| Capability | How to show it | Notes |
| --- | --- | --- |
| **Re-upload loop** | Beats 2–4 | S18; story T2 |
| **Second level → Yardi** | Beats 5–10 | S21, S23, S24; story T1 |
| **Reviewer assistant** | Beat 5 (Forecasted Sales Data); on a second review, *Find the Yardi company for Bean Street Trading.* → **Use** → **Link company** | E2; scripted `r1-yardi-suggest` |
| **Audit timeline** | Any case page: intake and case transitions, requests, notifications | |

#### L5 — Governed proactivity

| Capability | How to show it | Notes |
| --- | --- | --- |
| Stalled review → queue email | Fresh submit → leave in first review → `/dev` → **+48 h** → one `review_stalled` email; **Needs attention** badge **1** | `review_stall_hours` 48 |
| Escalation → region manager | Same case → **+48 h** again → `review_escalated` | 96 h total |
| Unanswered request → drafted reminder | Beat 5 → **+72 h** → **Needs attention** → the drafted reminder → **Approve and send** | E4 |
| Quiet hours (Riyadh) | **Approve and send** at **23:00** → *held until* morning; **To morning (08:00)** → one `applicant_reminder` | `22:00–08:00 Asia/Riyadh` |

### Reviewer console cheat sheet

1. **http://localhost:5173/review** → pick a reviewer (mock sign-in) → open **GEO-…** from the queue or from a `review_assigned` / request email in **/dev/inbox**.
2. Read the **case brief** (deterministic, no model).
3. **First level (Leasing Admin):** decide each document → re-upload **or** **Approve first level** (*Tenant Qualified*), or **Reject** (*Tenant Not Qualified*).
4. **Second level (Regional Sales Manager):** assign the unit → *(optional)* Forecasted Sales Data → **Approve Lead?** Yes (*Lead Approved*) or No (*Lead Rejected*) → contacts in → **Approve Lead** (*Approved and sent to Yardi*).
5. End on the **Audit timeline** and the applicant's **/inquiry/status/…** page.
