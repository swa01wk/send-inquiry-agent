# L3 — Reliable intake

**Status:** proposed · **Depends on:** [M0 modular core](m0-modular-core.md) · **Cursor steps:** `prompts/17`–`22`

## 1. Why

The framework defines L3 as: the agent understands the task, gathers only what's missing, and completes one bounded transaction with reliable state and recovery. M0 provides the reliable state. This spec makes the prospective-tenant intake (requirements §7.1.1 a1) complete end to end against real systems:
- **Real systems.** CR lookup, email and SMS, inquiry submission and status.
- **Resume.** The user can follow the email link and come back to the inquiry.
- **Status.** After submitting, they get a tracking page.
- **Routing.** Requests the inquiry flow doesn't serve go somewhere sensible.
- **Fallback.** A person can take over when the agent can't finish.

## 2. Exit gate

All rows are Must. These are the framework's L3 exit criteria, made concrete.

| # | Criterion | Proved by |
| --- | --- | --- |
| E1 | Correct routing: intake, status, General Inquiry, existing-tenant and off-topic messages reach the right handler | `tests/routing/test_router.py` (labelled set of ≥ 60 messages, ≥ 95% correct); live eval "Routing" scenarios |
| E2 | Validated inputs: every field in §7.1.1's basic-info and document tables is validated in code against Cenomi's rules (policy file) | `tests/domain/` and `tests/policy/` |
| E3 | Draft continuity: following the emailed link (same or another device) or reopening the tab resumes the same inquiry with nothing lost | `tests/resume/`, manual device test |
| E4 | One unambiguous submission: a single reference, and the user is never told "submitted" without a confirmed reference (M0 G3 still holds against the real adapter's sandbox) | `tests/workflow/`, contract test against the sandbox |
| E5 | Audit evidence for every case, including adapter calls and handoffs | `tests/audit/` |
| E6 | KPIs instrumented and reported (§6) | `scripts/kpi_report.py` on the eval runs |
| E7 | Recovery: an adapter timeout or outage at any step leaves the inquiry resumable, and the user is told what happens next | `tests/gateway/test_failures.py` |

A conversational demo alone does not pass this gate.

## 3. Work items

### 3.1 Real integrations behind the gateway (Must)

Each external system gets an adapter that implements the existing service protocol. Calls go through the M0 tool gateway, which handles timeouts, retries for idempotent calls, error mapping and audit. The mocks stay for development and tests, selected by `INTEGRATIONS=mock|sandbox|live`.

| Adapter | Protocol (exists) | Behaviour required | Open question |
| --- | --- | --- | --- |
| CR lookup | `CrService.verify` | Tells an existing Tenant Central account apart from a new company; returns registered name and address when the registry has them | Q1: which system answers "existing" (Tenant Central accounts, Yardi, or Ministry of Commerce)? |
| Email | `EmailVerificationService.send_link` / `verify` | Sends the verification link (§3.2) and, later, the submission email (§3.4); one live token per inquiry | Q2: sender domain and template approval |
| SMS | `OtpService.send` / `verify` | Sends the OTP to the mobile only; provider-side rate limits respected | Q3: SMS provider and sender ID |
| Submit | `SubmitService.submit` / `lookup` (M0) | Creates the inquiry in the Tenant Admin Platform with `InquiryPayload`; honours the idempotency key | Q4: endpoint, auth and payload |
| Status | `StatusService.get` | Returns stage and next owner from the admin platform | Q4 |
| Storage | `StorageService.save` / `delete` | Puts uploads in Cenomi's document store; virus scan if the store provides one | Q5 |

**Acceptance.**
- One contract test per adapter runs against the sandbox (marked `@pytest.mark.sandbox`) and checks success, a definite rejection, a timeout and a duplicate call.
- Each gateway error kind (`timeout`, `unavailable`, `rejected`, `invalid`) maps to a user-facing outcome. Nothing surfaces as a raw error.

### 3.2 Email-link verification and resume (Must)

This replaces the demo button as the real path. The button stays behind `EMAIL_LINK_DEMO` for demos.

**Following the link:**
1. `send_verification` emails `https://<tenant-central>/inquiry/verify?t=<token>`. The token is a signed, single-purpose JWT (HS256, `RESUME_TOKEN_SECRET`) that names the inquiry, the email it was sent to, and a nonce. It is valid for `EMAIL_LINK_TTL_HOURS` (default 72).
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
- **Tab closed.** A **Continue later** link on the verification card emails a resume link (same token type, purpose `resume`, TTL `RESUME_TTL_DAYS`, default 7). This covers the requirements' "complete the application from the link" path.

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

### 3.4 Submission notifications and the status page (Must)

**Notifying the applicant.** On `submitted`, the system sends the reference with a tracking link to the verified email, and to the verified mobile by SMS when there is one (requirements: "shared … via the verified email/mobile with a tracking link"). Sends go through the gateway and are audited. A failed send does not undo the submission; it is retried and flagged.

**Tracking link.** `https://<tenant-central>/inquiry/status/<reference>?t=<token>`. The signed token (purpose `track`) is required because a guessable reference alone must not expose an applicant's case.

**Status page.**
- A frontend route that calls `GET /api/inquiries/{reference}?t=<token>`.
- It shows the stages (submitted → first review → second review → outcome), the current owner as a role ("Regional Leasing Manager", not a person's name), and the date of the last change.
- The success card's `tracking_url` points here, replacing today's raw JSON link.

**Acceptance.** The page works without a session; a wrong or expired token returns 404 with no data.

### 3.5 Intent routing (Must; framework L3 capability 1)

The M0 supervisor gains a router that runs before the intake agent on each user message.

| Intent | Example | Handled by |
| --- | --- | --- |
| `inquiry_intake` | "We want a kiosk at Riyadh Mall A" | `intake` agent (default) |
| `inquiry_status` | "What's happening with GEO-SPC-123456?" | `status` agent |
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
- `CallCentreService.create_case(InquiryPayload, reason, transcript_summary)` (mock first) creates a case that a customer-care executive can open in the Tenant Admin Platform. This matches the requirements' a2 path: the executive continues the same inquiry rather than starting over.
- The inquiry stays resumable.

**Acceptance.** Each trigger produces the card, one handoff record and an audit event (`tests/handoff/`).

### 3.7 Business rules as policy configuration (Must; anti-pattern "prompt-only policy")

`backend/app/policy/policy.yaml` is loaded and validated at start-up (`PolicyConfig`, Pydantic). It holds:
- product lines (Store, Media, Specialty; Office removed, as requirements §1 lists only three);
- `existing_tenant_policy: sign_in | allow_inquiry` (open question from §7.1 vs §7.1.1 a2);
- `max_malls_per_inquiry: 1`;
- allowed phone countries (`any` or a list);
- verification channels;
- resend limits;
- required documents.

**Who reads it:**
- **Validators, `can_submit`, cards and the guard read the policy.** None of them hard-codes these rules.
- **The prompt doesn't state the rules.** It is rendered with a short "Rules in force" block generated from the policy, so it never contradicts the code.

**Acceptance.** Flipping each policy value in a test changes behaviour without touching code or prompt text (`tests/policy/`).

### 3.8 Cenomi master data (Should)

- **Source.** Malls, cities, product lines and sales categories are loaded from Cenomi's master data (Yardi export or API, Q6) instead of seeded JSON, cached with a daily refresh.
- **Matching.** Mall aliases include Arabic names so `mall_match` works for Arabic messages.
- **Fallback.** If the source is unavailable at start-up, the last good cache is used and the problem is logged.

### 3.9 Evidence for derived values (Should; framework anti-pattern "silent derivation")

- **Evidence on writes.** `update_draft` entries with `source: derived` may carry `evidence` (the user's words the value was derived from, ≤ 80 chars).
- **Shown to the user.** The confirm card shows it ("from: 'specialty coffee kiosk'"), so the user can see why a value was chosen.
- **Kept for reviewers.** It is stored in the audit trail for L4 reviewer briefs.

## 4. Contract changes to fold into `docs/spec.md`

| Area | Change |
| --- | --- |
| REST | `POST /api/verifications/email`, `POST /api/sessions/resume`, `GET /api/inquiries/{reference}?t=` (token required) |
| Actions | `verification_refreshed`, `continue_later` (emails a resume link), `request_handoff` |
| Cards | `verification` gains `resend_available_at`; new `handoff` card `{phone, email, hours, short_ref}`; `success.tracking_url` is the tokenised page URL |
| Notes | `resend_throttled <s>`, `email_verified` via refresh, `handoff_created <reason>` |
| Tools | `update_draft` entry gains optional `evidence` |
| Services | `CallCentreService.create_case`; adapters per §3.1; `NotificationService.send_submission(reference, contact)` |
| Config | `INTEGRATIONS`, `PUBLIC_BASE_URL`, `RESUME_TOKEN_SECRET`, `EMAIL_LINK_TTL_HOURS`, `RESUME_TTL_DAYS`, `RESEND_COOLDOWN_SECONDS`, `MAX_SENDS_PER_HOUR`, `ROUTER_MODEL`, `ROUTER_MIN_CONFIDENCE`, `CALL_CENTRE_*`, `POLICY_PATH` |
| Frontend routes | `/inquiry/verify`, `/inquiry/status/:reference` |

## 5. Sequencing

1. **Policy file (§3.7).** First, because every later item reads it.
2. **Gateway adapters (§3.1).** Mocks first, then the sandbox as access arrives.
3. **Email-link verification and resume (§3.2) and resend limits (§3.3).**
4. **Notifications and status page (§3.4).**
5. **Routing (§3.5) and handoff (§3.6).**
6. **Should items (§3.8, §3.9) and the KPI report**, then the exit-gate run.

## 6. KPIs (framework §11, L3 row)

All of these are computed from audit events by `scripts/kpi_report.py`, per run, and segmented by scenario.

| KPI | Definition | Target for the gate |
| --- | --- | --- |
| Correct first-attempt submissions | `submit_result=success` without a later reviewer correction ÷ submissions | Baseline set at the first sandbox run |
| Unnecessary questions | Questions asking for a value already in the draft or in the user's earlier messages, per inquiry | 0 in scripted scenarios; ≤ 0.2 in live eval |
| User turns to submit | Typed user messages from first message to `submitted` | ≤ 5 in the happy path (scenario C) |
| Duplicate submissions | Inquiries with more than one `submit_attempt` that reached the backend with a new key | 0 |
| Resume success | Resumed inquiries reaching `submitted` ÷ resumed inquiries | Reported; target set with Cenomi |
| Handoff rate | Inquiries with a handoff ÷ inquiries | Reported; reviewed per trigger |
| Routing accuracy | Labelled routing set | ≥ 95% |

## 7. Open questions for Cenomi

- **Q1** Which system decides that a CR already has a Tenant Central account?
- **Q2** Email sender, domain and template approval; is there a transactional email service to use?
- **Q3** SMS provider, sender ID, and countries that must be supported.
- **Q4** Tenant Admin Platform inquiry API (create, status), auth, sandbox access, and the payload shape.
- **Q5** Document store for uploads, and whether it scans files.
- **Q6** Master data source for malls, product lines and sales categories, with Arabic names.
- **Q7** Call-centre contact details and whether customer care can open a case created by the agent.
- **Q8** Confirm the existing-tenant policy (§7.1 vs §7.1.1 a2) and the remaining POC assumptions.
