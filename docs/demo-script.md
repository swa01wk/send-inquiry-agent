# Demo script — Send Inquiry Agent

Rehearse: `make e2e-demo` (or `make e2e-demo-headed` to watch).

Use with `make demo` (SMS code **1234**; the email link is a demo button). The **self-service happy path** below is ~5 minutes. The **§A3 walkthrough** and **§A4 L3–L5 beats** need mock integrations, the reviewer console, and (for restart) `DATA_DIR` — see [Setup for lifecycle demos](#setup-for-lifecycle-demos).

**Full user story (Sara):** [demo-queries.md](./demo-queries.md). **Coverage map:** [DELIVERY-PLAN.md](./DELIVERY-PLAN.md) §A3 (workflows) and §A4 (L3–L5 core).

---

## Setup for lifecycle demos

| Need | Backend (`backend/.env`) | Frontend (env or `docker-compose`) |
| --- | --- | --- |
| Dev inbox, audit API | `INTEGRATIONS=mock`, `DEV_TOOLS=true` | `VITE_DEV_TOOLS=1` |
| Reviewer console + assistant | `REVIEWER_CONSOLE=true` | `VITE_REVIEWER_CONSOLE=1` |
| Draft survives backend restart | `DATA_DIR=./.data` (default in `.env.example`) | — |
| Form mode without the model | `FORM_MODE=true` (testing only; restart backend) | — |

`make demo` sets `OTP_MOCK_CODE=1234`, `VITE_DEMO=1`, dev tools, reviewer console, call centre, tenant portal, and proactivity (`DEV_TOOLS`, `REVIEWER_CONSOLE`, `CALLCENTRE_CONSOLE`, `TENANT_PORTAL`, `PROACTIVE_ENABLED`).

**Personas (URLs):**

| Persona | URL |
| --- | --- |
| Demo hub | http://localhost:5173/dev |
| Applicant chat | http://localhost:5173 |
| Call centre / Guest Service | http://localhost:5173/callcentre (pick staff on the page, or open from **/dev**) |
| Tenant Central | http://localhost:5173/tenant (mock tenants linked from **/dev**) |
| Dev notification inbox | http://localhost:5173/dev/inbox |
| Reviewer queue / case | http://localhost:5173/review → open a **GEO-…** row |
| Needs attention | http://localhost:5173/review/attention |
| Applicant case link | From email in dev inbox → `/inquiry/case?t=…` |
| Applicant complete link (assisted) | `complete_application` email → `/inquiry/verify?t=…` (new session, email verified) |
| Tracking | `/inquiry/status/{reference}?t=` from submission email |

Use **Restart** in the chat header (demo builds, `VITE_DEMO=1`) to reset the applicant chat without reloading the page.

---

## Happy path — §7.1.1 a1 self-service (~5 min)

1. Open **http://localhost:5173** → welcome + suggestion chips.
2. Click **I have my CR number**, then send: `My CR number is 1010123456`.
3. Confirm company details on the **confirm** card (or say “Yes, that’s correct”).
4. One natural message, e.g.  
   `Bean Street specialty coffee kiosk at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567`
5. Confirm any derived fields (Arabic name, unit type, category).
6. In the verification card, click **Open verification link (demo)**, then enter the SMS code **1234**.
7. Upload **Company Profile** and **Brand Profile** (any small PDF).
8. Review card → accept terms → **Submit** → note the **GEO-…** reference.

---

## Wow moments (intake)

1. **Multi-field capture** — After skip CR or post-CR confirm, paste company + brand + mall + contact in **one** message; watch the draft panel populate without re-asks.
2. **Arabic name suggestion + confirm** — Agent proposes `بين ستريت` (or similar) as derived; confirm card shows source **Suggested · confirm** and an evidence line where the spec requires it.
3. **Draft panel live** — Keep the draft panel visible; each tool write flashes updated rows and the checks list moves toward submit-ready.

---

## §A3 — Full walkthrough (workflows)

Line-by-line requirements live in [workflows-7-1.md](specs/workflows-7-1.md). Rehearse in this order for the Mon 2 Nov demo check.

| Workflow | Demo path | When |
| --- | --- | --- |
| §7.1.1 **a1** — prospective, self-service | [Happy path](#happy-path--711-a1-self-service-5-min) above → submit → tracking email | **Today** (Days 1–3) |
| §7.1.1 **a2** — prospective, call centre | [Call centre / Guest Service](#call-centre-and-guest-service-711-a2) → [applicant from link](#applicant-completes-an-assisted-link-711-a2) | **Today** |
| §7.1.2 **a1** — existing tenant, signed in | [Tenant Central](#tenant-central-712-a1) | **Today** |
| §7.1.2 **a2** — existing tenant, call centre | [Existing CR choice](#call-centre-and-guest-service-711-a2) → prefilled assisted chat → link → applicant completes | **Today** |
| §7.1 — existing tenant on public page | [Public-page sign-in](#public-page-existing-tenant-71) (`sign_in` or `allow_inquiry`) | **Today** |
| §7.1.1 **b** / §7.1.2 **b** — first-level review | Reviewer queue → optional [re-upload (T2)](#l4--re-upload-loop-story-t2) → or **Approve first level** | **Today** (Day 4+) |
| §7.1.1 **c** / §7.1.2 **c** — second-level review | **Lead — second review** → [contacts + Yardi (T1)](#l4--contacts-and-final-approval-to-yardi-story-t1) → optional [reviewer assistant](#l4--reviewer-assistant-yardi-match) on re-link | **Today** (Day 4–5 track) |
| Tracking throughout | Status page: stage, owner role, **Waiting for you**; after Yardi, approved copy for the applicant | **Today** |

**Suggested presenter arc (~15 min):** start at **/dev** → self-service submit (or call-centre path) → **/review** from `review_assigned` → first approval **or** re-upload → second review with contacts → reviewer assistant **Use** on Yardi pickers (optional) → final approval → tracking shows *Approved — your details are with the leasing team for a proposal* → [L5 clock beats](#l5--governed-proactivity) on a stalled case → **Audit timeline** on the case page.

---

## Call centre and Guest Service (§7.1.1 a2)

Use **http://localhost:5173/callcentre** or open **Sami Al Anazi — The Cenomi call centre** / **Guest Service** from **/dev**. Mock sign-in if prompted (`?as=customer-care-1` or pick a Guest Service staff row on **/dev**).

1. Click **New inquiry** — chat opens in **assisted mode** (badge: from the call centre / Guest Service).
2. Dictate the caller in one or two short messages, e.g.  
   `The caller is Omar for a specialty coffee kiosk at Riyadh Mall A — Bean Street Trading, omar@beanstreet.example, +966501234567`  
   (Same bundles as self-service; the agent talks about “the caller”, never asks for verification, documents or consent on this side.)
3. When details are ready, use the **Send application link** card (or the agent offers it) → check **/dev/inbox** for `complete_application`.
4. **Existing CR (§7.1.2 a2):** give an existing tenant CR (e.g. from mock data) → **existing CR choice** card → **Continue for them** (prefilled assisted chat) **or** **Ask them to sign in** (public sign-in path; inquiry marked redirected).

Handoff cases from self-service appear under **Open handoffs** on the same page; open one to continue the inquiry as staff.

---

## Applicant completes an assisted link (§7.1.1 a2)

1. From **/dev/inbox**, open the **complete_application** email → **Open link** (demo) or follow `/inquiry/verify?t=…`.
2. New applicant session: email is already verified; **basic info review** card lists staff-entered fields — **Edit** optional → **Proceed**.
3. SMS code **1234** on the verification card.
4. Upload **Company Profile** and **Brand Profile** → review card → terms → **Submit**.
5. On the reviewer case page, channel shows **assisted** / **Started by the call centre** (or Guest Service).

---

## Tenant Central (§7.1.2 a1)

1. From **/dev**, open a mock tenant (e.g. signed-in tenant admin).
2. **Leasing Opportunities** — filter if needed → **Raise inquiry** on a row.
3. Chat greets by name; one confirm card for prefilled company, property and documents on file; pick brand if several; optional space note.
4. Signed-in tenants skip email/mobile verification → review → **Submit**.
5. **My inquiries** lists the new reference and stage.

---

## Public-page existing tenant (§7.1)

1. Open **http://localhost:5173** (applicant chat).
2. **Sign-in policy:** CR `1010000000` (or another seeded existing tenant) → **sign_in_prompt** card → **Sign in to Tenant Central** (demo copy; no submit on the public chat).
3. **Allow inquiry policy:** CR on the allow list → prefilled **basic info review** → **Proceed** → complete verification/documents if required → submit.

---

## /dev landing

**http://localhost:5173/dev** (`VITE_DEV_TOOLS=1`): one link per persona (applicant, inbox, each call-centre / Guest Service staff, each mock tenant, each reviewer queue, **Needs attention**), plus:

1. **Advance clock** — +24 h, +48 h, **To morning** (quiet-hours demo).
2. **Reset demo** — clears sessions, cases, outbox, clock and mock world for a clean rehearsal.

---

## §A4 — Agentic core (L3–L5 moments)

Each beat maps to [DELIVERY-PLAN.md](./DELIVERY-PLAN.md) §A4. Automated twins: Playwright `@scripted` stories cited below.

### L3 — Reliable intake

| Capability | How to show it | Notes |
| --- | --- | --- |
| Self-service intake | [Happy path](#happy-path--711-a1-self-service-5-min) + [demo-queries.md](./demo-queries.md) | Routing, bundles, evidence, guardrails |
| **Restart mid-inquiry** | With `DATA_DIR` set: start CR + one bundle message → **restart the backend** (same browser tab, same session) → send the next message; draft and transcript continue | Day 2; no Playwright shortcut in repo — manual or API test `test_backend_restart_mid_inquiry_continues` |
| **Form mode (model down)** | Set `FORM_MODE=true`, restart backend, new session: fixed bubble + **form mode** card; fill fields, mall picker, verification, documents, review → submit. Send a chat message after submit: assistant “welcome back” and form mode clears | Story **S13** (`llm:unavailable:2` in scripted e2e); live demo uses `FORM_MODE` |
| Audit (intake) | After any session with `DEV_TOOLS`: `GET /api/dev/audit/{session_id}` — redacted turns, tools, `form_mode_entered`, submit | Case page timeline merges session + case ids after submit |

**Quick alternates (1 minute each):**

- **FAQ:** “What documents do I need to upload?”
- **Existing account:** CR `1010000000` → Sign In guidance, no submit.
- **Resilience:** Stop the backend mid-reply → **Retry**; restart backend and send a message → **Start again** when the session expires.

### L4 — Outcome assistance

| Capability | How to show it | Notes |
| --- | --- | --- |
| **Re-upload loop (T2)** | Submit Bean Street inquiry → reviewer opens case → **Request re-upload** (e.g. Brand Profile + remarks) → applicant opens **case link** from dev inbox → upload card in **reupload** mode (only requested docs) → resubmit → reviewer timeline shows *Documents resubmitted* | Story **T2** |
| **Contacts + final approval → Yardi (T1)** | After submit: reviewer **Approve first level** → stage **Lead — second review**; `contacts_request` email → applicant case chat supplies signatory + billing (e.g. Omar) → **Submit contacts** → reviewer **Approve** when blockers clear → stage **Approved and sent to Yardi**; dev inbox: `inquiry_accepted`, `azure_ad_invitation` for new contact; tracking page: approved proposal copy | Story **T1** |
| **Reviewer assistant — Yardi match** | On a **second review** case: open **Reviewer assistant** on the case page → ask e.g. *Find the Yardi company for Bean Street Trading Co.* → suggestion card → **Use** fills **Company** / **Brand** re-link pickers only (reviewer still clicks **Re-link** / **Approve**; assistant never submits). Ask *Should I approve?* → it defers to the reviewer | Vitest fixture: `Bean Street Trading Co. (id YC-1001)` |
| **Audit timeline** | Same case page: **Audit timeline** lists intake + case transitions, requests, notifications (routing/tool noise hidden) | Built Day 4; includes post-submit and review events |

Case chat after submit: no intake re-asks; only open requests (re-upload, contacts) drive the dialogue.

### L5 — Governed proactivity

| Capability | How to show it | Notes |
| --- | --- | --- |
| Stalled review → queue email | Submit and leave a case in first review → **/dev** → **+48 h** → open **Needs attention** / queue email for `review_stalled` | Threshold 48 h (`review_stall_hours`) |
| Escalation → region manager | Same case → **+48 h** again → escalation flag to the region manager | 96 h total (`review_escalate_hours`) |
| Unanswered request → drafted reminder | Contacts (or re-upload) still open → advance to **72 h** unanswered → item on **Needs attention** → open case → **Reviewer assistant** drafts the reminder → **Use** fills the text → **Approve and send** → once in applicant **/dev/inbox** | Tier 2 needs approval |
| Quiet hours (Riyadh) | Set clock so a reminder would send at **23:00** → held until **08:00** → **To morning** or advance to send | Policy `22:00–08:00 Asia/Riyadh` |
| `/dev` landing | Personas, **Reset demo**, clock buttons | [Dev landing](#dev-landing) |

---

## Reviewer console cheat sheet (T1 / T2)

1. **http://localhost:5173/review** → pick reviewer (mock sign-in) → open **GEO-…** from the queue or from `review_assigned` / request emails in **/dev/inbox**.
2. Read the **case brief** (deterministic, no model).
3. **First review:** re-upload **or** **Approve first level**.
4. **Lead — second review:** wait for contacts fulfillment (applicant case link) → set Yardi re-link if needed (assistant **Use** optional) → **Approve**.
5. End on **Audit timeline** and applicant **/inquiry/status/…** for the Yardi handover message.

---

## End-of-day check (Day 5)

Use the checklist in [prompts/breadth/day5-yardi-channels-demo.md](../prompts/breadth/day5-yardi-channels-demo.md) (*End-of-day demo check*). Record pass/fail in [STATUS.md](./STATUS.md) §0 when the check is done.
