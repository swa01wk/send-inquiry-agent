# Requirements §7.1 traceability: every workflow step against the POC

**Source:** Cenomi Requirements Document v2.1.7.1, §7.1 Registration and Login (p. 10), §7.1.1 Prospective Tenant – Inquiry to Lead Qualification (pp. 10–15, flow diagram and process flow), §7.1.2 Existing Tenant – Inquiry to Lead Qualification (pp. 15–16, flow diagram and process flow). **Reviewed:** 26 Oct 2026.

Each row is one statement in the requirements. **Where** names the spec section that defines the behaviour; **When** is when the POC first shows it (Built = on `main` today; Day N = the 5-day plan; S1/S2/Closing = the sprints in `docs/DELIVERY-PLAN.md`). Rows marked **Gap → fixed** were missing from the plan before this review and have been added.

## Flow diagrams

Both diagrams (pp. 11 and 16) are swimlane charts embedded at 96 ppi, so their box labels can't be read; the structure can. Ask Cenomi for the source files (Visio or high-resolution PNG) to check the labels.

| Swimlane in the diagram | POC counterpart |
| --- | --- |
| Prospective / existing tenant (Tenant Platform, external page) | Applicant chat on the sign-in page; `/inquiry/verify` and `/inquiry/case` links; tenant portal `/tenant` (existing tenants) |
| Tenant Admin Platform (customer care, RLM / RPLM) | Call-centre console `/callcentre`; reviewer console `/review` |
| Azure AD | `IdentityService` mock (invite, has account, accept link in the dev inbox) |
| Yardi | `YardiService` mock (company search, brands, send lead) |

The visible structure matches the process-flow text below: CR check with a skip path; basic info; email-link and OTP verification; documents; submit; first-level review with a re-upload loop and approve or reject; Azure AD account creation; second-level review with contacts, sales data and re-link; approve or reject; Azure AD accounts for contacts; data to Yardi; end. Nothing in the diagrams' structure is absent from the text.

## §7.1 Registration and Login

| # | Requirement | POC behaviour | Where | When |
| --- | --- | --- | --- | --- |
| R1 | A prospective tenant raises an inquiry via "Send us an inquiry" on the Tenant Platform login page… | Chat agent on the sign-in page | `docs/spec.md` | Built |
| R2 | …or by calling customer care | Call-centre console: the executive raises it with the agent's help | Channels §3.2 | Day 5 — **Gap → fixed** |
| R3 | When RLM-Store / RPLM-Media / RPLM-Specialty approves, the primary contact receives an Azure AD invitation to log in | `approved_first` effect: `IdentityService.invite` | L4 §3.4 | Day 4 |
| R4 | Existing tenants are onboarded when a Super Admin sends an invite from user management | **Out of scope:** user management (§7.12.1), not an inquiry | — | — |
| R5 | Existing tenants may instead raise an inquiry via "Send us Inquiry", and are onboarded on approval | Policy `existing_tenant_policy: allow_inquiry` continues with the tenant record prefilled; default `sign_in` sends them to Tenant Central sign-in and Leasing Opportunities | Channels §3.6; L3 §3.7 | Day 1 flag; Day 5 both paths — **Gap → fixed** (the sign-in redirect led nowhere) |

## §7.1.1 Prospective tenant — a. Inquiry stage

| # | Requirement | POC behaviour | Where | When |
| --- | --- | --- | --- | --- |
| R6 | The inquiry starts from the Tenant Platform (a1) or the Tenant Admin Platform (a2) | Self-service chat (a1); call-centre console (a2) | Channels §1 | Built; Day 5 |
| R7 | a1: for a specific product (Stores / Media / Specialty) | `unit_type` with three product lines; Office removed | Pre-baseline F3 | Day 1 |
| R8 | a1: the platform checks whether the customer exists by CR (optional / skip) | `verify_cr`, `skip_cr` | `docs/spec.md` §3 | Built |
| R9 | a1: a skip option is available; the tenant then fills the form | `skip_cr` after the applicant agrees | `docs/spec.md` §3 | Built |
| R10 | a1: for new prospective tenants, email and mobile (optional) are verified after the basic details | Email by link, mobile by OTP; landline-only by email alone | L3 §3.2–3.3 | Built in chat; Day 2 real link |
| R11 | Landline and mobile: at least one is required | `missing_field:contact` blocker | `docs/spec.md` §2 | Built |
| R12 | On submit, a reference is shown on screen | Success card | `docs/spec.md` §7 | Built |
| R13 | The reference is sent to the verified email / mobile with a tracking link | `submission_email`, `submission_sms` | L3 §3.4 | Day 2 |
| R14 | The tracking link shows the inquiry's status | Tokenised status page; full lifecycle stages; "Waiting for you" | L3 §3.4; L4 §3.8 | Day 2; Day 5 |
| R15 | a2: a customer-care executive creates the inquiry on behalf of the prospective tenant in the Tenant Admin Platform | Call-centre console with the intake agent in assisted mode | Channels §3.2 | Day 5 — **Gap → fixed** |
| R16 | a2: the executive checks the CR (optional / skip) | Same `verify_cr` / `skip_cr` in assisted mode | Channels §3.2 | Day 5 |
| R17 | a2: if the CR exists, the executive tells the tenant to log in and raise the inquiry there | `existing_cr_choice` card: **Ask them to sign in** | Channels §3.2 | Day 5 |
| R18 | a2: if the CR doesn't exist, the executive fills the basic info and submits | Executive fills basic info with the agent; values stored as `staff`; the applicant completes from the link (R26–R31) | Channels §3.1–3.3 | Day 5 |
| R19 | a2: the executive can skip the CR check in either case | `skip_cr` in assisted mode | Channels §3.2 | Day 5 |

### Basic info (table)

| # | Attribute | Rule | POC | When |
| --- | --- | --- | --- | --- |
| R20 | First name, last name | Mandatory | `first_name`, `last_name` | Built |
| R21 | Company (customer name) | Mandatory | `company_name` (from CR when verified) | Built |
| R22 | Brand name (English), Brand name (Arabic) | Mandatory | `brand_name_en`, `brand_name_ar` (Arabic proposed, confirmed) | Built |
| R23 | Sales category | Mandatory | `sales_category` (master data) | Built |
| R24 | Company address | Mandatory | `company_address` | Built |
| R25 | Unit type (Stores / Media / Specialty) | Mandatory | `unit_type` | Built; Office removed Day 1 |
| R25a | Property / mall | Mandatory | `malls` (one) | Built |
| R25b | Mobile with country-code selection; company landline with country code | Mutually exclusive (at least one) | `mobile` / `landline`, E.164; landline 8 or 9 digits after +966 | Built; landline fix Day 1 |
| R25c | Email address | Mandatory | `email` | Built |

### Completing the application from the emailed link

| # | Requirement | POC behaviour | Where | When |
| --- | --- | --- | --- | --- |
| R26 | An email with a link to complete the application is sent to the tenant contact | a1: verification link (the chat already holds the form). a2: `complete_application` link sent by the executive | L3 §3.2; Channels §3.2 | Day 2; Day 5 |
| R27 | The link opens an external page with the inquiry form | `/inquiry/verify` resumes the inquiry in the chat on any device | L3 §3.2; Channels §3.3 | Day 2; Day 5 |
| R28 | The email is auto-verified on clicking the link | Token verification sets `email_verified` | L3 §3.2 | Day 2 |
| R29 | The user can update the basic info and click **Proceed** | a2 and `allow_inquiry`: `basic_info_review` card with Edit and **Proceed**. a1: the applicant entered it in the chat; confirm cards and the review card serve this (POC assumption 1) | Channels §3.3 | Day 5 — **Gap → fixed** |
| R30 | The mobile is verified by OTP, with resend after a set time | Verification card; resend cooldown and cap | L3 §3.3 | Built; cooldown Day 2 |
| R31 | The user uploads the documents and submits | Documents card, review card, consent, Submit | `docs/spec.md` | Built |

### Documents (table)

| # | Attribute | Rule | POC | When |
| --- | --- | --- | --- | --- |
| R32 | CR ID — 10 digits, **disabled**, value from basic info | Optional | Shown read-only on the documents card | Day 1 — **Gap → fixed** (not shown today) |
| R33 | CR document | Optional | `cr_certificate` upload | Built |
| R34 | VAT ID — 15 digits issued by ZATCA | Optional | `vat_number` input on the documents card next to the VAT upload | Day 1 — **Gap → fixed** (validated, but no input today) |
| R35 | VAT document | Optional | `vat_certificate` upload | Built |
| R36 | National ID — 10 digits, of the primary contact | Optional | `national_id_number` input on the documents card | Day 1 — **Gap → fixed** |
| R37 | National ID document | Optional | `national_id` upload | Built |
| R38 | National Address | Optional | `national_address` input on the documents card | Day 1 — **Gap → fixed** |
| R39 | National Address document | Optional | `national_address` upload | Built |
| R40 | Brand Profile | Mandatory | `brand_profile`, required | Built |
| R41 | Company Profile | Mandatory | `company_profile`, required | Built |
| R42 | On submit: alphanumeric reference shown, sent with a tracking link to the verified email / mobile | As R12–R14 | L3 §3.4 | Built; Day 2 |

## §7.1.1 Prospective tenant — b. First-level verification

| # | Requirement | POC behaviour | Where | When |
| --- | --- | --- | --- | --- |
| R43 | Sent to RLM (Stores), RPLM-Media or RPLM-Specialty for first-level verification, by unit type and region | Policy `review_routing`; mall → region from master data | L4 §3.2; M0 §6 `routed` | Day 4 |
| R44 | The reviewer verifies the customer profile and documents | Reviewer console case page with the grounded case brief | L4 §3.3, §3.6 | Day 4 |
| R45 | If a document isn't acceptable, the reviewer requests a re-upload | `reupload_requested(doc_types, remarks)` | M0 §6; L4 §3.3 | Day 4 |
| R46 | Email with a link; the tenant clicks it and re-uploads on an external page | `reupload_request` email with a case link; the case assistant explains and takes the upload; Resubmit | L4 §3.5 | Day 4 |
| R47 | Based on background checks, the reviewer approves or rejects | Console actions; only legal actions shown | L4 §3.3 | Day 4 |
| R48 | Reject: remarks captured, rejection email sent | `rejected(remarks)`; `inquiry_rejected` email; the case assistant explains | L4 §3.4–3.5 | Day 4 |
| R49 | Approve: Azure AD account created for the primary contact | `approved_first` effect: `IdentityService.invite` (skipped if `has_account`) | L4 §3.4; Channels §3.7 | Day 4 |
| R50 | Azure AD sends an invitation with a login / registration link | `azure_ad_invitation` in the dev inbox, with an accept link | L4 §3.2 | Day 4 |
| R51 | On login, limited access; the tenant completes the profile | **Out of scope:** profile completion on the Tenant Platform; the case assistant explains it | L4 §1 | — |
| R52 | On contact creation, a notification asks the primary contact to provide additional tenant contacts | A contacts request opens automatically on first-level approval (`contacts_request` email) | L4 §3.4; M0 §6; Channels D6 | Day 4 — **Gap → fixed** |
| R53 | After first-level verification the tenant is qualified as a **lead** for second-level verification | Status page and case brief label second review "Lead — second review" | L4 §3.8 | Day 5 — **Gap → fixed** (wording) |

## §7.1.1 Prospective tenant — c. Second-level verification

| # | Requirement | POC behaviour | Where | When |
| --- | --- | --- | --- | --- |
| R54 | Second level by RLM (Stores), RPLM-Media or RPLM-Specialty | Same queue | L4 §3.2 | Day 4 |
| R55 | The reviewer can request additional contacts: Authorized Signatory (mandatory), Billing Contact (mandatory), Leasing Manager, Financial Controller, Company Admin (optional) | `contacts_requested`; policy `second_level_contacts`; the case assistant collects all in one bundle and reuses the primary contact | L4 §3.5 | Day 4 |
| R56 | The reviewer can request estimated sales data; the tenant is notified | `sales_data_requested`; `sales_data_request` email | L4 §3.4 | Day 4 |
| R57 | The tenant uploads estimated sales data from the Tenant Platform | `sales_data_upload` card from the case link | L4 §3.5 | Day 4 |
| R58 | The reviewer is notified once it's uploaded | `sales_data_received` to the queue | L4 §3.4 | Day 4 |
| R59 | The reviewer can select a different company and brand; they replace the tenant's choice | `company_relinked`, `brand_relinked`; the brief shows the Yardi ids | L4 §3.3 | Day 5 |
| R60 | Company matches: first company-name search on active Yardi companies | `YardiService.search_companies`; reviewer-assistant suggestions | L4 §3.2, §3.6 | Day 5 |
| R61 | Brands: those associated with the selected company's previous leases and proposals | `YardiService.brands_for_company` | L4 §3.2 | Day 5 |
| R62 | The reviewer approves or rejects the lead in the Tenant Admin Platform | Console actions | L4 §3.3 | Day 4 (reject), Day 5 (approve to Yardi) |
| R63 | Reject: rejection email to the primary contact | `inquiry_rejected` | L4 §3.4 | Day 4 |
| R64 | Approve: Azure AD accounts for additional contacts **who don't have existing accounts**; invitations sent | `IdentityService.has_account` checked, then `invite` | L4 §3.4; Channels §3.7 | Day 5 — **Gap → fixed** (the account check) |
| R65 | Additional contacts register and log in | Accept link in the dev inbox marks the invitation accepted; login itself is out of scope | L4 §3.2 | Day 5 |
| R66 | Acceptance email to the primary contact | `inquiry_accepted` | L4 §3.4 | Day 5 |
| R67 | Customer, brand, contacts, estimated sales data and documents sent to Yardi for the Proposal stage | `YardiService.send_lead(LeadPayload)`, idempotent; `sent_to_yardi` | L4 §3.7 | Day 5 |

## §7.1.2 Existing tenant — inquiry to lead qualification

| # | Requirement | POC behaviour | Where | When |
| --- | --- | --- | --- | --- |
| R68 | The inquiry starts from the Tenant Platform or the Tenant Admin Platform | Tenant portal (a1); call-centre console (a2) | Channels §3.2, §3.5 | Day 5 — **Gap → fixed** |
| R69 | a1: existing tenants raise inquiries through **Leasing Opportunities** on the Tenant Platform | Mock sign-in; `/tenant/opportunities`; Raise inquiry | Channels §3.5 | Day 5 — **Gap → fixed** |
| R70 | a1: all available basic details and documents are prefilled, with the property already selected | `prefill_from_tenant`; mall and unit type from the opportunity | Channels §3.4–3.5 | Day 5 — **Gap → fixed** |
| R71 | a1: existing tenants can verify and edit the basic details and documents | Confirm card; keep or replace documents on file | Channels §3.5 | Day 5 |
| R72 | a1: on submit, reference shown and sent with a tracking link | Same as R12–R14 | L3 §3.4 | Day 5 |
| R73 | a1: existing tenants can view all their submitted inquiries by reference | `/tenant/inquiries` (My inquiries) | Channels §3.5 | Day 5 — **Gap → fixed** |
| R74 | a2: the executive checks the CR | Assisted mode `verify_cr` | Channels §3.2 | Day 5 |
| R75 | a2: if the CR doesn't exist, the executive fills the basic info and submits | As R18 | Channels §3.2 | Day 5 |
| R76 | a2: if the CR exists, the executive tells the contact to log in **or continues to fill the inquiry** | `existing_cr_choice`: sign in, or continue with the tenant record prefilled | Channels §3.2 | Day 5 — **Gap → fixed** |
| R77 | a2: email with a link to complete the application; the external page shows the form with basic info prefilled; email auto-verified; update; Proceed; mobile OTP with resend; upload documents; submit | As R26–R31, with the tenant record prefilled | Channels §3.3 | Day 5 |
| R78 | On submit: reference shown and sent with a tracking link | Same as R12–R14 | L3 §3.4 | Day 5 |
| R79 | b: first-level verification, same as for prospective tenants | Same lifecycle; the brief shows "Existing tenant" | Channels §3.8 | Day 5 |
| R80 | c: second-level verification, same as for prospective tenants | Same lifecycle | L4 | Day 5 |
| R81 | c: existing tenants' contacts are prefilled under the Tenants tab, editable (delete) by the Regional Leasing Manager | Contacts prefilled from the tenant record at second review; console **Remove** | Channels §3.7 | Day 5 — **Gap → fixed** |

## Summary of what this review changed

| Gap | Rows | Fixed in |
| --- | --- | --- |
| Call-centre assisted intake (a2) for prospective and existing tenants, completed by the applicant from a link with Proceed | R2, R15–R19, R26, R29, R74–R77 | Channels §3.1–3.3; Day 5; step 21c |
| Existing tenant journey via Leasing Opportunities, with prefill and My inquiries | R5, R68–R73 | Channels §3.4–3.6; Day 5; step 21c |
| Existing tenants' contacts prefilled at second review; reviewer can remove one | R81 | Channels §3.7; Day 5; step 26 |
| Azure AD invitations only for people without an account | R64 | L4 §3.4; Day 5; step 28 |
| Automatic contacts request on first-level approval | R52 | L4 §3.4; M0 §6; Day 4; step 23 |
| CR ID (read-only), VAT ID, National ID and National Address inputs on the documents card | R32, R34, R36, R38 | Pre-baseline F5; Day 1; step 11c |
| "Lead" wording for second review | R53 | L4 §3.8; Day 5 |
| Guest Service as a second staff channel; roles on Azure AD invitations; funnel view | R82, R84, R88 | Channels §3.2; L4 §3.2–3.3; Days 4–5, S2 |

## Other sections that touch the inquiry

Reviewed alongside §7.1 ([POC lifecycle](../POC-LIFECYCLE.md) §6).

| # | Requirement | Source | POC | When |
| --- | --- | --- | --- | --- |
| R82 | Guest Service (mall service desk) "will be able to add customer inquiries" | Roles table | Second staff role in the assisted channel | Day 5 — **Gap → fixed** |
| R83 | Customer Relations Team: call centre, first contact, passes lead information on | Roles table | Call-centre console (as R15) | Day 5 |
| R84 | Tenant users' details are verified by the leasing team; on approval, Azure AD accounts are created and users assigned their roles | §7.12.1, §7.12.2 | Contacts confirmed in the case; invitations carry the role | Day 4 — **Gap → fixed** (role) |
| R85 | Super Admin: invite, re-invite, block, activate users | §7.12.1 | **Out of scope:** user management | — |
| R86 | Tenant–staff messaging per module (proposal, service request, sales data) | §7.13 | **Out of scope:** not listed for inquiries | — |
| R87 | Existing tenant dashboard: "Lease request: list of inquiries … and detail page"; Leasing Opportunity | §7.14 | My inquiries; Leasing Opportunities | Day 5 |
| R88 | Super Admin dashboard: sales funnel (lease request, lead, proposal, contract), pending approvals, lease requests | §7.14 | Funnel and pending approvals in the reviewer console (Should) | S2 — **Gap → fixed** |
| R89 | Notifications are "information" or "action required"; content and triggers in a linked document | §7.15 | Every template declares its kind; wording synthetic until Cenomi shares the document | Days 2, 4 |
| R90 | Lead verification by "Cenomi Leasing Staff & Regional Leasing / Regional Product Line Managers"; Regional Sales Manager replaced Key Account Manager for inquiries | §6 phases; revision V1.7 | **Open question:** only RLM / RPLM act in the POC, as §7.1.1 b–c describe | — |

**Out of scope, by design:** Super Admin onboarding of existing tenants (R4), profile completion after Azure AD login (R51), real Azure AD login for contacts (R65), the Proposal stage (§7.2), General Inquiries (§7.8.1.1) and document-content checks.
