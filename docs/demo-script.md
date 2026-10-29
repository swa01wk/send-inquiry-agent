# Demo script — Send Inquiry Agent

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

`make demo` today sets `OTP_MOCK_CODE=1234` and `VITE_DEMO=1` only. Day 5 will also turn on dev tools, reviewer console, call centre, tenant portal, and proactivity from one command.

**Personas (URLs today):**

| Persona | URL |
| --- | --- |
| Applicant chat | http://localhost:5173 |
| Dev notification inbox | http://localhost:5173/dev/inbox |
| Reviewer queue / case | http://localhost:5173/review → open a **GEO-…** row |
| Applicant case link | From email in dev inbox → `/inquiry/case?t=…` |
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
| §7.1.1 **a2** — prospective, call centre | Executive at `/callcentre` → assisted chat → link → applicant **Proceed** → OTP → documents → submit | **(after Day 5 backend)** |
| §7.1.2 **a1** — existing tenant, signed in | `/tenant` → Leasing Opportunities → **Raise inquiry** → prefilled confirm → submit → My inquiries | **(after Day 5 backend)** |
| §7.1.2 **a2** — existing tenant, call centre | Executive + existing CR → **Continue for them** or **Ask them to sign in** → link → applicant completes | **(after Day 5 backend)** |
| §7.1 — existing tenant on public page | CR `1010000000` → Sign in; or `allow_inquiry` prefill path | **(after Day 5 backend)** for portal/sign-in UX; **existing account redirect** today: CR `1010000000` → Sign In guidance, no submit |
| §7.1.1 **b** / §7.1.2 **b** — first-level review | Reviewer queue → optional [re-upload (T2)](#l4--re-upload-loop-story-t2) → or **Approve first level** | **Today** (Day 4+) |
| §7.1.1 **c** / §7.1.2 **c** — second-level review | **Lead — second review** → [contacts + Yardi (T1)](#l4--contacts-and-final-approval-to-yardi-story-t1) → optional [reviewer assistant](#l4--reviewer-assistant-yardi-match) on re-link | **Today** (Day 4–5 track) |
| Tracking throughout | Status page: stage, owner role; after Yardi, approved copy for the applicant | **Today** for submit and review stages; **Waiting for you** on status **(after Day 5 backend)** |

**Suggested presenter arc (what you can run today):** self-service submit → open **/review** from the `review_assigned` email (or queue) → first approval **or** re-upload loop → second review with contacts → final approval → applicant tracking shows *Approved — your details are with the leasing team for a proposal* → scroll **Audit timeline** on the case page. Slot call-centre, tenant-portal, and clock beats when Day 5 backend lands.

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
| Stalled review → queue email | Advance clock **+49 h** → case in **Needs attention** | **(after Day 5 backend)** |
| Escalation → region manager | **+48 h** more on stalled case | **(after Day 5 backend)** |
| Unanswered request → drafted reminder | Contacts (or re-upload) open **73 h** → reminder item; reviewer assistant draft → **Approve and send** → applicant dev inbox | **(after Day 5 backend)** |
| Quiet hours (Riyadh) | Reminder due 23:00 held until 08:00 | **(after Day 5 backend)** |
| `/dev` landing | One link per persona, **Reset demo**, **Advance clock** | **(after Day 5 backend)** |

Until then, treat L5 as specified in [l5-governed-proactivity.md](specs/l5-governed-proactivity.md) and rehearse L3–L4 beats above.

---

## Reviewer console cheat sheet (T1 / T2)

1. **http://localhost:5173/review** → pick reviewer (mock sign-in) → open **GEO-…** from the queue or from `review_assigned` / request emails in **/dev/inbox**.
2. Read the **case brief** (deterministic, no model).
3. **First review:** re-upload **or** **Approve first level**.
4. **Lead — second review:** wait for contacts fulfillment (applicant case link) → set Yardi re-link if needed (assistant **Use** optional) → **Approve**.
5. End on **Audit timeline** and applicant **/inquiry/status/…** for the Yardi handover message.

---

## End-of-day check (Day 5)

Use the checklist in [prompts/breadth/day5-yardi-channels-demo.md](../prompts/breadth/day5-yardi-channels-demo.md) (*End-of-day demo check*). Items marked **(after Day 5 backend)** in this script should flip to **Today** as those PRs land; update this file in the same PR when they do.
