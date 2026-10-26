# Intake channels: call-centre assisted intake and existing tenants

**Status:** locked (PRD v1.0, `docs/PRD.md`) · **Requirements:** v2.1.7.1 §7.1, §7.1.1 a2, §7.1.2 · **Depends on:** [L3](l3-reliable-intake.md) §3.2 (signed links and resume), [L4](l4-outcome-assistance.md) §3.1 (case data) · **Cursor step:** `prompts/21c-intake-channels.md` · **Traceability:** [workflows-7-1.md](workflows-7-1.md)

## 1. Why

The other specs cover one way in: a prospective tenant typing in the chat on the sign-in page (§7.1.1 a1). Requirements §7.1 has three more, and the POC needs all of them to show the real process:

| Channel | Requirement | Who starts it | Today |
| --- | --- | --- | --- |
| **Self-service, prospective** | §7.1.1 a1 | Applicant, on the sign-in page | Built |
| **Call-centre assisted** | §7.1.1 a2, §7.1.2 a2 | Customer-care executive in the Tenant Admin Platform, then the applicant completes it from an emailed link | Only a handoff card |
| **Existing tenant, signed in** | §7.1.2 a1 | Signed-in tenant, from Leasing Opportunities | Not built; existing CRs are just told to sign in |
| **Existing tenant, via "Send us an inquiry"** | §7.1 | Existing tenant on the public page | Policy flag `existing_tenant_policy`, default `sign_in` |

All four channels end in the same submitted inquiry and the same review lifecycle (§7.1.1 b–c and §7.1.2 b–c are explicitly the same). The differences are who enters the basic info, how the contact is verified, and what is prefilled.

**Why this is agentic, not just more forms.** The same intake agent serves a second role (the executive) and hands the case across roles and sessions without losing context (framework L4 capability 6, cross-step continuity). For existing tenants it reuses verified context from their tenant record instead of asking again (L3 capability 4, L4 capability 3). In every channel, what someone else entered or what the system prefilled is shown to the applicant and confirmed before submit (golden rule 2).

## 2. Gate

All rows are Must. They're added to the L3 gate run in step 22 and re-checked at the L4 gate.

| # | Criterion | Proved by |
| --- | --- | --- |
| C1 | **Assisted, prospective:** an executive creates an inquiry by talking to the agent; the applicant receives a link; opening it verifies the email; they review the basic info, press Proceed, verify the mobile, upload documents and submit — nothing the executive entered is asked again, and nothing they entered is submitted unconfirmed | Story S9 |
| C2 | **Assisted, existing CR:** the executive is offered both options in §7.1.1 a2 and §7.1.2 a2 — ask the caller to sign in, or continue for them with the tenant record prefilled | Story S10 |
| C3 | **Existing tenant, signed in:** from a Leasing Opportunity, the inquiry opens with company, brand, contact and documents prefilled and the property selected; the tenant confirms or edits, submits, and sees it in My inquiries | Story S11 |
| C4 | **Public page, existing CR:** with `existing_tenant_policy: sign_in`, the applicant is sent to sign in and lands on Leasing Opportunities; with `allow_inquiry`, the inquiry continues with the tenant record prefilled | Story S12, `tests/policy/` |
| C5 | Every channel reaches the same review lifecycle; for an existing tenant, contacts are prefilled from the tenant record and a reviewer can remove one; Azure AD invitations go only to people without an account | Story T10, `tests/lifecycle/` |
| C6 | Access: the executive console needs an executive identity; the tenant portal needs a signed-in tenant; a tenant sees only their own company's inquiries | `tests/access/` |

## 3. Work items

### 3.1 Who entered a value: the `staff` source (Must)

`Source` gains `staff`: a value a customer-care executive entered for the applicant.
- Like `derived` and `verified`, a `staff` value is **unconfirmed** until the applicant confirms it, and `can_submit` blocks on it (golden rule 2, extended).
- The draft summary and cards show a "From the call centre" badge.
- The audit trail records the executive's id as the actor of each `staff` write.

Why a new source instead of reusing `verified`: `verified` means a system of record returned the value (CR lookup, tenant record). An executive typing what a caller said is neither the applicant's own words nor a system fact, and reviewers should be able to tell the difference in the case brief.

### 3.2 Call-centre console (Must; §7.1.1 a2, §7.1.2 a2)

The console stands in for the inquiry-creation screen of the Tenant Admin Platform (assumption D1).

**Access.** `/callcentre`, only when `CALLCENTRE_CONSOLE=true` and `INTEGRATIONS=mock`. A mock sign-in picks a staff member from the reviewer directory, role `customer_care` (the Customer Relations Team, i.e. the call centre) or `guest_service` (the mall service desk, which "will be able to add customer inquiries" per the requirements' roles table); the frontend sends `X-Staff-Id`. Both roles use the same assisted mode; `created_by` records which.

**Starting an inquiry.** **New inquiry** creates an inquiry with `channel: "assisted"` and opens the chat in **assisted mode**:
- The same intake agent, with an assisted prompt: it addresses the executive ("the caller", "they"), asks in the same bundles, and keeps answers short because someone is on the phone.
- Tool allowlist: the intake tools minus `send_verification`, `request_documents` and `show_review`, plus `send_application_link`. Writes from `update_draft` are stored as `source: staff`.
- **CR check, optional and skippable** (§7.1.1 a2). On an existing CR, an `existing_cr_choice` card offers:
  - **Ask them to sign in** — the inquiry is closed as `redirected_to_sign_in`; the agent gives the executive the words to use.
  - **Continue for them** (§7.1.2 a2) — the tenant record is loaded (§3.4) and its values are prefilled as `verified`.
- Handoff cases from the applicant chat (L3 §3.6) are listed in the console; opening one continues the **same** inquiry in assisted mode, with the conversation so far summarised for the executive.

**Sending the link.** When the basic info is complete (every required basic-info field present), the **Send application link** button on a `send_link` card runs the UI action `send_application_link`:
- It sends the `complete_application` email ("action required") to the applicant's email with a link `/inquiry/verify?t=<token>`, token purpose `complete` (L3 §3.2 tokens), valid for `EMAIL_LINK_TTL_HOURS`.
- The inquiry records `awaiting_applicant` (a draft sub-state, not a workflow status) and the executive sees "Link sent to s***@…".
- The executive can resend the link or correct a field and resend; the old link stops working.

### 3.3 Completing the application from the link (Must; §7.1.1 a2, §7.1.2 a2)

Requirements: "On clicking the link: the external page shows the inquiry form; the email is auto-verified; the user can update the basic info and click Proceed; the mobile is verified by OTP with resend after a set time; the user uploads documents and submits."

- Opening `/inquiry/verify?t=` with purpose `complete` sets `email_verified` (the click is the verification), consumes the token's nonce, and resumes the inquiry in a new chat session (L3 §3.2 resume).
- The chat opens with a short greeting naming who started it ("The Cenomi call centre started this inquiry for you") and a **`basic_info_review`** card: every basic-info field with its value and source badge, an **Edit** control per field, and a **Proceed** button.
- **Proceed** (UI action `proceed_basic_info`) confirms every `staff` and `verified` value on the card in one step (`confirmed: true`, audited with the applicant as actor). Edits made on the card are written as `user`.
- The agent then continues as in the self-service flow: mobile OTP if there is a mobile (the verification card, with the resend cooldown), the documents card, the review card and consent, Submit.
- **Nothing is asked again.** The agent only asks about something the applicant changed or that is still missing.

The same card and Proceed step also serve the existing-tenant `allow_inquiry` path (§3.5), where values are prefilled from the tenant record.

### 3.4 Tenant record and existing-tenant prefill (Must; §7.1.2)

**Mock tenant directory** (`data/mock_world/tenants.json`), behind `TenantDirectory.get_by_cr(cr)` and `get_by_id(tenant_id)`:
- company name, address, CR, VAT and National Address;
- brands (English and Arabic names, sales category);
- the primary contact and contacts by role (Authorized Signatory, Billing Contact, …), each with whether they already have a Tenant Central account;
- documents on file (Company Profile, Brand Profile, CR, VAT), as stored file references;
- active leases (mall, product line).

The CR registry's existing number (`1010000000`) maps to a tenant here, so today's "existing CR" scenario gains a record. Add one more tenant with two brands.

**Prefill rule** (one function, `prefill_from_tenant(draft, tenant, brand_id?)`, used by every channel):
- company, address, CR, VAT, National Address, the chosen brand, sales category and the primary contact → `source: verified`, unconfirmed;
- documents on file → attached as references, shown as "On file"; the tenant can keep or replace each;
- with several brands and none chosen, the agent asks which brand (or a new one) in one question.

### 3.5 Existing tenant, signed in (Must; §7.1.2 a1)

Requirements: "Existing tenants raise inquiries through Leasing Opportunities on the Tenant Platform. Basic details and documents are prefilled, with the property already selected. They can verify and edit them. On submission: reference, email or SMS with a tracking link. They can view all submitted inquiries by reference."

**Mock Tenant Central sign-in** (assumption D3): `/tenant` with a picker of tenants from the directory, only when `TENANT_PORTAL=true` and `INTEGRATIONS=mock`. The frontend sends `X-Tenant-Id`; in production this is the Azure AD session.

**Leasing Opportunities** (`/tenant/opportunities`): a list from `data/mock_world/opportunities.json` (mall, product line, unit reference, size range), filterable by city and product line. **Raise inquiry** on one:
- creates an inquiry with `channel: "existing_tenant"` and `tenant_id`;
- prefills it from the tenant record (§3.4);
- sets the mall and unit type from the opportunity as `user`, confirmed — the tenant chose them by clicking; the area range is prefilled as `default`;
- opens the chat in **existing-tenant mode**: the agent greets them by name, shows one confirm card with the prefilled details, asks only for what's missing (the brand if there are several; space or budget if they want to add it), and offers the documents on file.

**Verification.** A signed-in tenant is already verified by Azure AD, so the email-link and OTP steps are skipped: `email_verified` and `mobile_verified` are set from the session, with source recorded as `signed_in` in the audit trail (policy `signed_in_skips_verification: true`, assumption D4).

**Submit and tracking.** As in every channel: review card, consent, Submit, reference shown, submission email and SMS with the tracking link.

**My inquiries** (`/tenant/inquiries`): every inquiry for the tenant's company, newest first, with reference, mall, product line, stage and last change; each opens the tracking page.

### 3.6 Public page with an existing CR (Must; §7.1)

`existing_tenant_policy` (L3 §3.7) now leads somewhere:
- **`sign_in` (default, assumption 3).** The agent explains kindly, and the reply has a **Sign in to Tenant Central** button to `/tenant` (mock sign-in), which lands on Leasing Opportunities. No inquiry is created.
- **`allow_inquiry`** (§7.1: existing tenants "can raise an inquiry via Send us an inquiry"). The inquiry continues with the tenant record prefilled as `verified` and a `basic_info_review` card; the email link and OTP still apply, because the public page has no sign-in.

### 3.7 Lifecycle differences for existing tenants (Must; §7.1.2 c)

- **Contacts prefilled.** When an existing tenant's case enters `second_review`, `tenant_contacts` is filled from the tenant record (`verified`). The applicant's contacts request shows them; the applicant can confirm, edit or add.
- **Reviewers can remove a prefilled contact** (requirement: "editable (Delete) for the Regional Leasing Manager"): console action `remove_contact {role}` → event `contact_removed` (M0 §6), audited.
- **Azure AD invitations only for people without an account** (§7.1.1 c, "who don't have existing accounts"): `IdentityService.has_account(email)` is checked before every invite. An existing tenant's primary contact is never re-invited.

### 3.8 Inquiry channel on the case (Must)

`Inquiry.channel`: `self_service | assisted | existing_tenant`, plus `created_by` (applicant, executive id, or tenant id). The case brief, the queue, the status page and the KPI report show the channel. Reviewers see "Started by the call centre" or "Existing tenant" on the case.

## 4. Stories (Playwright `@scripted`)

| # | Story | Proves |
| --- | --- | --- |
| S9 | An executive signs in to `/callcentre`, starts a new inquiry and types what the caller says (company, brand, mall, contact) in two messages → **Send application link** → the applicant opens the link from `/dev/inbox` in a new browser context → email verified → `basic_info_review` card shows the executive's values with "From the call centre" → edits the brand's Arabic name → **Proceed** → OTP → documents → Submit → submission email | C1 |
| S10 | The executive enters CR `1010000000` → `existing_cr_choice` → **Continue for them** → the tenant record is prefilled → link → applicant completes as in S9. Second run: **Ask them to sign in** closes it | C2 |
| S11 | A tenant signs in at `/tenant`, opens Leasing Opportunities, raises an inquiry for a Specialty unit at a Jeddah mall → prefilled confirm card; picks one of two brands; keeps the documents on file → no email link or OTP → Submit → the inquiry appears in My inquiries with its reference | C3 |
| S12 | On the public chat, CR `1010000000` → Sign in button → `/tenant` → Leasing Opportunities. With `allow_inquiry`, the chat continues with the prefilled `basic_info_review` card | C4 |
| T9 | First-level approval of a prospective tenant's case opens a contacts request automatically; the `contacts_request` email arrives without a reviewer asking (L4 §3.4) | L4, §7.1.1 b |
| T10 | An existing tenant's case reaches second review with contacts prefilled; the reviewer removes the Leasing Manager; final approval invites only the new Billing Contact | C5 |

## 5. Contract changes to fold into `docs/spec.md`

| Area | Change |
| --- | --- |
| Data | `Source.staff`; `Inquiry.channel`, `Inquiry.created_by`, `Inquiry.tenant_id`; `awaiting_applicant` draft sub-state; inquiry outcome `redirected_to_sign_in` |
| Tokens | Purpose `complete` |
| Actions | `send_application_link`, `resend_application_link`, `proceed_basic_info`, `existing_cr_choice {choice: "sign_in" \| "continue"}`, `remove_contact {role}` (console) |
| Cards | `basic_info_review {fields[], can_proceed}`, `send_link {masked_email, sent, can_send}`, `existing_cr_choice {company_name}`, `sign_in_prompt {url}` |
| Notes | `application_link_sent`, `basic_info_confirmed`, `existing_cr_choice <choice>`, `prefilled_from_tenant` |
| Tools | `send_application_link` (assisted mode only) |
| REST | `/api/callcentre/*` (sessions, handoff list); `/api/tenant/*` (`me`, `opportunities`, `inquiries`, `inquiries` POST from an opportunity); all mock-only |
| Services | `TenantDirectory`, `OpportunityCatalogue`; `IdentityService.has_account` |
| Policy | `signed_in_skips_verification`, `existing_tenant_prefill` (fields copied) |
| Config | `CALLCENTRE_CONSOLE`, `TENANT_PORTAL` |
| Frontend routes | `/callcentre`, `/tenant`, `/tenant/opportunities`, `/tenant/inquiries` |
| Templates | `complete_application` (action required) |

## 6. Assumptions

Status **Assumed** until Cenomi confirms.

| # | Assumption |
| --- | --- |
| D1 | The call-centre console stands in for inquiry creation in the Tenant Admin Platform; executives sign in with a mock picker |
| D2 | Values an executive enters are recorded as `staff` and must be confirmed by the applicant (Proceed) before submit |
| D3 | Tenant Central sign-in is mocked with a tenant picker; in production it is the Azure AD session |
| D4 | A signed-in existing tenant skips the email link and OTP; Azure AD has already verified them |
| D5 | When the executive meets an existing CR, both options apply (§7.1.1 a2 says ask them to sign in; §7.1.2 a2 adds continuing for them) |
| D6 | "On contact creation, a notification … to provide additional tenant contacts" (§7.1.1 b) means a contacts request opens automatically when first-level approval creates the Azure AD account |
| D7 | Reviewers may only remove prefilled contacts ("editable (Delete)"); adding or changing them is the tenant's job |
| D8 | Leasing Opportunities is a mock list of available units (mall, product line, size range); its real source isn't specified in §7.1 |
| D9 | Guest Service (mall service desk) raises inquiries exactly as the call centre does; the requirements' roles table says they can add customer inquiries but §7.1 doesn't describe their flow |
