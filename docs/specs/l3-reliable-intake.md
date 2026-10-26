# L3 — Reliable intake

**Status:** proposed · **Depends on:** [M0 modular core](m0-modular-core.md) · **Cursor steps:** `prompts/17`–`22` (with `21b`)

**Revised 26 Oct 2026: mock-first.** Every external Cenomi system is simulated (§3.1), so no step waits for Cenomi access. The open questions became working assumptions (§7). New items: a dev inbox for the simulated email and SMS (§3.4), generated master data (§3.8), Arabic in the safety nets (§3.10), follow-on inquiries that reuse verified details (§3.11), a duplicate check before submit (§3.12) and acceptance stories (§3.13).

## 1. Why

The framework defines L3 as: the agent understands the task, gathers only what's missing, and completes one bounded transaction with reliable state and recovery. M0 provides the reliable state. This spec makes the prospective-tenant intake (requirements §7.1.1 a1) complete end to end:
- **Simulated Cenomi.** CR registry, email, SMS, the Tenant Admin Platform inbox and status behave like real systems, including failures, behind the same interfaces the real adapters will use.
- **Resume.** The user can follow the email link and come back to the inquiry, on any device.
- **Status.** After submitting, they get the reference and a private tracking page.
- **Routing.** Requests the inquiry flow doesn't serve go somewhere sensible.
- **Fallback.** A person can take over when the agent can't finish.
- **Context reuse.** A second inquiry (another mall) reuses what was already verified, and a duplicate is caught before it is sent.

The real adapters are not part of this spec's gate. When Cenomi grants access, each one replaces its mock by configuration and must pass the same contract tests (§3.1).

## 2. Exit gate

All rows are Must. These are the framework's L3 exit criteria, made concrete.

| # | Criterion | Proved by |
| --- | --- | --- |
| E1 | Correct routing: intake, status, General Inquiry, existing-tenant, handoff and off-topic messages reach the right handler | `tests/routing/test_router.py` (labelled set of ≥ 60 messages, ≥ 95% correct); live eval "Routing" scenarios |
| E2 | Validated inputs: every field in §7.1.1's basic-info and document tables is validated in code against the policy file | `tests/domain/` and `tests/policy/` |
| E3 | Draft continuity: following the emailed link (same or another device) or reopening the tab resumes the same inquiry with nothing lost | `tests/resume/`, Playwright `@scripted` resume story (§3.13), manual device test |
| E4 | One unambiguous submission: a single reference, and the user is never told "submitted" without a confirmed reference (M0 G3 holds against the simulated admin platform with faults on) | `tests/workflow/`, `tests/contract/` |
| E5 | Audit evidence for every case, including simulated adapter calls, notifications and handoffs | `tests/audit/` |
| E6 | KPIs instrumented and reported (§6) | `scripts/kpi_report.py` on the eval runs |
| E7 | Recovery: a timeout or outage at any step leaves the inquiry resumable, and the user is told what happens next | `tests/gateway/test_failures.py` with mock faults (§3.1) |
| E8 | Arabic: routing, doubt detection, contact and mall capture work for Arabic and mixed messages, including Arabic-Indic digits | `tests/arabic/`, the Arabic golden transcript, live eval "Arabic" scenario |
| E9 | The acceptance stories in §3.13 pass as Playwright `@scripted` tests | `make e2e` |

A conversational demo alone does not pass this gate.

## 3. Work items

### 3.1 Simulated Cenomi behind the gateway (Must)

Each external system is a mock that behaves like the real one: it keeps state, returns realistic outcomes, and fails on demand. Calls go through the M0 tool gateway, which handles timeouts, retries for idempotent calls, error mapping and audit. Tools and actions can't tell a mock from a real adapter.

**Selection.** `INTEGRATIONS=mock|sandbox|live` selects implementations in `services/container.py`. `mock` is the default and the only tier this spec builds. `sandbox` and `live` are stub modules under `app/integrations/` that raise `NotImplementedError` with the open question that blocks them (§7).

**Mocks and their scenario data** (`backend/app/data/mock_world/`, loaded at start-up):

| Service | Protocol | Simulated behaviour | Scenario data |
| --- | --- | --- | --- |
| CR registry | `CrService.verify` | New with details, new without details, existing account; Arabic company names where present | `cr_registry.json`. Keeps today's numbers (`1010123456`, `1010222222`, `1010000000`) so the goldens don't move. Adds `1010333333` (new, Arabic name) and fault numbers `1010999991` (timeout) and `1010999992` (unavailable) |
| Email | `EmailVerificationService.send_link` / `verify` | Delivers the verification link to the outbox (§3.4); one live token per inquiry | — |
| SMS | `OtpService.send` / `verify` | Delivers the code to the outbox; mobile only; cooldown and cap (§3.3) | `OTP_MOCK_CODE` stays the code |
| Tenant Admin Platform: inbox | `SubmitService.submit` / `lookup` | Accepts `InquiryPayload` with an idempotency key; a repeat key returns the same reference | — |
| Tenant Admin Platform: status | `StatusService.get` | Returns stage, next owner as a role, open requests and last change, from the inquiry's workflow status | — |
| Notifications | `NotificationService.send(template, to, context)` | Renders a template and delivers it to the outbox | `app/notifications/templates/*.txt` (`string.Template`, no new dependency) |
| Call centre | `CallCentreService.create_case` | Stores the case; visible in the dev inbox as a "call-centre case" | — |
| Storage | `StorageService.save` / `delete` | Today's local-disk mock | — |

**Fault injection.** Mocks raise real failure types so the gateway maps them like it would a real outage:
- `MOCK_FAULTS` (env), a comma list of `service:kind[:count]`, for example `submit:timeout:1,otp:unavailable`. `kind` is `timeout`, `unavailable` or `rejected`; `count` defaults to every call.
- In `AGENT_MODE=scripted` only, `POST /api/sessions` accepts an `X-Mock-Faults` header with the same syntax, scoped to that session. It is ignored otherwise, like `X-Test-Scenario`.
- `MOCK_LATENCY_MS` (default 0) adds a delay to every mock call, so demos show the typing indicator and timeouts can be exercised.

**Contract tests.** `tests/contract/` has one module per service, run against the mock now (`-m contract`) and against a sandbox later (`-m sandbox`, skipped until one exists). Each checks success, a definite rejection, a timeout and a duplicate call. A real adapter is accepted only when it passes the same module.

**Acceptance.**
- Each gateway error kind (`timeout`, `unavailable`, `rejected`, `invalid`) maps to a user-facing outcome. Nothing surfaces as a raw error.
- Every fault in the table above has a test that ends with a resumable inquiry and a clear next step (E7).

### 3.2 Email-link verification and resume (Must)

This replaces the demo button as the real path. The button stays behind `EMAIL_LINK_DEMO` for quick demos; the full path goes through the dev inbox (§3.4).

**Following the link:**
1. `send_verification` sends `https://<tenant-central>/inquiry/verify?t=<token>` (built from `PUBLIC_BASE_URL`). The token is a signed, single-purpose JWT (HS256, `RESUME_TOKEN_SECRET`) that names the inquiry, the email it was sent to, and a nonce. It is valid for `EMAIL_LINK_TTL_HOURS` (default 72).
2. The link opens a lightweight page in the frontend, `/inquiry/verify`. The page calls `POST /api/verifications/email {token}`, which:
   - validates the token;
   - checks the email still matches the draft;
   - consumes the nonce;
   - sets `email_verified`;
   - audits the result.
3. The page shows "Email verified" and a **Continue your inquiry** button.
4. The button calls `POST /api/sessions/resume {token}`. That opens a new browser session on the same inquiry and returns the last 20 messages, the live cards and the draft summary. The chat then renders exactly where the user left off, on any device.

**Coming back to the chat:**
- **Original tab still open.** While its verification card is pending, it polls `GET /api/sessions/{id}/draft` every 5 s for up to 15 minutes. When it sees `checks.email_verified`, it sends a `verification_refreshed` action. That runs a turn with `[ui_event] email_verified …`, so the agent moves on without the user typing.
- **Tab closed.** A **Continue later** link on the verification card sends a resume link (same token type, purpose `resume`, TTL `RESUME_TTL_DAYS`, default 7). This covers the requirements' "complete the application from the link" path.

**Frontend routes.** The app gains client-side routes (`/`, `/inquiry/verify`, `/inquiry/status/:reference`, `/dev/inbox`; L4 adds `/inquiry/case` and `/review/*`). Use `react-router-dom` v6. Why a new dependency: L4's reviewer console needs nested routes with parameters, and a hand-rolled router would grow into one.

**Acceptance.**
- A token works once.
- A token for an email that has since changed is rejected.
- An expired token offers to resend.
- Resuming on a second device shows the same draft and cards (`tests/resume/`).

### 3.3 Resend limits (Must; requirements "resend after a predefined time")

- **Cooldown.** Email links and OTPs can be resent only after `RESEND_COOLDOWN_SECONDS` (default 60).
- **Cap.** At most `MAX_SENDS_PER_HOUR` per channel per inquiry (default 5).
- **Card.** The verification card gains `resend_available_at`, and its Resend buttons show a countdown.
- **Over the limit.** The action note is `resend_throttled <seconds>`, and the agent explains when to try again.

### 3.4 Submission notifications, status page and dev inbox (Must)

**Notifying the applicant.** On `submitted`, the system sends the reference with a tracking link to the verified email, and to the verified mobile by SMS when there is one (requirements: "shared … via the verified email/mobile with a tracking link"). Sends go through the gateway and are audited. A failed send does not undo the submission; it is retried and flagged.

**Templates.** Every message the system sends has a template under `app/notifications/templates/`, named by its trigger: `email_verification_link`, `sms_otp`, `resume_link`, `submission_email`, `submission_sms`. L4 adds the post-submit templates. Requirements §7.15 splits notifications into "information" and "action required"; each template declares its kind.

**Tracking link.** `https://<tenant-central>/inquiry/status/<reference>?t=<token>`. The signed token (purpose `track`) is required because a guessable reference alone must not expose an applicant's case.

**Status page.**
- A frontend route that calls `GET /api/inquiries/{reference}?t=<token>`.
- It shows the stages (submitted → first review → second review → outcome), the current owner as a role ("Regional Leasing Manager", not a person's name), anything waiting on the applicant, and the date of the last change.
- The success card's `tracking_url` points here, replacing today's raw JSON link.

**Dev inbox (dev and demo only).** The outbox is how a demo shows the business flow without real email or SMS.
- `MockNotificationService` stores every message: `{id, inquiry_id, channel, to, template, kind, subject, body, links, created_at}`.
- `GET /api/dev/outbox?to=` lists messages, newest first. `DELETE /api/dev/outbox` clears it.
- Frontend `/dev/inbox` shows the messages per recipient, with clickable links (verification, resume, tracking).
- Both exist only when `DEV_TOOLS=true`. The app refuses to start with `DEV_TOOLS=true` unless `INTEGRATIONS=mock`. The outbox may hold the mock OTP; it is never written to logs (golden rule 8 is about logs, and the outbox is dev-only data).

**Acceptance.** The status page works without a session; a wrong or expired token returns 404 with no data; every message in the happy path appears in the outbox exactly once.

### 3.5 Intent routing (Must; framework L3 capability 1)

The M0 supervisor gains a router that runs before the intake agent on each user message.

| Intent | Example | Handled by |
| --- | --- | --- |
| `inquiry_intake` | "We want a kiosk at Riyadh Mall A" | `intake` agent (default) |
| `inquiry_status` | "What's happening with GEO-SPC-123456?" | `status` agent (L4: `case` agent) |
| `general_inquiry` | "I have a question about signage rules" | `redirect` agent (no write tools): explain that General Inquiries are raised after sign-in (§7.8.1.1); offer to continue a leasing inquiry |
| `existing_tenant_new_space` | "We already lease two stores, want a third" | `redirect` agent: point to Sign In → Leasing Opportunities (§7.1.2); follows the existing-tenant policy flag (§3.7) |
| `human_help` | "Can I talk to someone?" | Handoff (§3.6) |
| `off_topic` | "Write me a poem" | Kind redirect, as the v1 prompt does |

How the router decides:
1. **Rules first.** A reference pattern, an explicit request for a person, or an existing CR match decides immediately.
2. **Small structured-output classifier otherwise.** It gets the message and the inquiry's status, and returns `{intent, confidence}` (a separate model call; `ROUTER_MODEL` can be a smaller model).
3. **Fallbacks.** Below `ROUTER_MIN_CONFIDENCE` (default 0.6), or mid-intake, the router defaults to `inquiry_intake`. The intake agent already handles small talk and FAQs well, so a mid-flow question doesn't leave intake.

**Acceptance.** E1, using the labelled set in `tests/routing/fixtures.jsonl`. It includes Arabic and mixed-language messages.

### 3.6 Human handoff (Must; framework L3 capability 10)

**Triggers.** Any one of these hands the case to a person:
- the `human_help` intent;
- the guard's second failed retry in one turn;
- three gateway failures on the same step;
- submit stuck in `submitting` after reconciliation;
- the user saying something is wrong twice after corrections.

**What happens:**
- A new `handoff` card shows the call-centre phone number, email and hours (from config) and the inquiry's short reference.
- `CallCentreService.create_case(InquiryPayload, reason, transcript_summary)` creates a case that a customer-care executive can open in the Tenant Admin Platform. This matches the requirements' a2 path: the executive continues the same inquiry rather than starting over. In the POC the case shows in the dev inbox.
- The inquiry stays resumable.

**Acceptance.** Each trigger produces the card, one handoff record and an audit event (`tests/handoff/`).

### 3.7 Business rules as policy configuration (Must; anti-pattern "prompt-only policy")

`backend/app/policy/policy.yaml` is loaded and validated at start-up (`PolicyConfig`, Pydantic). It holds:
- product lines (Store, Media, Specialty; Office was removed by the pre-baseline fixes);
- `existing_tenant_policy: sign_in | allow_inquiry` (assumption 3, §7);
- `max_malls_per_inquiry: 1`;
- allowed phone countries (`any` or a list);
- verification channels;
- resend limits;
- required documents;
- `duplicate_policy: warn | block` (§3.12, default `warn`);
- `follow_on_reuse_hours` (§3.11, default 24).

L4 adds the review routing table and the second-level contact rules to the same file.

**Who reads it:**
- **Validators, `can_submit`, cards and the guard read the policy.** None of them hard-codes these rules.
- **The prompt doesn't state the rules.** It is rendered with a short "Rules in force" block generated from the policy, so it never contradicts the code.

**Acceptance.** Flipping each policy value in a test changes behaviour without touching code or prompt text (`tests/policy/`).

### 3.8 Generated master data (Must)

The seed data today has 9 "Mall A"-style malls in 3 cities, English only. Mocks need data rich enough to exercise routing, Arabic and review queues.

- **Generator.** `backend/scripts/generate_master_data.py` (fixed random seed, so output is stable) writes `backend/app/data/master_data.json`:
  - regions (Central, Western, Eastern) with cities;
  - about 20 malls with English and Arabic names, aliases (Arabic included), city and region;
  - product lines Store, Media, Specialty with codes;
  - sales categories with Arabic labels;
  - lease and rent periods.
- **Names.** Clearly synthetic ("Riyadh Mall A", «رياض مول أ»), unless Cenomi supplies its list (assumption 6). Today's ids stay so goldens and e2e scripts don't move.
- **Interface.** `MasterDataSource` with `SeedMasterDataSource` (the JSON) and a stub `CenomiMasterDataSource`, cached with a daily refresh and a last-good fallback.
- **Matching.** `mall_match` uses the Arabic names and aliases.

### 3.9 Evidence for derived values (Should; framework anti-pattern "silent derivation")

- **Evidence on writes.** `update_draft` entries with `source: derived` may carry `evidence` (the user's words the value was derived from, ≤ 80 chars).
- **Shown to the user.** The confirm card shows it ("from: 'specialty coffee kiosk'"), so the user can see why a value was chosen.
- **Kept for reviewers.** It is stored in the audit trail for the L4 case brief.

### 3.10 Arabic in the safety nets (Must)

The prompt replies in Arabic, but the deterministic checks around it are English-only today.

- **Digits.** `domain/validation.py` normalises Arabic-Indic (`٠١٢٣٤٥٦٧٨٩`) and Eastern Arabic-Indic (`۰…۹`) digits before every numeric rule: CR, phone numbers, VAT, National ID, area and rent. Contact detection in `agent/contact_infer.py` does the same.
- **Doubt.** `agent/confirm_policy.py` recognises Arabic doubt phrases (for example «مو متأكد», «لست متأكدا», «يمكن غلط») and covers every derived field, not only unit type and sales category.
- **Capture.** The guard's capture heuristics (`message_likely_has_inquiry_data`, the bulk and contact checks) recognise Arabic business words (كشك، متجر، مطعم، مقهى، مول) and Arabic names.
- **Malls.** Arabic names and aliases from §3.8.
- **Tests.** `tests/arabic/` for each rule; an Arabic happy-path golden transcript added to the parity suite; an "Arabic" live-eval scenario.

### 3.11 Follow-on inquiries: reuse verified details (Should; framework L3 capability 4)

One mall per inquiry (assumption 2) means a brand that wants two malls raises two inquiries. The second one shouldn't repeat anything.

**In the same chat.** After a submission, when the user asks for another mall ("can we also do Mall B?"), the agent calls `start_follow_on(mall_id?)`:
- A new inquiry is created with `follow_on_of = <reference>` and the session moves to it. The UI shows a divider "New inquiry".
- Company, brand, unit type, sales category and contact are copied as `source=verified`, unconfirmed, in one confirm card titled "Same details as <reference>". One click confirms them all; any can be edited.
- Email and mobile stay verified if they are unchanged and the first inquiry was verified within `follow_on_reuse_hours`.
- Company Profile and Brand Profile are copied by reference (same stored files).
- The agent asks only for the new mall (if not given) and any space details. Target: submitted in two typed messages.

**From the tracking page.** A **Start another inquiry** button on the status page (the `track` token proves access) opens the chat with the same follow-on prefill.

**Privacy.** Reuse needs proof of access to the earlier inquiry (same session, or its token). Nothing is looked up by CR, email or company alone.

### 3.12 Duplicate check before submit (Should)

**When.** On `verification_complete`, the system checks for an open inquiry (any status except `draft`, `abandoned` and `rejected`) with the same mall and either the same CR number or the same normalised company and brand names (`InquiryIndex.find_open`).

**What the agent says.**
- **Same verified email:** it's theirs. Note `duplicate_own reference=<ref>`. The agent offers the status of the existing inquiry and asks whether they still want a second one.
- **Different contact:** note `duplicate_other`. The agent says an inquiry for this brand at this mall is already being reviewed and they can still continue. It never reveals the other inquiry's reference or contact.

**Policy.** `duplicate_policy: warn` lets them continue and records `possible_duplicate_of` on the new case for the reviewer (L4 case brief). `block` adds a `duplicate_open` blocker to `can_submit`.

### 3.13 Acceptance stories (Must; gate E9)

Each story is a Playwright `@scripted` test with its scripts in `backend/tests/e2e_scripts/`, and a matching live-eval scenario where noted.

| # | Story | Proves |
| --- | --- | --- |
| S1 | A user front-loads company, brand, mall and contact in one message, verifies by the emailed link (opened from the dev inbox), uploads the two required documents, and submits. The submission email with the tracking link is in the inbox; the status page shows the inquiry as submitted and waiting for review (L4 adds the review stages) | Whole a1 flow, notifications, tracking (E3, E4) |
| S2 | The user closes the tab at the verification card, opens the resume link from the inbox in a new context (a second device), and finishes | Resume (E3) |
| S3 | Submit times out (`X-Mock-Faults: submit:timeout:1`); the agent says it is confirming, never claims success; reconciliation finds the reference | Recovery, no premature success (E4, E7) |
| S4 | An Arabic-speaking user gives a phone number in Arabic-Indic digits and doubts the sales category; it stays unconfirmed until they choose | Arabic safety nets (E8) |
| S5 | After submitting for Mall A, the user asks for Mall B and submits the second inquiry in two typed messages | Follow-on reuse (§3.11) |
| S6 | The same brand and mall are submitted twice by two contacts; the second sees the duplicate warning and continues | Duplicate check (§3.12) |
| S7 | "Can I speak to someone?" mid-intake → handoff card; the call-centre case is in the dev inbox; the inquiry resumes afterwards | Handoff (§3.6) |
| S8 | "We already lease two stores" → existing-tenant redirect; "how long does review take?" mid-flow stays in intake | Routing (E1) |

## 4. Contract changes to fold into `docs/spec.md`

| Area | Change |
| --- | --- |
| REST | `POST /api/verifications/email`, `POST /api/sessions/resume`, `GET /api/inquiries/{reference}?t=` (token required); dev only: `GET`/`DELETE /api/dev/outbox` |
| Actions | `verification_refreshed`, `continue_later` (sends a resume link), `request_handoff`, `start_follow_on {mall_id?}` |
| Cards | `verification` gains `resend_available_at`; new `handoff` card `{phone, email, hours, short_ref}`; `success.tracking_url` is the tokenised page URL; `confirm_fields` gains optional `evidence` per field and a `title` for follow-on prefill |
| Notes | `resend_throttled <s>`, `email_verified` via refresh, `handoff_created <reason>`, `duplicate_own reference=<ref>`, `duplicate_other`, `follow_on_started from=<ref>` |
| Tools | `update_draft` entry gains optional `evidence`; new `start_follow_on` |
| Services | `NotificationService.send(template, to, context)`; `CallCentreService.create_case`; `InquiryIndex.find_open`; mock scenario data under `data/mock_world/` |
| Data | `Inquiry.follow_on_of`, `Inquiry.possible_duplicate_of` |
| Config | `INTEGRATIONS`, `DEV_TOOLS`, `MOCK_FAULTS`, `MOCK_LATENCY_MS`, `PUBLIC_BASE_URL`, `RESUME_TOKEN_SECRET`, `EMAIL_LINK_TTL_HOURS`, `RESUME_TTL_DAYS`, `RESEND_COOLDOWN_SECONDS`, `MAX_SENDS_PER_HOUR`, `ROUTER_MODEL`, `ROUTER_MIN_CONFIDENCE`, `CALL_CENTRE_*`, `POLICY_PATH` |
| Test hooks | `X-Mock-Faults` header on `POST /api/sessions` (scripted mode only) |
| Frontend routes | `/inquiry/verify`, `/inquiry/status/:reference`, `/dev/inbox` (dev only) |

## 5. Sequencing

1. **Policy file and generated master data (§3.7, §3.8)** — step 17. Every later item reads them.
2. **Simulated Cenomi (§3.1)** and the notification outbox (§3.4 templates and dev inbox) — step 18.
3. **Email-link verification, resume and resend limits (§3.2, §3.3)** — step 19.
4. **Submission notifications and status page (§3.4)** — step 20.
5. **Routing and handoff (§3.5, §3.6)** — step 21.
6. **Arabic, follow-on and duplicate check (§3.10–§3.12)** — step 21b.
7. **Evidence (§3.9), acceptance stories (§3.13), the KPI report**, then the exit-gate run — step 22.

## 6. KPIs (framework §11, L3 row)

All of these are computed from audit events by `scripts/kpi_report.py`, per run, and segmented by scenario and language.

| KPI | Definition | Target for the gate |
| --- | --- | --- |
| Correct first-attempt submissions | `submit_result=success` without a later reviewer correction ÷ submissions | Baseline set at the first gate run |
| Unnecessary questions | Questions asking for a value already in the draft or in the user's earlier messages, per inquiry | 0 in scripted scenarios; ≤ 0.2 in live eval |
| User turns to submit | Typed user messages from first message to `submitted` | ≤ 5 in the happy path (scenario C); ≤ 2 for a follow-on |
| Duplicate submissions | Inquiries with more than one `submit_attempt` that reached the backend with a new key | 0 |
| Resume success | Resumed inquiries reaching `submitted` ÷ resumed inquiries | Reported |
| Handoff rate | Inquiries with a handoff ÷ inquiries | Reported; reviewed per trigger |
| Routing accuracy | Labelled routing set | ≥ 95% |
| Duplicate warnings | `duplicate_own` and `duplicate_other` per 100 submissions | Reported |

## 7. Assumptions in place of the open questions

Each question still goes to Cenomi, but nothing waits for the answer: the mock implements the assumption, and changing it later is an adapter or policy change. Status stays **Assumed** until Cenomi confirms.

| # | Question for Cenomi | Assumption the mock implements |
| --- | --- | --- |
| Q1 | Which system decides that a CR already has a Tenant Central account? | The CR registry mock answers "existing" from `cr_registry.json` |
| Q2 | Email sender, domain and template approval; transactional email service? | Templates in the repo; delivered to the dev inbox |
| Q3 | SMS provider, sender ID, countries | OTP to any mobile with a country code; delivered to the dev inbox |
| Q4 | Tenant Admin Platform inquiry API (create, status), auth, sandbox, payload | `InquiryPayload` as defined in M0 §7.2; the mock admin platform stores it |
| Q5 | Document store, virus scanning | Local disk; no scanning |
| Q6 | Master data source with Arabic names | Generated synthetic data (§3.8) |
| Q7 | Call-centre contact details; can customer care open agent-created cases? | Contact details from config; cases appear in the dev inbox |
| Q8 | Existing-tenant policy (§7.1 vs §7.1.1 a2) and the POC assumptions | `existing_tenant_policy: sign_in` |
