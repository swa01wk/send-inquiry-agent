# Flow v2 alignment (Prospective Tenant Journey v2 + 10 Nov demo feedback)

**Status:** agreed 12 Nov 2026 · **Delivery:** days F1–F5 (Fri 13 – Wed 18 Nov, Sun 15 off), `prompts/flow-v2/` · **Tracker:** [Flow v2 build tracker](https://claude.ai/artifact/N6P9iLDCZBniCLoNmXng67) (V1–V14, E1–E5, S1–S24, G1–G5) · **Reasoning and decisions:** [aligning to the v2 business flow](https://claude.ai/artifact/6ZRhmxyvBTj8bbCPTcNVUG) (M13–M26, A1–A3) · **Chart and scenario paths:** [Prospective Tenant Journey v2: self-service scenarios](https://claude.ai/artifact/Kkt57H5ZLgu2mBbG7nZRi6) · **Baseline:** `main` at `1645837` (#88), demoed to Muzammil on 10 Nov 2026

This spec makes the agent follow Cenomi's v2 business flowchart step for step and takes in the 10 Nov demo feedback. It changes what the re-demo days (R1–R5, [`demo-feedback.md`](demo-feedback.md)) built. It does not replace the M0, L3, L4 or L5 specs; where it changes one of them, the section here says so, and the PR that builds it updates `docs/spec.md`.

## 1. Why

The client is aligned with the v2 chart ("Prospective Tenant Journey: Inquiry to Lead Qualification"), and Tenant Central's Send Inquiry screens implement it. Our build differs from the chart in nine places (V1–V9), and the 10 Nov demo added five more (V10–V14). The two largest are:

- **Public intake order (V2).** Today we ask company → brand and space → contact → verify → documents. The chart, and the app, ask Company Registration → Unit Type and Sales Category → Basic Info with verification → Property Details → terms → documents → Submit.
- **Second level (V6).** Today the contacts request opens at first approval and one final approval follows. The chart has the RSM / RPLM decide "Approve Lead?" first; only a Yes asks for contacts, and the same reviewer then gives the final "Approve Lead".

**Rule for this round.** Where our build and the chart differ, the chart wins; where the chart leaves a detail open, the app's Send Inquiry screens settle it. Our extra steps stay only where the chart has no step, and each one can be turned off in `policy.yaml` (ADR-V1).

**Naming.** V1–V14 are the changes, E1–E5 the new enhancements, M13–M26 the client decisions, A1–A3 the confirmed assumptions, G1–G5 the gaps found in the code (§8), S1–S24 the self-service scenarios and CC1–CC3 the call-centre stories, F0–F5 the build days, FV1–FV22 this spec's gate rows and ADR-V1–V6 its design rules. Chart step ids (`chk_tp`, `emv`, `approve_lead2`, …) are the ids on the scenario page and in `FlowNode` (§3.1).

**In scope:**

| Change | What | Day |
| --- | --- | --- |
| V1 | Check for Existing Customer: Company Registration with Verify or Skip (Skip confirmed); a registered CR → sign in; otherwise the CR stays on the inquiry | F3 |
| V2 | The app's section order; verification inside Basic Info | F3 |
| V3 | Call centre: Customer CR Existing? → Primary Contact existing? | F4 |
| V4 | Chart names in statuses (Tenant Qualified, Tenant Not Qualified, Lead Approved, Lead Rejected) | F1 |
| V5 | Regional Sales Manager (RLM-Store renamed), Leasing Admin | F1 |
| V6 | Approve Lead? → contacts → Approve Lead | F2 |
| V7 | No per-contact approval; mandatory contacts before Approve Lead | F2 |
| V8 | "Forecasted Sales Data" everywhere | F1 |
| V9 | Reject Lead revokes the Azure AD account made at first approval | F1 |
| V10 | Unit Type right after the CR; Store and Office this round | F3 |
| V11 | No units shown to the tenant; Property Details as in the app with up to 5 malls; the RSM assigns the unit | F2 (console), F3 (intake) |
| V12 | Sales Category from "what do you sell?", never from the brand alone | F3 |
| V13 | A pending inquiry is saved when verification succeeds; re-verify to resume; expires after 2 hours | F3 |
| V14 | Console: no Remove on contacts; no extra confirm on document reject | F1 |
| E1–E5 | §3.12 | F2–F4 |
| FlowNode | Chart step ids in code, `flow_step` audit, dev flow endpoint | F2 (machine), F3 (intake), F4 (call centre) |

**Not in this round:** login requests for a registered CR's person (M18, backlog F4 → I10 → M3); Media and Specialty units and the RPLM branch (A3, off in policy); a console list of pending inquiries (G2, parked 12 Nov); the registration process after an Azure AD invite (out of POC scope on the chart).

## 2. Gate

All rows are Must and due by Wed 18 Nov (F5). A row's test must pass in CI, or for Playwright locally with the result in the PR.

| # | Criterion | Proved by | Day |
| --- | --- | --- | --- |
| FV1 | Every chart step the system reaches is recorded once per visit as a `flow_step` audit entry by code, never by the model; `GET /api/dev/flow/{id}` returns the path for a session id or a reference. | `tests/flow/test_flow_steps.py`; every `flow-v2` Playwright spec (`expectFlowPath`) | F2 (lifecycle), F3 (intake) |
| FV2 | Status labels, emails and case-agent wording use the chart names: Tenant Qualified, Tenant Not Qualified, Lead Approved, Lead Rejected, Leasing Admin, Regional Sales Manager, Forecasted Sales Data. No "Lead — second review", "Regional Leasing Manager" or "estimated sales" text remains in templates, labels or prompts. | `tests/flow/test_labels.py` (grep over templates, labels, prompts); S19, S20, S21 | F1 |
| FV3 | Reject Lead revokes the invitation made at first approval; an account that existed before the inquiry (A1) is never revoked and never invited twice. | `tests/lifecycle/test_revoke.py`; S22, S7 | F1 |
| FV4 | Console: contact rows have no Remove; document Reject applies with its remarks in one step. | Vitest `ReviewCasePage`; S18 | F1 |
| FV5 | Second level follows the chart: `second_review` → `lead_approved` (Approve Lead? Yes) → `approved` (Approve Lead). Reject Lead only from `second_review`. `lead_approved` has no reject. Wrong role or region is refused for each new event. | `tests/lifecycle/test_lead_approval.py`; S22, S23 | F2 |
| FV6 | The contacts request opens on `lead_approved` (not at first approval); `approved` is refused until Authorized Signatory and Billing Contact are given; contacts are not approved one by one. | `tests/lifecycle/test_lead_contacts.py`; S23, S24 | F2 |
| FV7 | The RSM assigns a unit before Approve Lead?; the tenant never sees a unit list; the Yardi payload carries the assigned unit. | `tests/lifecycle/test_unit_assignment.py`; `tests/domain/test_payload.py`; S21, S23 | F2 |
| FV8 | Reminders (E4) fire for a contacts or forecasted-sales request unanswered for `proactive.tenant_reminder_hours`, including in `lead_approved`. | `tests/proactive/test_flow_v2_reminders.py` (dev clock); S21 | F2 |
| FV9 | Company Registration: Verify checks the CR in Tenant Central without sending it to the model. Registered → one-line message and sign-in card, status `redirected`, nothing else asked. Not registered → `cr_number` kept (source user), company name and address asked. Skip needs the confirmation. A 9-digit CR stays at `chk_tp`. | `tests/agent/test_company_registration.py`; S2, S3, S4, S5 | F3 |
| FV10 | The agent asks one section at a time in the app's order; an answer given early is saved; a reply that asks for a later section while an earlier one is open is sent back once. | `tests/agent/test_section_order.py`; eval `flow_v2` S1; S1 | F3 |
| FV11 | Unit Type offers Store and Office only; Sales Category is set from what the business sells and confirmed, never from the brand name alone. | `tests/agent/test_unit_category.py`; eval S10; S10 | F3 |
| FV12 | When verification succeeds, the inquiry becomes `pending` with name, mobile and email. Nothing else moves (no reference, routing or tracking email). A pending inquiry not submitted within `pending_inquiry_ttl_minutes` becomes `abandoned`. | `tests/lifecycle/test_pending_inquiry.py` (dev clock); S9 | F3 |
| FV13 | Resume: "Continue my inquiry" + email → if a pending inquiry exists, a resume link is emailed; opening it re-verifies the email and the chat resumes with the draft. The reply is the same whether or not one exists. | `tests/api/test_pending_resume.py`; S9 | F3 |
| FV14 | Property Details: at least one mall, up to 5; the first mall's region routes the first level; area and rent ranges as today; lease period optional. | `tests/domain/test_validation.py`; `tests/lifecycle/test_routing.py`; S11, S12 | F3 |
| FV15 | Terms and privacy consent come before documents (the `terms` card, a UI action); Submit stays a UI action on the review card and still needs `terms_accepted`. | `tests/api/test_terms_before_documents.py`; S1 | F3 |
| FV16 | Call centre: an existing CR leads to the caller's contact check. An existing contact → "Inform the primary tenant", no inquiry, E5 script and the sign-in link email. A new contact → fresh capture (no Yardi prefill) → application link. | `tests/api/test_callcentre_flow_v2.py`; CC1–CC3 | F4 |
| FV17 | E2: the reviewer assistant suggests whether to ask for forecasted sales data, with a reason from the case facts; it never sends the request itself. | `tests/agent/test_reviewer_fsd_suggestion.py`; eval S21; S21 | F4 |
| FV18 | E3: in `lead_approved` the case agent says which mandatory contacts are missing, asks the signatory question first, and never mentions per-contact approval. | eval S23, S24; S23, S24 | F4 |
| FV19 | All 24 scenarios and CC1–CC3 pass on INT (`@scripted @flow-v2`) on desktop Chrome and mobile WebKit. | `make e2e-int ARGS='--grep @flow-v2'` | F5 |
| FV20 | `@live @flow-v2` passes at least 22 of 24 scenarios, and every CC story, on two runs. | `make e2e-live ARGS='--grep @flow-v2'` | F5 |
| FV21 | `GROUP=flow_v2` passes 3/3 per scenario on two consecutive days on Azure `gpt-5.4-mini`; the existing groups stay within `EVAL_TOLERANCE` of `docs/eval-notes.md`. | `make eval-live GROUP=flow_v2`; `make eval-live` | F5 |
| FV22 | No regression in the R1–R5 stories that this spec doesn't replace (§5.3). | `make e2e-int` | F5 |

## 3. Work items

### 3.1 Chart steps in code: `FlowNode` and `flow_step` (F2, F3, F4)

**Why.** Case statuses don't line up one-for-one with the chart's boxes, so a test can't tell which route a case took. The chart's step ids become ids in code.

**Behaviour.**
- `backend/app/workflow/flow.py`:
  - `class FlowNode(StrEnum)` with the chart ids that code can reach (table below).
  - `IGNORED_NODES = {"A1", "A2", "A3", "B1", "B2", "reg1", "reg2"}`: connectors and out-of-scope boxes. They are never recorded, and the path check skips them.
  - `record_flow_step(runtime, *, inquiry_id, node: FlowNode, actor: str, detail: dict | None = None)` writes audit type `flow_step` `{node, detail}`. It doesn't dedupe; a loop (S6, S18) records the node again. `detail` is allowlisted per node (`reason`, `outcome`, `doc_types`), never contact details or the CR.
- Audit allowlist: `flow_step` → `node`, `detail.reason`, `detail.outcome`, `detail.doc_types`.
- `GET /api/dev/flow/{id}` (`DEV_TOOLS=true` only): `id` is a session id, an inquiry id or a reference. It returns `{inquiry_id, reference, path: [node], steps: [{seq, at, node, actor, detail}]}` for the inquiry and, after submit, its case. 404 `flow_not_found`.
- `POST /api/dev/flow/seed` (`DEV_TOOLS=true`, scripted or mock only): `{stage: "submitted" | "qualified" | "lead_approved", unit_type?: "store" | "office", malls?: [id], applicant?: "existing_account"}` builds a case at that stage **by applying the real events in order** (submit, route, documents approved, `approved_first`, `unit_assigned`, `lead_approved`), so its `flow_step` path is the real one. It returns `{reference, case_id, applicant_case_link, reviewer: {first, final}}`. The after-submit Playwright specs use it (§5).

**Who records each step:**

| Node | Chart box | Recorded by (code only) |
| --- | --- | --- |
| `start` | START | `POST /api/sessions` (self-service) |
| `raise_tp` | Inquiry raised through Tenant Platform | `POST /api/sessions`, after `start` |
| `chk_tp` | Check for Existing Customer | each Verify or Skip on the Company Registration card, and a typed CR (§3.2) |
| `db` | DB (Tenant Central) | the Tenant Central lookup in `check_existing_customer` |
| `exist` | Existing Customer? | the lookup's outcome or a confirmed Skip (`detail.outcome: yes \| no \| skipped`) |
| `display`, `redirect` | Display Message; Redirect to Login Page | a registered CR: the sign-in reply and `sign_in_prompt` card |
| `emv` | Email/Mobile Verification | each `send_verification` that sends (first send and resend) |
| `succ1` | Success? | `verification_complete` (`outcome: yes`) and each failed attempt (`outcome: no`) |
| `complete1` | Complete Inquiry Upload Documents & Submit | `submit_requested` |
| `ref1` | Reference ID with Tracking Link emailed | `submission_email` sent |
| `vla` | Verification Process by Leasing Admin | `routed` |
| `docsok` | Documents OK? | the first document decision after `routed` and after each `documents_resubmitted` (`outcome: yes \| no`) |
| `reup_req`, `reup_mail` | Request Reupload; email with link | `reupload_requested`; its email effect |
| `reup_submit` | Upload Documents & Re-submit | `documents_resubmitted` |
| `approve_pt` | Approve Prospective Tenant? | `approved_first` (`outcome: yes`) or first-level `rejected` (`outcome: no`) |
| `not_q`, `rej_mail` | Tenant Not Qualified; rejection email | first-level `rejected`; its email effect (also after Reject Lead) |
| `ptc_create`, `az1`, `reg_link1` | Primary Tenant Contact Creation; Azure AD; invitation email | `approved_first`: `_invite_primary` (`az1` and `reg_link1` only when an invitation was sent; A1) |
| `qualified` | Tenant Qualified | `approved_first`, after the invite |
| `prod2` | Product = Specialty/Media? | routing to the final reviewer (`outcome: no` for Store and Office) |
| `rsm` / `rplm` | Verification by RSM / RPLM | `unit_assigned` |
| `fsd_q` | Require Forecasted Sales Data? | `sales_data_requested` (`outcome: yes`), or `lead_approved` / second-level `rejected` with no sales-data request (`outcome: no`) |
| `fsd_notify`, `fsd_provide` | Notify; tenant provides | the request email effect; `sales_data_provided` |
| `approve_lead` | Approve Lead? | `lead_approved` (`outcome: yes`) or second-level `rejected` (`outcome: no`) |
| `reject_lead`, `az2` | Reject Lead; revoke | second-level `rejected`; the revoke effect (only when an invitation was revoked) |
| `req_contacts`, `contacts_notify`, `contacts_provide` | Request for Additional Contacts; notify; tenant provides | `contacts_requested`; its email; `contacts_provided` |
| `approve_lead2` | Approve Lead | `approved` |
| `create_all`, `az3`, `reg_link2` | Create User Account for all contacts; Azure AD; invitations | `approved`: `_invite_contacts` (`az3`, `reg_link2` when at least one invitation was sent) |
| `yardi_box`, `end` | Yardi received; END | `sent_to_yardi` |
| `raise_cc`, `chk_cc`, `crx`, `pcx`, `inform`, `exec`, `email_link`, `open_form`, `bic`, `update_bi`, `mob`, `succ2`, `upload_submit`, `ref2` | Call-centre boxes | `api/callcentre.py` and the applicant's application-link session (§3.4) |

### 3.2 Check for Existing Customer: Company Registration (F3; V1, E1; M13, M18, M23)

**Behaviour.**
- New policy value `public_cr_check: verify_or_skip`, the new default. The old values `lookup` and `ask_then_sign_in` stay for tests that set them. Staff channels are unchanged.
- A self-service session opens with the welcome message and a `company_registration` card (replaces `cr_question` under `verify_or_skip`):
  - payload `{prompt, input_placeholder: "10-digit CR number", verify_label: "Verify", skip_label: "Skip", skip_confirm: {prompt: "Are you sure you want to proceed without CR ID?", yes_label: "Yes, continue without it", no_label: "No, I'll enter it"}, state: "open" | "confirm_skip" | "registered" | "not_registered" | "skipped", cr_masked: str | null, error: str | null}`;
  - card id `company_registration`, updated in place.
- **Verify** sends the existing UI action `cr_check {cr_number}`, now allowed on the self-service channel under `verify_or_skip`. The handler `check_existing_customer(session, runtime, cr_number)` in `app/agent/cr_check.py`:
  1. validates (10 digits after `normalise_digits`), else `cr_invalid invalid_cr_number`, state `open` with `error` (S5);
  2. records `chk_tp`, then calls `CrService.verify` through the gateway (Tenant Central; records `db`);
  3. **registered** (`existing`): `cr_status="existing"`; records `exist {outcome: yes}`, `display`, `redirect`; emits the `sign_in_prompt` card (reason `registered_cr`, message "Customer already registered. Please login"); sets `Session.closed = "redirected_to_sign_in"`; inquiry status `redirected`; audit `inquiry_redirected {reason: registered_cr}`. No login request (M18). Nothing else is asked (E1);
  4. **not registered** (`new`): `cr_status="new"`, writes `cr_number` as `user`, confirmed; **does not** write the registry's company name or address (M23: they're asked in Basic Info); records `exist {outcome: no}`;
  5. a service error leaves the card `open` with a retry message: `service_error cr <kind>`.
- **Skip** sends `cr_skip {}` → card state `confirm_skip` (quiet action, no agent turn); `cr_skip {confirmed: true}` → `cr_status="skipped"`, records `chk_tp`, `exist {outcome: skipped}`. Without `confirmed` under `verify_or_skip` the skip never completes. The agent's `skip_cr` tool does the same: without `confirmed=true` it shows the confirm state; with it, only after the user said yes to that question.
- **A CR typed in the chat** (`contains_cr_number`), while `cr_status == "unknown"`: before the graph runs, the chat endpoint replaces it with `[CR number removed]` in the transcript, audit and model input (as today) and runs `check_existing_customer` with it, as if the card was used. The model gets the `[ui_event] cr_checked registered | not_registered` or `cr_invalid` note. A CR typed after the check is scrubbed and not re-checked. (ADR-V4: the CR never reaches the model.)
- Invariant **I8** changes: on the self-service channel no assistant text or card payload contains a CR number in full (the card shows `cr_masked`, e.g. `•••••• 3456`) or a company name or address from a CR lookup.
- The tracker named this "tool `check_existing_customer`". It is a deterministic handler, not a model tool, so the CR stays out of the model (golden rule 1, ADR-V4).

### 3.3 The app's section order, verification and the pending inquiry (F3; V2, V10, V11 intake, V12, V13; M21, M22, M24, M25, A2, A3, G1, G5)

**Sections**, in this order (`app/agent/bundles.py: IntakeSection`):

| # | Section | Fields and steps | Done when |
| --- | --- | --- | --- |
| 1 | `company_registration` | Verify or Skip (§3.2) | `cr_status` is `new` or `skipped` |
| 2 | `unit_and_category` | `unit_type` (Store, Office), `sales_category` | both set and confirmed |
| 3 | `basic_info` | `first_name`, `last_name`, `company_name`, `company_address`, `brand_name_en`, `brand_name_ar`, `email`, `mobile` or `landline` | all set and confirmed |
| 4 | `verification` | email link and, when a mobile was given, the SMS code (G1: unchanged) | `email_verified` and, with a mobile, `mobile_verified` |
| 5 | `property_details` | `malls` (1–5), `lease_period` (optional), `area_min`/`area_max`, `rent_period`, `rent_min`/`rent_max` | `malls` set |
| 6 | `terms` | terms and privacy consent (UI action) | `terms_accepted` |
| 7 | `documents` | Company Profile, Brand Profile (required); the rest optional | required uploaded |
| 8 | `review` | review card → Submit (UI action) | `reference` set |

- `DraftSummary` gains `section` (the first section not done) and `checks.sections: [{key, label, done}]`. `phase` keeps its values for compatibility (`collecting` covers sections 2, 3 and 5).
- `remaining_steps` and `can_submit` blockers follow the section order: `cr`, `unit_and_category`, `basic_info`, `verify_email`, `verify_mobile`, `property_details`, `terms`, `documents`.
- **One section per turn.** The bundle hint (`bundles.still_needed_line`, the "Ask next" line in the prompt) names only the current section's missing items. The agent still saves anything given early (`update_draft` takes any key), and never asks it again.
- **Guard rule 8, `_later_section_ask`** (self-service only): the reply asks for a field of a later section while an earlier one isn't done → a note with the current section and route back to `agent` once. It doesn't fire when the user raised that later field in this turn.
- **Verification sits inside Basic Info.** Once `basic_info` is done, the guard's existing nudge (`_missing_send_verification_note`) makes sure `send_verification` has run, so the `verification` card follows Basic Info before Property Details. Records `emv` and `succ1` (§3.1).
- **Unit Type (V10, M21, A3).** Master data gains `office` (`{id: office, label: Office, label_ar: مكتب, code: OFF}`, via `scripts/generate_master_data.py`). Policy `product_lines: [store, office]`; `media` and `specialty` stay in master data, switched off. The agent offers the enabled types as quick replies. References: `GEO-{STR|MED|SPC|OFF}-{6 digits}` (router regex too).
- **Sales Category (V12).** The agent asks what the business sells, maps the answer to `sales_categories` (G4: the 7 seed categories until the app's list arrives) and shows it on a confirm card. `update_draft` refuses a derived `sales_category` whose `evidence` is only the brand name (error `category_needs_what_you_sell`).
- **Property Details (V11, M25, G5).** Policy `max_malls_per_inquiry: 5`. A city or "any mall" → the mall picker for that city (`min_select: 1`). No unit list is shown to the tenant; the space-bundle unit cards are removed. Routing uses the first mall's region (`route_queue`, unchanged).
- **Terms before documents (FV15).** Policy `terms_before_documents: true`. After Property Details the guard attaches a `terms` card (`{text, privacy_url, accepted}`); its checkbox sends the UI action `accept_terms {terms_accepted: true}` (note `terms_accepted`). The review card then shows "Terms accepted" with Submit. `accept_and_submit` still refuses without `terms_accepted`. With the policy off, today's review-card checkbox is used.
- **Pending inquiry (V13, M24, A2).**
  - New `InquiryStatus.PENDING` and `CaseStatus.PENDING`. `verification_complete` applies `verification_succeeded`: `draft` → `pending` (system); audit `inquiry_pending`.
  - `pending` → `submitting` on `submit_requested`; `submit_failed` returns to the status it came from (`draft` or `pending`).
  - `pending` → `abandoned` on `expired` after policy `pending_inquiry_ttl_minutes: 120` since `verified_at`: the proactive tick and a lazy check on resume both apply it.
  - Nothing else moves at `pending`: no reference, routing, tracking email or reviewer email.
  - **Resume (FV13).** The welcome quick replies gain "Continue my inquiry". The agent asks for the email; the UI action `resume_pending {email}` (the email isn't sent to the model) → if a `pending` inquiry for that verified email exists and hasn't expired, the `resume_link` template is emailed. The same reply follows either way: "If there's an inquiry in progress for that email, we've sent you a link to continue." Opening the link (`POST /api/sessions/resume`) re-verifies the email and the chat resumes with the last 20 messages and the draft. If the mobile was verified, it stays verified. Records `emv` and `succ1` again.
  - No console list this round (G2 parked); tests read it through the dev API.

### 3.4 Call centre: Customer CR Existing? → Primary Contact existing? (F4; V3, E5; M16)

- The executive enters the CR (unchanged; records `raise_cc`, `chk_cc`, `db`, `crx`).
- **Existing CR** → the chat shows a `contact_check` card for the caller's email (card action `contact_check {email}`; built in F4 as a card action, not the `POST …/contact-check` endpoint first planned, to match every other card) → `IdentityService.has_account(email)` (records `pcx`):
  - **exists** → the "Inform the primary tenant to raise inquiry through tenant platform" outcome (records `inform`); no inquiry (status `redirected`, reason `existing_contact`). The `existing_cr_choice` card is removed. E5: the assisted agent gives the executive one or two sentences to say, and an **Email sign-in link** button sends template `sign_in_link` to that email (action `send_sign_in_link`);
  - **new** → fresh capture (M16: no Yardi prefill), as for a new CR.
- **New CR, or an existing CR with a new contact** → the executive captures the public chat's sections without documents (Unit Type and Sales Category, Basic Info, Property Details) and submits (records `exec`) → the application link email (`email_link`) → the applicant opens it (email verified, `open_form`), reviews Basic Info (`bic`; a change → `update_bi`), mobile OTP when a mobile was given (`mob`, `succ2`), terms, documents and Submit (`upload_submit`, `ref2`).
- Landline only (M22): no OTP; the email link is the verification.

### 3.5 Chart names (F1; V4, V5, V8; M17)

- `backend/app/workflow/labels.py` is the one place for display names:
  - `status_label(case)`: `pending` "Pending inquiry", `submitted` "Submitted", `first_review` "With the Leasing Admin", `reupload_requested` "Documents needed", `rejected` at the first level "Tenant Not Qualified", `second_review` "Tenant Qualified", `lead_approved` "Lead Approved", `rejected` at the final level "Lead Rejected", `approved` and `sent_to_yardi` "Approved";
  - `role_label(role)`: `lease_admin` "Leasing Admin", `rlm_store` "Regional Sales Manager", `rplm_media` / `rplm_specialty` "Regional Product Line Manager".
- Role ids, status ids and request kinds keep their names (ADR-V3): `rlm_store` stays the queue id, and request kind `sales_data` stays the id. Only labels change.
- "Forecasted Sales Data" replaces "estimated sales data" in templates, cards, console, case agent and reviewer prompts, and the Yardi payload label. The status page stages become Submitted → With the Leasing Admin → Tenant Qualified → Lead Approved → Outcome.
- `StatusService` owner roles use `role_label`.

### 3.6 Reject Lead revokes (F1; V9; A1)

- `IdentityService.revoke(invitation_id) -> Invitation | None` (mock: marks `revoked_at`, removes the account only if it was created by accepting that invitation). Audit `identity_revoked {invitation_id}`.
- `_invite` (`workflow/effects.py`) already sends no invitation when the email has an account (A1), so `Case.onboarding.invitations` holds only invitations this case created.
- Effect `revoke_primary` on second-level `rejected` (policy `identity.revoke_on_lead_rejection: true`): revokes the case's `primary_contact` invitation, if there is one. An account that existed before the inquiry has no invitation on the case, so it's never touched. A first-level rejection has nothing to revoke.

### 3.7 Second level: Approve Lead? → contacts → Approve Lead (F2; V6, V7, V11 console; M14, M15, M20, M26)

**States and events** (`workflow/machine.py`):

| From | Event | To | Who | Level |
| --- | --- | --- | --- | --- |
| `second_review` | `unit_assigned {mall_id, unit_ref, area_sqm?}` | `second_review` | reviewer | final |
| `second_review` | `sales_data_requested` / `sales_data_provided` | `second_review` | reviewer / user | final |
| `second_review` | `lead_approved {remarks?}` | **`lead_approved`** | reviewer | final |
| `second_review` | `rejected {remarks, reason_category}` (Reject Lead) | `rejected` | reviewer | final |
| `lead_approved` | `contacts_requested` | `lead_approved` | system | — |
| `lead_approved` | `contacts_provided` | `lead_approved` | user | — |
| `lead_approved` | `request_withdrawn` | `lead_approved` | reviewer | final |
| `lead_approved` | `approved {remarks?}` (Approve Lead) | `approved` | reviewer | final |

- Rows removed: `(second_review, contacts_requested | contacts_provided | contact_approved | contact_rejected | contact_removed)` and the per-contact rows; `approved` from `second_review`.
- `lead_approved` blockers: `unit_not_assigned` (policy `lead_approval.require_unit_assigned: true`), `sales_data_pending` (an open sales-data request).
- `approved` blockers: `missing_contact:authorized_signatory`, `missing_contact:billing_contact` (policy `second_level_contacts.required`). Contacts aren't verified or approved one by one (`contacts.approval_required: false`; M15, M26).
- Effects on `lead_approved`: `prefill_tenant_contacts`; `auto_contacts_request` (system `contacts_requested` with every role, the signatory question first); `lead_approved_email` to the applicant. `auto_request_contacts_after_first_approval: false` removes them from `approved_first`.
- Effects on `approved`: unchanged (`invite_contacts`, `accepted_email`, `send_lead`). `send_lead` adds `assigned_unit` to the Yardi payload.
- No reject from `lead_approved`: the chart's final box has no No branch (M26). A reviewer who must stop a lead there uses handoff to operations (out of scope).
- **Console** (`ReviewCasePage`), final reviewer, `second_review`: **Assign unit** (mall from the inquiry, unit reference, area), **Request Forecasted Sales Data**, **Approve Lead?** with **Yes, approve lead** / **No, reject lead**. In `lead_approved`: contacts read-only with mandatory roles marked, missing ones listed, and **Approve Lead** disabled until both are in.
- **Status page and case agent:** `waiting_on_you` lists the missing mandatory contacts in `lead_approved`.
- Migration: none for stored statuses (ADR-V3). Cases already in `second_review` with an open contacts request keep it; `lead_approved` isn't required for them (`legacy_contacts_open`), so the demo seeds still work. `demo_seed.py` is updated to the new flow.

### 3.8 Forecasted sales data and reminders (F2; V8, E4)

- The final reviewer may ask for Forecasted Sales Data before Approve Lead? (`sales_data_requested`), with the same request card and case-agent upload as today.
- **E4.** The proactive tenant-reminder trigger (`proactive.tenant_reminder_hours`, drafted reminder, `reminder_pre_approved`) covers open `contacts` requests in `lead_approved` and open `sales_data` requests in `second_review`. The stall trigger (`review_stall_hours`) counts `lead_approved` as a review stage only while no contacts request is open (the wait is on the tenant, not the reviewer).

### 3.9 Console fixes (F1; V14)

- Contact rows: no **Remove** (the `contact_removed` event stays for API tests, not in the console's actions).
- Document **Reject**: one step with remarks (no second confirmation dialog).

### 3.10 Case agent (F2 tools, F4 prompt; E3)

- `get_case_status` returns the chart stage label, and in `lead_approved` the missing mandatory contacts.
- In `lead_approved`, the case agent asks the signatory question first (`record_signatory_answer`), then the billing contact, then mentions the optional roles once. It never mentions per-contact approval. It explains what's missing before Approve Lead in plain words.
- After Reject Lead: explains the outcome and offers a new inquiry (`after_rejection`), names no reviewer and promises no timeline.

### 3.11 Reviewer assistant (F4; E2)

- New read-only reviewer tool `assess_forecasted_sales_need()` returns facts from the case: unit type, requested area range, rent range, malls count, whether the company is new to Cenomi (no Yardi company), and the matching policy rule.
- Policy `forecasted_sales.suggest_when: {area_min_sqm_at_least: 150, new_company: true}` (any rule true → suggest). These are demo values (assumption A-F1 in `docs/assumptions.md`).
- The assistant words a one-line suggestion with the reason ("Suggest asking for forecasted sales data: a new company asking for 200–300 sqm."). The reviewer presses the request button; the assistant never fires it.

### 3.12 Enhancements

| ID | Enhancement | Section | Switch |
| --- | --- | --- | --- |
| E1 | A registered CR gets one line and the sign-in card; nothing else is asked | §3.2 | `public_cr_check` |
| E2 | Reviewer assistant suggests forecasted sales data with a reason | §3.11 | `forecasted_sales.suggest_when` (empty → no suggestion) |
| E3 | Case agent walks the tenant through the contacts after lead approval | §3.10 | `contacts.ask_signatory` |
| E4 | Reminders for late contacts and forecasted sales data | §3.8 | `proactive.tenant_reminder_hours` |
| E5 | Call centre: words to say and a sign-in link email for an existing contact | §3.4 | `callcentre.offer_sign_in_link: true` |

**Kept from today:** conversational intake with confirmation, type or upload the profiles (F6), per-document approval with expiry (F8, F16), the signatory question (F19), the case agent, the reviewer assistant, the acceptance email, proactive stall flags, handoff, form mode and Arabic. **Switched off:** `auto_request_contacts_after_first_approval: false` (V6), `contacts.approval_required: false` (V7).

## 4. Design rules (ADRs)

ADR-R1 to ADR-R7 from the demo feedback spec still apply.

| ADR | Decision | Where it shows |
| --- | --- | --- |
| V1 | **The chart wins; the app settles details.** Where the build and the chart differ, the chart wins. Where the chart is silent, the app's Send Inquiry screens decide. Extras stay only where the chart has no step, each behind a policy switch. | §1, §3.12 |
| V2 | **Code records the path.** `flow_step` entries are written by code at the event or action that reaches the step, never by the model or the frontend. Tests check the path, not just the end state. | §3.1, FV1 |
| V3 | **Labels change, ids don't.** No stored status, role or request-kind id is renamed; display names come from `workflow/labels.py`. No data migration. | §3.5, §3.7 |
| V4 | **The CR never reaches the model.** The card and a typed CR both go through `check_existing_customer` before the graph; the model sees only the outcome note. | §3.2 |
| V5 | **People decide.** Approve Lead?, Approve Lead, Reject Lead and unit assignment are reviewer actions; the reviewer assistant only suggests (E2). | §3.7, §3.11 |
| V6 | **One scenario catalogue.** `docs/flow-v2/scenarios.json` is the source for the pytest scenario runner, the eval group and the Playwright specs; a scenario changes in one place. | §5 |

## 5. Stories (Playwright)

All in `e2e/tests/flow-v2/`, tagged `@flow-v2` and `@scripted`; those marked live are also `@live`. Each reads its scenario from `docs/flow-v2/scenarios.json` (`e2e/support/scenarios.ts`) and ends with `expectFlowPath(page, scenario)` (`e2e/support/flow.ts`):
- the chart paths of the scenario, minus `IGNORED_NODES`, must each appear in order (as a subsequence) in `GET /api/dev/flow/{id}`'s `path`;
- `not_path` nodes must not appear;
- then the scenario's `expect` block: status and label, draft or case fields, outbox templates, cards.

After-submit specs (S18–S24) start from `POST /api/dev/flow/seed` and use a reviewer browser context (`e2e/pages/console.ts`) alongside the applicant's case chat.

Every spec also runs the existing per-turn checks (`support/plainLanguage.ts`, I1–I8 under `E2E_LIVE=1`), an axe scan at the end, and on mobile no horizontal scroll.

The full matrix (layers, live flags, eval checks) is in [`docs/testing/flow-v2-test-plan.md`](../testing/flow-v2-test-plan.md).

### 5.3 Stories this spec replaces or changes

| Story | Change |
| --- | --- |
| `rd-cr-question` | Replaced by S1–S5 (`verify_or_skip`); kept with `public_cr_check: ask_then_sign_in` set by its script header |
| `rd-contact-approval` | Replaced by S23, S24 (no per-contact approval) |
| `t1-lifecycle-to-yardi`, `a1-approvals`, `l4-reviewer-console`, `demo.spec.ts` | Updated to `lead_approved` and unit assignment |
| `s1-happy-path`, `basics`, `edge-cases`, `mistakes-and-changes`, `confused-users`, `language-and-style` | Scripts re-recorded for the section order; expectations unchanged unless they asserted the old order |
| `a2-call-centre`, `a2-existing-cr` | Updated to the contact check (CC1–CC3) |

## 6. Evaluation

- **Invariant I8 (changed, §3.2).** No CR number in full and no CR-lookup company details in any self-service reply or card.
- **New invariant I9.** In the self-service chat before submit, no reply names a unit, a unit number or a price per unit (V11).
- **Live-eval group `flow_v2`** (`scripts/eval_live.py`, `GROUP=flow_v2`, ×3, pass 3/3): one scenario per S1–S24 and CC1–CC3, built from the catalogue's `eval` block. The checks are listed in the test plan.
- **Goldens.** Re-recorded for every intake script whose order changes (§5.3), with the reason in the PR; new goldens `flow-v2-s01`, `flow-v2-s10`, `flow-v2-s13`.
- **KPI.** `questions_per_section` (questions the agent asked per section) is added to the eval summary, with a target of at most 2 for `unit_and_category` and 3 for `basic_info`.

## 7. Contract changes to fold into `docs/spec.md`

| Day | Change |
| --- | --- |
| F1 | `workflow/labels.py` (`status_label`, `role_label`); status page stage labels; template wording; `IdentityService.revoke`; `Invitation.revoked_at`; effect `revoke_primary`; audit `identity_revoked`; policy `identity.revoke_on_lead_rejection` |
| F2 | `CaseStatus.LEAD_APPROVED`; events `unit_assigned`, `lead_approved`; `approved` and `lead_approved` blockers; `Case.assigned_unit`; Yardi payload `assigned_unit`; effects on `lead_approved`; policy `lead_approval`, `auto_request_contacts_after_first_approval: false`, `contacts.approval_required: false`; `FlowNode`, audit `flow_step`, `GET /api/dev/flow/{id}`, `POST /api/dev/flow/seed` |
| F3 | Policy `public_cr_check: verify_or_skip`, `product_lines: [store, office]`, `review_routing.office`, `max_malls_per_inquiry: 5`, `pending_inquiry_ttl_minutes`, `terms_before_documents`; master unit `office` (`OFF`); card `company_registration`; actions `cr_check` and `cr_skip {confirmed}` on self-service, `accept_terms`, `resume_pending`; card `terms`; `DraftSummary.section`, `checks.sections`; blocker order; `InquiryStatus.PENDING`, `CaseStatus.PENDING`, events `verification_succeeded`, `expired` from `pending`; audit `inquiry_pending`; `update_draft` error `category_needs_what_you_sell`; guard rules 8 and the verification due-card; invariants I8, I9; reference regex with `OFF` |
| F4 | card `contact_check` + action `contact_check {email}` (instead of `POST /api/callcentre/inquiries/{id}/contact-check`); card `inform_tenant`; action `send_sign_in_link`; template `sign_in_link`; `existing_cr_choice` card removed; reviewer tool `assess_forecasted_sales_need`; policy `forecasted_sales`, `callcentre.offer_sign_in_link` |

## 8. Decisions, assumptions and gaps

All client decisions are answered (M13–M26, 11–12 Nov) and A1–A3 are confirmed; see the [tracker](https://claude.ai/artifact/N6P9iLDCZBniCLoNmXng67) §3 and `docs/assumptions.md` ("Flow v2 assumptions"). Gaps found in the code, decided 12 Nov:

| Gap | Decision |
| --- | --- |
| G1: how the email is verified | Keep today's email link plus mobile OTP; landline-only → email link alone |
| G2: who sees a pending inquiry | Parked: saved, no console list this round |
| G3: Office isn't in master data | Add `office` (`OFF`), routed to the RSM. This reverses the pre-baseline "no Office product line" ([pre-baseline-fixes.md](pre-baseline-fixes.md)), on the client's answer M21 |
| G4: the app's Sales Category list | Keep the 7 seed categories until Cenomi shares the list (data change only) |
| G5: malls per inquiry | Up to 5 |

## 9. Out of scope

- Login requests for a registered CR's person (M18).
- Media and Specialty units and the RPLM branch (A3; switched off, code paths kept and tested with the policy on).
- The registration process after an Azure AD invitation (chart: out of POC scope).
- A console list of pending inquiries (G2).
- Real Tenant Central, Azure AD and Yardi integrations (mocked, golden rule 5).
