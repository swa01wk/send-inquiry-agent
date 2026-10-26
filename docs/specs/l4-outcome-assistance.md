# L4 — Outcome assistance (inquiry to Yardi-ready lead)

**Status:** proposed · **Depends on:** [L3 reliable intake](l3-reliable-intake.md) · **Cursor steps:** `prompts/23`–`28`

## 1. Why

Intake is the first of three stages in requirements §7.1.1. After submission, a Regional Leasing Manager (Store) or Regional Product Line Manager (Media or Specialty) reviews the inquiry twice, can send it back for re-uploads, contacts or sales data, and finally approves it into a lead that goes to Yardi for the Proposal stage. Today the agent stops at the reference number.

The framework defines L4 as owning the **outcome**: the agent stays with the case across handoffs, for the applicant and the reviewers, and reduces rework. "Own" means assist and track. Reviewers keep every decision: approve, reject, request, re-link. The agent prepares, explains and collects; deterministic code moves the case.

Everything external stays simulated (as in L3 §3.1): the Tenant Admin Platform is stood in for by a reviewer console, and Azure AD and Yardi are mocks.

### Business flow covered

| Requirement (§7.1.1) | Actor | The system does (code) | The agent does |
| --- | --- | --- | --- |
| b. Inquiry sent to RLM-Store / RPLM-Media / RPLM-Specialty by unit type and region | System | Routes the case to a review queue from the policy routing table | — |
| b. First-level verification of profile and documents | Reviewer | Shows the case in the queue | **Reviewer assistant:** case brief with every value's source, documents checklist, duplicates, suggested next step |
| b. Re-upload requested, email with link to an external page | Reviewer → applicant | Transition, `reupload_request` email with a case link | **Case assistant:** explains which document and why (from the remarks), shows an upload card for only those documents, resubmits |
| b. Rejected with remarks, rejection email | Reviewer → applicant | Transition, `inquiry_rejected` email | **Case assistant:** explains the remarks plainly and what the applicant can do next; never reopens |
| b. Approved: Azure AD account and invitation; limited access; profile completion | Reviewer → applicant | Transition, identity invitation (mocked, skipped if the contact already has an account), `first_level_approved` email | **Case assistant:** explains the invitation and what comes next |
| b. On contact creation, a notification asks for additional tenant contacts | System → applicant | A contacts request opens automatically with first-level approval; `contacts_request` email | **Case assistant:** collects the contacts (as in c) |
| b. After first level, the tenant is qualified as a lead | System | Second review is shown as "Lead — second review" | Uses the same wording |
| c. Additional contacts requested (Authorized Signatory and Billing Contact required; Leasing Manager, Financial Controller, Company Admin optional) | Reviewer → applicant | Open request, `contacts_request` email | **Case assistant:** collects all contacts in one bundle; reuses the primary contact when it's the same person |
| c. Estimated sales data requested; reviewer notified when uploaded | Reviewer → applicant → reviewer | Open request, `sales_data_request` email, `sales_data_received` to the reviewer | **Case assistant:** explains the request and takes the upload |
| c. Re-link company (first company-name search on active Yardi companies) and brand (brands from that company's leases and proposals) | Reviewer | Transition with the chosen Yardi ids | **Reviewer assistant:** suggests matches with the reason for each |
| c. Existing tenants (§7.1.2 c): contacts prefilled under the Tenants tab, editable (delete) by the reviewer | System, reviewer | Contacts prefilled from the tenant record; console **Remove** (`contact_removed`) | **Case assistant:** shows the prefilled contacts for confirmation |
| c. Approve or reject the lead; AD accounts for additional contacts; acceptance email; data sent to Yardi | Reviewer → system | Transition, invitations, `inquiry_accepted` email, `send_lead` to Yardi | **Case assistant:** explains the outcome and the Proposal stage next |
| Tracking link: track the status at any time | Applicant | Status page with stage, owner role and anything waiting on them | **Case assistant:** answers "where is my inquiry?" with stage, owner and what's pending |

Every intake channel — self-service, call-centre assisted and existing tenant ([intake channels](intake-channels.md)) — reaches this same lifecycle (requirements §7.1.2 b–c: "same as prospective tenant flow").

Out of scope: profile completion on the Tenant Platform after Azure AD sign-in (explained, not built), the Proposal stage (§7.2) and document-content checks (not in the POC; see `docs/assumptions.md`, Documents).

## 2. Exit gate

All rows are Must. These are the framework's L4 exit criteria, made concrete.

| # | Criterion | Proved by |
| --- | --- | --- |
| X1 | Lifecycle: every path in §1 runs end to end on the simulated back office — approve → approve → Yardi; reject at either level; the re-upload loop; contacts and sales-data requests; re-link | `tests/lifecycle/`, stories T1–T5 |
| X2 | Reviewer authority: no agent tool can change a case's status or send a decision. Only console actions by a reviewer assigned to the case's queue can, and the state machine checks the actor | `tests/lifecycle/test_authority.py`, story T6 |
| X3 | No re-asking: answering a request never re-collects intake facts, and the primary contact is reused when the applicant says it's them | Scripted stories; KPI "facts re-asked after submit" = 0 in scripted runs |
| X4 | Grounded briefs: every line of the case brief comes from a field (with its source), a document record or an audit event; the reviewer assistant answers only from the brief and its tools | `tests/case_brief/`, live eval "Reviewer" scenario |
| X5 | Notifications: every message in §3.4 is sent once, to the right party, with a working link | `tests/lifecycle/test_effects.py` against the outbox |
| X6 | Access: case links are signed and scoped; the review API needs a reviewer identity; nothing is reachable with a reference alone | `tests/access/` |
| X7 | Audit: every decision, request, applicant response, side effect and assistant suggestion is in the trail with its actor | `tests/audit/` extended |
| X8 | The stories in §3.10 pass as Playwright `@scripted` tests, with separate applicant and reviewer browser contexts | `make e2e` |
| X9 | KPIs instrumented and reported (§3.11) | `scripts/kpi_report.py` |

## 3. Work items

### 3.1 Case data (Must)

`Inquiry` (M0 §5.1) gains the post-submit case data. All of it is written by the state machine's effects or by deterministic UI actions, never by the LLM.

```python
class ReviewQueue(BaseModel):
    product_line: Literal["store", "media", "specialty"]
    region: str                       # from the mall's region in master data
    role: Literal["rlm_store", "rplm_media", "rplm_specialty"]

class CaseRequest(BaseModel):
    id: str
    kind: Literal["reupload", "contacts", "sales_data"]
    status: Literal["open", "fulfilled", "withdrawn"]
    doc_types: list[DocType] = []     # reupload only
    remarks: str                      # the reviewer's words, shown to the applicant
    requested_by: str                 # reviewer id
    requested_at: datetime
    closed_at: datetime | None = None

class Decision(BaseModel):
    level: Literal["first", "second"]
    outcome: Literal["approved", "rejected"]
    remarks: str | None = None        # required for a rejection
    reason_category: str | None = None  # from policy.rejection_categories; feeds L5 insights
    by: str
    at: datetime

class TenantContact(BaseModel):
    role: Literal["authorized_signatory", "billing_contact", "leasing_manager",
                  "financial_controller", "company_admin"]
    first_name: FieldValue
    last_name: FieldValue
    email: FieldValue
    mobile: FieldValue
    landline: FieldValue
    same_as_primary: bool = False

# New fields on Inquiry
review_queue: ReviewQueue | None
requests: list[CaseRequest]
decisions: list[Decision]
tenant_contacts: list[TenantContact]
sales_data: DocumentRef | None
document_history: list[DocumentRef]          # replaced versions, for the brief
onboarding: Onboarding | None                # invitation id, invited_at, accepted_at
yardi: YardiLink | None                      # company_id, brand_id, lead_ref, sent_at
```

`TenantContact` fields reuse `FieldValue`, so `source` and `confirmed` work as for intake (golden rule 2), and validation reuses `domain/validation.py`.

### 3.2 Simulated back office (Must)

| Mock | Interface | Behaviour | Data |
| --- | --- | --- | --- |
| Review routing | policy `review_routing` | `(product_line, region) → role`; Store → `rlm_store`, Media → `rplm_media`, Specialty → `rplm_specialty` | `policy.yaml` |
| Reviewer directory | `ReviewerDirectory` | Reviewers with role and regions; at least one per queue, plus a region manager per role for L5 escalation | `data/mock_world/reviewers.json` |
| Azure AD | `IdentityService.invite(contact, role) / status(invitation_id) / has_account(email)`; the invitation records the tenant role it assigns (requirements §7.12.2: "on approval, these users are automatically assigned to their respective roles") | Sends an `azure_ad_invitation` message with an "Accept invitation" link to the outbox; following it marks the invitation accepted | — |
| Yardi | `YardiService.search_companies(name) / brands_for_company(company_id) / send_lead(payload, idempotency_key)` | Company search by the first word of the company name, active companies only (§7.1.1 c); brands from that company's previous leases and proposals; `send_lead` returns a lead reference, idempotent | `data/mock_world/yardi.json`: includes the companies the CR mock returns (Bean Street Trading Co., Fawaz Alhokair Trading Co.) and near-matches, each with brands |

All go through the gateway and honour `MOCK_FAULTS` (L3 §3.1).

### 3.3 Reviewer console (Must)

The console stands in for the Tenant Admin Platform so the lifecycle can be run and demoed. In production the admin platform is the system of record; the console stays a dev tool, and the case data arrives through a `CaseEventSource` adapter instead (not built in the POC).

**Access.** Only when `REVIEWER_CONSOLE=true` and `INTEGRATIONS=mock`. A mock sign-in picks a reviewer from the directory; the frontend then sends `X-Reviewer-Id` on every `/api/review/*` call. The backend resolves the reviewer and passes them to the state machine as the actor.

**Pages** (`/review/*`, same design tokens as the chat):
- **Queue:** cases in the reviewer's queues, with stage, what it's waiting on (reviewer or applicant), age and a possible-duplicate flag.
- **Case:** the case brief (§3.6), fields with source badges and evidence, documents (open the file; no content processing), the request history, the audit timeline, and an actions panel showing only the actions legal in the current status.
- **Assistant panel:** the reviewer assistant (§3.6) beside the case.
- **Funnel (Should):** counts for the reviewer's queues and overall — lease requests (submitted, in first review), leads (second review), approved, sent to Yardi, rejected — and pending approvals per queue, for a chosen period. It mirrors the Super Admin dashboard's "Sales Funnel" and "Pending Approvals" widgets (§7.14), computed from case states.

**Actions.** Each maps 1:1 to a state-machine event (M0 §6): request re-upload (pick documents, remarks), reject (remarks, reason category), approve first level, request contacts, request sales data, withdraw a request, re-link company or brand (with suggestions), approve, reject.

**API.**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/review/me` | The signed-in mock reviewer |
| GET | `/api/review/cases?queue=&waiting_on=` | Queue list |
| GET | `/api/review/cases/{inquiry_id}` | Case detail with brief, documents, requests, timeline |
| GET | `/api/review/cases/{inquiry_id}/documents/{file_id}` | Download a document |
| POST | `/api/review/cases/{inquiry_id}/actions` | `{action, payload}` → transition and effects |
| POST | `/api/review/cases/{inquiry_id}/assistant` | Reviewer-assistant chat (SSE, same event types as the applicant chat) |

### 3.4 Side effects and notifications (Must)

Effects run after the transition is persisted, from a small outbox table (`case_effects`), each keyed by `(inquiry_id, event_seq, effect)` so a retry never sends twice. A failed effect is retried through the gateway and audited; it never rolls back the transition.

| Event | Effects | Template (kind) → recipient |
| --- | --- | --- |
| `submitted` | Route to a queue (`routed`) | `review_assigned` (information) → queue reviewers |
| `reupload_requested` | — | `reupload_request` (action required) → primary contact, with a case link |
| `documents_resubmitted` | — | `reupload_received` (information) → queue reviewers |
| `rejected` (either level) | — | `inquiry_rejected` (information) → primary contact, with the remarks |
| `approved_first` | `IdentityService.invite(primary contact)` unless `has_account`; then, when policy `auto_request_contacts_after_first_approval` is on (default), a system `contacts_requested` | `azure_ad_invitation` → primary contact (if invited); `first_level_approved` (information) → primary contact; `contacts_request` (action required) → primary contact |
| `contacts_requested` | — | `contacts_request` (action required) → primary contact, with a case link |
| `contacts_provided` | — | `contacts_received` (information) → queue reviewers |
| `sales_data_requested` | — | `sales_data_request` (action required) → primary contact, with a case link |
| `sales_data_provided` | — | `sales_data_received` (information) → queue reviewers (requirement: reviewer notified on upload) |
| `request_withdrawn` | — | `request_withdrawn` (information) → primary contact |
| `approved` | Invite each additional contact for whom `IdentityService.has_account` is false and no invitation exists; then `send_lead` to Yardi | `azure_ad_invitation` → each new contact; `inquiry_accepted` (information) → primary contact |
| `sent_to_yardi` | — | — (the status page shows "Proposal stage next") |
| `yardi_failed` | Retry with backoff; after `YARDI_MAX_ATTEMPTS`, flag the case for operations in the console | — |

### 3.5 Case assistant (Must)

The `case` agent replaces M0's `status` agent for any inquiry that isn't a draft. The supervisor routes to it by inquiry status, as in M0 §9.

**Entry.** Every link the applicant receives after submission opens the same case:
- the tracking link (`track` token, L3 §3.4);
- action links in `reupload_request`, `contacts_request` and `sales_data_request` (`case` token, scoped to the request id, valid until the request closes).

Both open `/inquiry/case?t=…`, which resumes a session in case mode (L3 §3.2 resume) and starts with a `case_status` card: stage, owner role, last change, and any open requests with the reviewer's remarks.

**What it does:**
- **Outcome framing.** Says where the case is, who acts next (as a role), and what the applicant can do now. Never promises an outcome or a timeline.
- **Re-upload.** Explains which documents and why, quoting the reviewer's remarks in the card and paraphrasing them in the reply. `request_reupload_documents` shows a `document_upload` card in re-upload mode with only the requested types. The **Resubmit** button sends the UI action `resubmit_documents`, which checks every requested document was replaced after the request, then fires `documents_resubmitted`.
- **Contacts.** One bundle question: "Who are your Authorized Signatory and Billing Contact? Name, email and phone for each; you can add a Leasing Manager, Financial Controller or Company Admin too." `update_contacts` writes `TenantContact` entries. "That's me" copies the primary contact as `verified`, unconfirmed. `show_contacts_review` shows a `contacts` card; the **Send contacts** button (`submit_contacts`) validates required roles from the policy and fires `contacts_provided`.
- **Sales data.** Explains the request; `request_sales_data_upload` shows a `sales_data_upload` card (one file, the usual extension and size checks); **Send** (`submit_sales_data`) fires `sales_data_provided`.
- **Rejection.** Explains the remarks in plain words and what the applicant may do next (from `policy.after_rejection`, for example raising a new inquiry). Never reopens the case or argues the decision.
- **Approval.** First level: explains the Azure AD invitation and that more contacts or sales data may be requested. Final: explains that the details go to the leasing team's system for a proposal.

**Tools (allowlist):** `get_case_status`, `request_reupload_documents`, `update_contacts`, `confirm_fields`, `show_contacts_review`, `request_sales_data_upload`, `search_faq`, `suggest_replies`, `start_follow_on` (L3 §3.11), `request_handoff`.

**Rules in code:**
- No tool changes the case status; only the three UI actions above (applicant) and console actions (reviewer) do.
- The guard adds: no claim that something was resubmitted, approved, accepted or sent to Yardi without the matching `[ui_event]`; no reviewer names (roles only).

### 3.6 Reviewer assistant (Must)

**Case brief** (`domain/case_brief.py`, deterministic). Built only from the case record and its audit trail:
- applicant, company and brand; product line, mall and region; CR status (verified, new without details, or skipped);
- each field with its source — typed, derived (with the evidence) or verified — and whether the applicant confirmed it;
- verification checks; documents with their history (requested, replaced);
- possible duplicate and follow-on relations (L3 §3.11, §3.12);
- open and closed requests, decisions, and how long the case has waited at each stage;
- a deterministic checklist of what's missing for the next decision (for example "Billing Contact missing: request contacts before final approval", from the policy).

**Agent** (`reviewer`), in the console's assistant panel. It answers questions about the case and prepares work:

| Tool | Does |
| --- | --- |
| `get_case_brief` | The brief above |
| `search_yardi_companies` | Matches by the first company-name word, active companies only, each with the reason it matched |
| `list_company_brands` | Brands from the chosen company's leases and proposals |
| `find_related_inquiries` | Other inquiries with the same CR or company (references and status only) |
| `draft_reviewer_note(kind, points)` | Draft text for re-upload remarks, rejection remarks or a contacts request, put into the action form for the reviewer to edit |

It never decides. Asked to approve or reject, it says the decision is the reviewer's and points to the button. Every suggestion is audited as `assistant_suggestion`, with whether the reviewer used it.

### 3.7 Approval to Yardi (Must)

On `approved`: invitations for additional contacts, the `inquiry_accepted` email, then `YardiService.send_lead(LeadPayload, idempotency_key=f"lead:{inquiry_id}")`.
- `LeadPayload`: customer (relinked Yardi company id when set), brand (relinked id when set), tenant contacts, sales-data reference and document references.
- Success → `sent_to_yardi` with the lead reference. Failure → `yardi_failed`, retried; nobody is told it was sent until Yardi acknowledges.

### 3.8 Status page (Must)

The L3 status page shows the full lifecycle: Submitted → First review → Lead — second review → Outcome (Approved and sent to the leasing team, or Not approved). The requirements call a case that passed first-level verification a **lead** (§7.1.1 b), so the page, the case assistant and the console use that word. "Waiting for you" lists open requests, each with a button that opens the case link.

### 3.9 Access (Must)

- **Applicant:** `track` (read the case, start a follow-on) and `case` (scoped to one request) tokens, both signed (L3 §3.2). In production, after first-level approval the applicant signs in to Tenant Central with Azure AD; the POC uses signed links throughout (assumption A2).
- **Reviewer:** the mock identity header, only with `REVIEWER_CONSOLE=true` and `INTEGRATIONS=mock`. The state machine, not the console, checks the reviewer's queue.
- **Never** by reference alone, and never another applicant's data in a reply.

### 3.10 Acceptance stories (Must; gate X8)

Playwright `@scripted`, with an applicant context and a reviewer context in the same test; scripts in `backend/tests/e2e_scripts/`.

| # | Story | Proves |
| --- | --- | --- |
| T1 | Submit a Store inquiry at a Central mall → it appears in the RLM-Store Central queue → approve first level → the Azure AD invitation and the automatic contacts request are in the dev inbox; the invitation is accepted → the applicant opens the contacts link and says "I'm the authorized signatory; billing is Omar Saleh, omar@…, +966 5…" → contacts sent → approve → acceptance email; status page shows approved and sent | The full a1 → b → c path (X1, X3, X5) |
| T2 | Reviewer requests a Brand Profile re-upload with remarks → the applicant opens the link; the agent explains the reason; the card offers only Brand Profile → upload → Resubmit → the case is back in first review; no intake question asked | Re-upload loop, no re-asking (X1, X3) |
| T3 | Reviewer rejects at first level with remarks → the applicant opens the tracking link; the agent explains and doesn't reopen | Rejection framing |
| T4 | Reviewer requests sales data → the applicant uploads → the reviewer gets `sales_data_received` | Sales-data loop |
| T5 | The reviewer asks the assistant for Yardi matches for "Bean Street Trading Co." → picks a company and brand → re-link recorded; the brief shows the Yardi ids | Re-link (X4) |
| T6 | The applicant asks the agent to approve or hurry the review; the reviewer asks the assistant to approve. Both decline and point to the right place; nothing changes | Authority (X2) |
| T7 | Yardi is down (`yardi:unavailable:2`) after approval → `yardi_failed` twice → sent on the third attempt; the status page never shows "sent" before that | Recovery |
| T8 | A Media inquiry at an Eastern mall lands in the RPLM-Media Eastern queue and is not visible to an RLM-Store Central reviewer | Routing and access (X6) |

### 3.11 KPIs (framework §11, L4 row)

Computed by `scripts/kpi_report.py` from audit events and console timestamps.

| KPI | Definition |
| --- | --- |
| Re-upload requests per inquiry | `reupload_requested` events ÷ submitted inquiries |
| Reviewer handling time | Case opened in the console → decision, per level |
| Facts re-asked after submit | Case-agent questions asking for a value already on the case (target 0 in scripted runs) |
| Applicant response time | Request opened → fulfilled, per kind |
| Turns to fulfil a request | Typed applicant messages per fulfilled request |
| Assistant suggestion use | Suggestions used ÷ suggestions made |

## 4. Contract changes to fold into `docs/spec.md`

| Area | Change |
| --- | --- |
| Data | `Inquiry` case fields (§3.1); `TenantContact`, `CaseRequest`, `Decision` |
| Workflow | L4 rows of M0 §6 become reachable |
| Agents | `case` replaces `status`; new `reviewer` agent |
| Tools | Case: `get_case_status`, `request_reupload_documents`, `update_contacts`, `show_contacts_review`, `request_sales_data_upload`. Reviewer: `get_case_brief`, `search_yardi_companies`, `list_company_brands`, `find_related_inquiries`, `draft_reviewer_note` |
| Actions | `resubmit_documents`, `submit_contacts`, `submit_sales_data` (applicant); console actions per §3.3 (reviewer) |
| Cards | `case_status`, `contacts`, `sales_data_upload`, `reviewer_suggestion` (console); `document_upload` gains `mode: "intake" \| "reupload"` and `requested_doc_types` |
| Documents | `DocType` gains `sales_data` (not part of the intake document list) |
| Notes | `documents_resubmitted`, `contacts_submitted`, `sales_data_submitted`, `case_updated <event>` |
| REST | `/api/review/*` (§3.3); `GET /api/inquiries/{reference}?t=` gains `waiting_on_you` |
| Services | `IdentityService`, `YardiService`, `ReviewerDirectory` |
| Config | `REVIEWER_CONSOLE`, `YARDI_MAX_ATTEMPTS`; policy `review_routing`, `second_level_contacts`, `rejection_categories`, `after_rejection`, `auto_request_contacts_after_first_approval` |
| Frontend routes | `/inquiry/case`, `/review`, `/review/cases/:id` |

## 5. Sequencing

1. **Lifecycle core** — step 23: case data, live L4 transitions, routing, effects, back-office mocks, templates.
2. **Reviewer console** — step 24: review API, mock sign-in, queue and case pages, deterministic case brief.
3. **Case assistant** — step 25: case links, `case` agent, re-upload loop, rejection and approval framing, status page.
4. **Second-level requests** — step 26: contacts and sales data.
5. **Reviewer assistant** — step 27: reviewer agent, Yardi suggestions, drafted notes.
6. **Approval to Yardi and the gate** — step 28.

## 6. Assumptions

Status **Assumed** until Cenomi confirms.

| # | Assumption |
| --- | --- |
| A1 | The reviewer console stands in for the Tenant Admin Platform; reviewers sign in with a mock picker |
| A2 | Applicants answer requests through signed links, not an Azure AD sign-in |
| A3 | Azure AD invitations are mocked; accepting is a link in the dev inbox |
| A4 | Additional contacts are not OTP-verified; Azure AD verifies them when they accept the invitation |
| A5 | The routing table and regions are synthetic: Store → RLM-Store, Media → RPLM-Media, Specialty → RPLM-Specialty, per region |
| A6 | Estimated sales data is one file in the usual formats; Cenomi's template (§7.9.6) isn't known |
| A7 | Yardi search follows §7.1.1 c: first company-name word, active companies; brands from the company's previous leases and proposals |
| A8 | Rejection reason categories are a synthetic list in the policy |
| A9 | No review SLAs (L5 adds demo-only thresholds) |
| A10 | A contacts request opens automatically on first-level approval (requirements §7.1.1 b, "on contact creation"); reviewers can still request contacts later if none is open. Same as intake-channels D6 |
