# Demo feedback (3–4 Nov 2026)

**Status:** agreed 4 Nov 2026 (PRD v1.1, `docs/PRD.md` §11) · **Delivery:** days F1–F5, `prompts/feedback/` ([DELIVERY-PLAN](../DELIVERY-PLAN.md) Part C) · **Re-demo:** Tue 10 Nov 2026 · **Tracker:** [demo feedback implementation tracker](https://claude.ai/artifact/U4cXzYrjUKofTVjWR4oEHx) (F1–F20, I1–I19, M1–M12)

This spec changes what the 5-day slice built, in response to the client's demo feedback. It doesn't replace the M0, L3, L4 or L5 specs. Where it changes one of them, the section here says so, and the PR that builds it updates `docs/spec.md`.

## 1. Why

The client accepted conversational intake and verification inside the chat. He asked for four changes:

1. **CR numbers are public and sequential.** The public page must not reveal whether a company deals with Cenomi, or any of its details (F1, F2).
2. **This is an approval process.** The Lease Admin approves each document and each contact individually before the inquiry moves on (F8, F12, F13, F16, F18).
3. **Check the documents against the answers**, and fill what can be filled from them (F6, F20).
4. **Fewer steps.** Ask one authorised-signatory question instead of showing a contact form (F19).

Our 4 Nov review turned these into one intake flow with two paths and a shared review. Slice A (F1–F3) ships before the re-demo. Slice B (F4–F5) follows in Sprint 1.

```
Do you have a CR? ── No ──▶ chat intake: type the details, or upload the profiles to fill them (B)
        │                    email link + OTP · both profiles · expiry extracted · checks (B)
        └─ Yes ─▶ Sign in ─▶ Leasing Opportunities: company from Yardi by CR (B) · both profiles
                                                   │
Review, both paths: Lease Admin confirms expiry and approves each document → approves first level
  → contacts request ("Are you the authorised signatory?") → Lease Admin approves each contact
  → RLM / RPLM final review and approval → Yardi (company and brand codes shown, B)
```

## 2. Gate

The rows are checked on the day named. A row's test must pass in CI (or, for Playwright, locally with the result in the PR). All rows are Must unless marked.

| # | Criterion | Proved by | Day |
| --- | --- | --- | --- |
| D1 | The public chat never asks for, accepts, looks up or repeats a CR number. A typed CR number gets the sign-in reply and is never stored. | INV8 on every live turn; `tests/agent/test_cr_question.py`; Playwright `f1-cr-question`; live eval `cr_privacy` 3/3 | F1 |
| D2 | "Yes, I have a CR" shows the sign-in card, which lands on Leasing Opportunities. "No" continues the inquiry in chat. | `f1-cr-question`; `tests/api/test_cr_question.py` | F1 |
| D3 | The call-centre path is unchanged: staff still enter and check CRs (§7.1.1 a2, §7.1.2 a2). | `a2-call-centre`, `a2-existing-cr`, `a2-guest-service` still pass | F1 |
| D4 | First-level events can be fired only by the Lease Admin of the case's region. Final-level events can be fired only by the RLM or RPLM of the product line. Any other role is refused. | `tests/lifecycle/test_review_levels.py` (a wrong-role case for every reviewer event) | F1 |
| D5 | The Lease Admin approves or rejects each document, with remarks. First-level approval is refused until every required document is approved. | `tests/lifecycle/test_document_review.py`; Playwright `f2-document-approval` | F2 |
| D6 | Expiry: the date is extracted, then confirmed by the Lease Admin. Its status (expired, expiring soon, valid) comes from `policy.yaml` and the clock. An expired document can't be approved. Nothing is approved or rejected automatically. | `tests/lifecycle/test_document_expiry.py` (simulated clock); Playwright `f3-expiry` | F2 |
| D7 | A re-uploaded document goes back to pending. An approval sent for a file that has since been replaced is refused. | `tests/lifecycle/test_document_review.py::test_stale_file` | F2 |
| D8 | The Lease Admin approves or rejects each contact the tenant enters. A "Yes, I'm the authorised signatory" answer needs no separate approval. Final approval needs the required contacts approved. | `tests/lifecycle/test_contact_review.py`; Playwright `f4-contact-approval`; live eval `signatory` 3/3 | F2 |
| D9 | `DocumentReviewService` sits behind an interface with a mock and contract tests. A timeout leaves the document "check pending" and never blocks a decision. The service returns typed fields only, and no document text reaches a prompt. | `tests/services/test_document_review.py` (`-m contract`); `tests/security/test_document_text_isolation.py` | F1 |
| D10 | The re-demo runs end to end on Postgres, including a backend restart. | `make e2e-demo` (`demo.spec.ts`, three browser contexts) | F3 |
| D11 | Type or upload: extracted values are `derived`, carry their document as evidence, and are confirmed before submit. A re-upload sets them back to unconfirmed. | `tests/agent/test_document_extract.py`; Playwright `f5-type-or-upload`; live eval `document_extract` 3/3 | F4 |
| D12 | A difference between a profile and a typed value warns the applicant and flags it in the case brief. It never blocks submit. | `tests/domain/test_document_checks.py`; `f5-type-or-upload` | F4 |
| D13 | Signed in: company details come from Yardi by CR and are confirmed by the tenant. Both profiles are required, and the company profile is checked against the Yardi record. | `tests/agent/test_signed_in_new_brand.py`; Playwright `f6-signed-in-new-brand` | F5 |
| D14 | After Yardi accepts the lead, the company and brand codes show on the case page, the status page and the `case_status` card. | Extended `t1-lifecycle-to-yardi` | F5 |
| D15 | No regression: the step 12 live-eval baseline holds within `EVAL_TOLERANCE`. Changed goldens are re-recorded in the PR that changes them, with the reason. | `make eval-live`; `make golden` | F3, F5 |

## 3. Work items

### 3.1 "Do you have a CR?" on the public page (FB1; I2, I3; Must)

**Behaviour.**
- A self-service session opens with the welcome message and a `cr_question` card: **Yes, I have a CR** and **No, I don't**.
- The buttons send the UI action `cr_answer {has_cr: bool}`. The agent can record the same answer from text with the tool `record_cr_answer(has_cr)`, which calls the same handler.
- **Yes:**
  - the handler shows today's `sign_in_prompt` card with new wording, a landing URL of `<PUBLIC_BASE_URL>/tenant/opportunities`, and audit `inquiry_redirected {reason: "has_cr"}`;
  - the session moves to `redirected`, as the sign-in path does today, and nothing more is collected.
- **No:**
  - `draft.cr_status = "none"`, and company name and address join the basic-info bundle (as on today's skip path);
  - the CR number is not a field on this path.
- **A typed CR number.** A ten-digit number that matches the CR format, in a self-service message, is caught by a deterministic pre-model check (`app/agent/cr_question.py`):
  - it's never written to the draft, the audit payload or the history sent to the model, where it's replaced with `[CR number removed]`;
  - the turn gets the note `[guard] cr_number_typed`: reply with the sign-in prompt, and don't repeat the number.
- **Tools.**
  - Self-service intake loses `verify_cr` and `skip_cr` (new list `SELF_SERVICE_TOOLS`) and gains `record_cr_answer`.
  - Assisted mode keeps `verify_cr` (staff are signed in).
  - Existing-tenant mode is unchanged.
- **Policy:** `public_cr_check: ask_then_sign_in | lookup`, default `ask_then_sign_in`. `lookup` keeps today's behaviour so older goldens and tests can still run it. `existing_tenant_policy` now applies to the assisted channel only.

**Contracts** (add to `docs/spec.md`):
- the `cr_question` card;
- the `cr_answer` action;
- the `record_cr_answer` tool;
- `cr_status: "none"`;
- the new `sign_in_prompt` wording;
- `public_cr_check`.

**Acceptance:** D1–D3. Goldens that start with a CR lookup are re-recorded under `ask_then_sign_in`, and their old form keeps running under `lookup`.

### 3.2 Lease Admin as first-level reviewer (FB2; I8; Must)

**Data.**
- `ReviewRole` gains `lease_admin`, labelled "Lease Admin".
- `ReviewQueue` gains `first_role`, set by `routed` from `policy.first_level_review_role` (default `lease_admin`). `role` keeps the final reviewer from `review_routing`.
- `reviewers.json` gains one Lease Admin per region and one Lease Admin manager.

**Who acts.**
- `machine.py` gains a declared table, `EVENT_LEVEL: dict[str, Literal["first", "final"]]`:
  - first: every event from `first_review` and `reupload_requested`, plus the document and contact events in §3.4 and §3.5;
  - final: the rest.
- `_check_actor` reads the role for the event's level from the queue. There are no role-name conditionals in shared code; a startup test fails if a reviewer event has no level.

**Routing and notifications.**
- `routed` notifies the Lease Admin queue (`review_assigned`).
- `approved_first` notifies the final queue (`review_assigned` with `level: final`).
- The L5 stalled-review trigger notifies the queue of the level that's waiting.

**Console.**
- The Lease Admin's queue lists cases in `first_review` and `reupload_requested`, plus `second_review` cases with contacts waiting for approval.
- The RLM's queue lists `second_review` cases.
- Stage labels become "First review — Lease Admin" and "Final review — RLM / RPLM".
- `/dev` gains a Lease Admin persona.

**Acceptance:** D4. The existing stories T1 and T2 are updated so the first level is acted on by the Lease Admin.

### 3.3 Document review service (FB3 thin, FB7 full; I12; Must)

The agent never reads document content. A separate service does, and returns typed results only.

```python
class ExtractedValue(BaseModel):
    value: str
    page: int | None = None

class DocumentReviewResult(BaseModel):
    doc_type: DocType
    file_id: str
    status: Literal["done", "pending", "failed"]
    expiry_date: date | None = None
    fields: dict[str, ExtractedValue] = {}   # F4: company_name, company_address, brand_name_en, sales_category
    checked_at: datetime

class DocumentReviewService(Protocol):
    def review(self, ref: DocumentRef, path: Path) -> DocumentReviewResult: ...
```

**Mock** (`app/services/document_review.py`):
- results come from `mock_world/document_review.json`, keyed by file name: `*expired*` gives a date 30 days ago, `*soon*` gives today plus 7 days, and anything else gives today plus 365 days;
- F4 adds field values per scenario file in `e2e/fixtures/files/`;
- the expected answers can be read without opening any file.

**Calls.**
- The upload handler calls the service through the gateway (`"document_review", "review"`) after a company or brand profile is saved, and stores the result on `DocumentRef.review`.
- A timeout or outage stores `status: "pending"` and audits the failure. The console shows "check pending", and the Lease Admin can still decide.
- F1 ships the interface, the expiry-only mock and contract tests. F4 adds the fields.

**Isolation.**
- Tool results and notes may say that expiry or fields were extracted. They never contain document text.
- Extracted values reach the model only as draft field values (`source: derived`), like any other derived value.
- `tests/security/test_document_text_isolation.py` uploads a profile whose mock result carries an injection string in a field. It asserts that the string is stored as a value, shown on the confirm card as data, and never sent to the model as a system note or a tool result.

**Acceptance:** D9.

### 3.4 Per-document approval and expiry (FB4; I4, I18; Must)

**Data** (on the case, not the applicant's draft):

```python
class DocumentDecision(BaseModel):
    doc_type: DocType
    file_id: str                                   # the upload this decision is about
    status: Literal["pending", "approved", "rejected"] = "pending"
    remarks: str | None = None
    expiry_extracted: date | None = None           # from DocumentReviewResult
    expiry_confirmed: date | None = None           # confirmed or corrected by the Lease Admin
    by: str | None = None
    at: datetime | None = None

Case.document_decisions: dict[DocType, DocumentDecision]   # one per uploaded intake document
```

**Expiry status** (`app/workflow/expiry.py`, pure):
- computed from `expiry_confirmed`, falling back to `expiry_extracted`, against today on the app clock (`app/clock.py`, so the simulated clock moves it);
- `expired` if before today;
- `expiring_soon` if less than `policy.document_expiry.expiring_soon_days` days away (default 14, M9);
- otherwise `valid`, or `unknown` when there's no date.

**Events** (first level; state `first_review`):

| Event | Payload | Guard |
| --- | --- | --- |
| `document_expiry_confirmed` | `doc_type`, `file_id`, `expiry_date` | `file_id` is the current upload |
| `document_approved` | `doc_type`, `file_id`, `remarks?` | current upload; expiry status isn't `expired`; an `unknown` expiry must be confirmed first |
| `document_rejected` | `doc_type`, `file_id`, `remarks` (required) | current upload |

**Rules.**
- `reupload_requested` with no `doc_types` uses the rejected documents. Their remarks are prefilled into the request's remarks.
- `approved_first` gains blockers:
  - `document_pending:<type>` for each required document not approved;
  - `document_rejected:<type>` for each rejected one;
  - `expiry_unconfirmed:<type>`.
- `documents_resubmitted` resets the decision for each re-uploaded type to `pending`, with the new `file_id` and the new review result.
- **Expired documents:** the console marks the row "Expired on …" and preselects Reject, with the remark "This document expired on {date}. Please upload a current one." The Lease Admin presses the button. The system never fires the event itself (ADR-F6).

**Console.**
- Each document row has a viewer link, the expiry status chip, an editable expiry date, and **Approve** and **Reject** (remarks required).
- The row shows who decided and when.
- The brief's `next_decision_checklist` lists what's pending.

**Case assistant.** It explains rejected or expired documents in plain words from the request's remarks, and asks only for those (today's re-upload card).

**Audit.** Every event goes through `apply_event` (`case_transition`), as today.

**Acceptance:** D5–D7.

### 3.5 Per-contact approval and the signatory question (FB5; I5, I16; Must)

**Data.**

```python
class TenantContact(BaseModel):            # existing fields kept
    contact_id: str
    approval: Literal["pending", "approved", "rejected"] = "pending"
    approval_remarks: str | None = None
    approved_by: str | None = None         # reviewer id, or "system:<reason>"
    added_by: Literal["tenant", "reviewer", "system"] = "tenant"
```

**Signatory question.**
- When the contacts request opens, the case agent shows a `signatory_question` card: **Yes, I'm the authorised signatory** and **No, someone else is**.
- The UI action is `signatory_answer {is_signatory: bool}`, and the tool `record_signatory_answer` calls the same handler.
- **Yes:** `authorized_signatory` is written with `same_as_primary` from the verified primary contact and approved on entry (`approved_by: "system:verified_primary"`, M8). Policy flag: `contacts.applicant_signatory_needs_approval: false`.
- **No:** the contacts card asks for the signatory's name, email and mobile, then the billing contact and the optional roles.

**Events.**
- **Lease Admin, state `second_review`:**
  - `contact_approved {contact_id}`;
  - `contact_rejected {contact_id, remarks}`, which opens a contacts request for that role (`CaseRequest.roles`);
  - Should: `contact_added {contact}`, approved on entry.
- **Tenant:** `contacts_provided` sets each new or changed contact to `pending`. Unchanged approved contacts stay approved.
- **System:** contacts prefilled from the tenant record are approved on entry (`added_by: system`).

**Rules.**
- `approved` blockers become `contact_not_approved:<role>` for each required role that isn't approved, not only missing.
- `require_contacts_before_approval` stays.

**Console.**
- Contact rows with an approval chip, **Approve** and **Reject** (remarks required) for the Lease Admin.
- The RLM sees the chips read-only.

**Acceptance:** D8.

### 3.6 Demo hardening (FB6; I6, I15; Must)

**Demo stack.**
- `make demo` runs on Postgres (`docker-compose.demo.yml`, step 13 store).
- `scripts/seed_demo.py` seeds three cases:
  - first review, with one expiring-soon and one expired profile;
  - second review, with contacts waiting for approval;
  - approved, with codes from F5 once that day lands.
- `POST /api/dev/reset` reseeds.

**Rehearsal.**
- `demo.spec.ts` is rewritten for the 10 Nov script with three browser contexts (applicant, Lease Admin, RLM). It restarts the backend and continues.
- `docs/demo-script.md` opens turn by turn, and the one-message paste becomes a later "power user" moment.

**Local setup check (Swaroop).** The repo sits outside any iCloud-synced folder, migrations apply from clean, and `make demo` starts on a fresh clone.

**Acceptance:** D10.

### 3.7 Type or upload, with profile checks (FB7; I19; Must for slice B)

**Choice.**
- On the no-CR path, the agent offers once, in one line: type the company and brand details, or upload the company and brand profiles and the agent fills them in.
- Either answer is accepted, and the agent doesn't push one.

**Upload path.** The F4 mock returns these fields:
- company profile: `company_name`, `company_address`;
- brand profile: `brand_name_en`, `sales_category` (mapped to master data ids).

They're written with `source: derived`, evidence `"Company Profile: <file name>, uploaded <time>"`, and `confirmed: false`. The confirm card shows them with that evidence (golden rule 2).

**Typed path.** Values stay `source: user`. Once the profiles are uploaded, `app/domain/document_checks.py` compares each typed value with the extracted one. The comparison ignores case, whitespace and punctuation, normalises Arabic, and maps categories through master data.

**Mismatch.**
- A difference becomes `draft.document_checks[field] = {typed, document_value, doc_type}`.
- The turn gets the note `[ui_event] document_mismatch <field>`: tell the applicant in one sentence what differs, and offer to update.
- It never blocks submit.
- After submit, the case brief shows each flag to the Lease Admin.

**Re-upload.** Values extracted from a replaced file go back to unconfirmed and are re-checked (ADR-F4).

**Questions.** The agent never asks for a value a document has already given. The `unnecessary_questions` KPI (§6) counts any that slip through.

**Acceptance:** D11, D12.

### 3.8 Signed-in tenant, new brand (FB8; I9, I14; Must for slice B)

**Company from Yardi.**
- Today, signed-in prefill reads the mock Tenant Central record (`tenants.json`).
- F5 adds `YardiService.company_by_cr(cr_number)`: the mock Yardi companies gain `cr_number`, `address` and `codes`, linked to `tenants.json`.
- Company name and address are prefilled as `verified` and confirmed by the tenant on the basic-info card.

**Brand and documents.**
- The brand follows §3.7 (type or upload).
- Both profiles are required. Documents already on file aren't reused for these two (assumption: a new brand under the same company).
- The company profile is checked against the Yardi record, using the same checks and flags as §3.7.

**Codes.**
- The `send_lead` mock returns `company_code` and `brand_code`, stored on `YardiLink`.
- The case page, status page and `case_status` card show them after `sent_to_yardi`.

**Acceptance:** D13, D14.

### 3.9 Parked

| Item | Why parked | Until |
| --- | --- | --- |
| Request access (I10, FB9) | Outside §7.1; needs the client's agreement and a PRD change | M3 |
| CR without a login (CR-3) | Out of scope for now | M2 |
| CR certificate extraction and cross-check (I17, I11) | The client hasn't said whether the CR certificate is required | M1 |
| Notification-agent entry for reviewers (I13) | The inbox and queue are enough (Q8) | Dropped |

## 4. Design rules (ADRs)

These come from the [architecture assessment](https://claude.ai/artifact/FfG3nKjo2uLM469yuMckwJ) (§5, §8, §13, §16) and apply to every day.

| ADR | Decision | Where it shows |
| --- | --- | --- |
| F1 | **Code decides, the model explains.** Approvals, expiry status, mismatch flags and the CR branch are computed in code. The agent only words them. | §3.1, §3.4, §3.7 |
| F2 | **No role-name branches.** Review levels are declared data (`EVENT_LEVEL`, `first_level_review_role`); shared code reads them. | §3.2 |
| F3 | **Stage-level authorization.** Every reviewer event checks the role for its level and region. Each event has a wrong-role test. | §3.2, D4 |
| F4 | **Confirmation is bound to what was shown.** A value is confirmed for the file it came from; replacing the file resets it. A decision names the `file_id` it was made on. | §3.4, §3.7 |
| F5 | **Uploads are untrusted input.** Only typed fields leave the document review service, and no document text reaches a prompt. | §3.3, D9 |
| F6 | **Recommendation only.** The review service's result and an expired date are suggestions; a person approves or rejects. No path changes a case's status without a reviewer or applicant action (PRD rule 6). | §3.4 |
| F7 | **Provenance on every extracted value:** document, file, upload time, shown on the confirm card and in the brief. | §3.7, §3.8 |

## 5. Stories (Playwright)

| Story | Layer | Day | Steps |
| --- | --- | --- | --- |
| `f1-cr-question` | INT `@scripted` | F1 | Yes → sign-in card → `/tenant/opportunities`. No → intake continues. A typed CR number → sign-in reply; the number isn't in the draft panel, SSE events or audit. |
| `f2-document-approval` | INT, two contexts | F2 | Submit → Lease Admin rejects the Brand Profile with remarks → re-upload request → applicant re-uploads in the case chat → Lease Admin approves both → **Approve first level** enabled → approves |
| `f3-expiry` | INT | F2 | Profiles `company_expired.pdf` and `brand_soon.pdf` → console shows "Expired" (Reject preselected, Approve disabled) and "Expiring soon" (approvable) → Lease Admin corrects a date → status updates |
| `f4-contact-approval` | INT, two contexts | F2 | Contacts request → "Yes, I'm the authorised signatory" → billing contact → Lease Admin rejects billing → tenant fixes it → Lease Admin approves → RLM **Approve** enabled |
| `f5-type-or-upload` | INT | F4 | Upload path: values filled and confirmed with evidence. Typed path: a mismatch warns in chat and shows in the brief; submit still works. |
| `f6-signed-in-new-brand` | INT | F5 | `/tenant` → Raise inquiry → company from Yardi → brand from the brand profile → both profiles → submit |
| `demo.spec.ts` | DEMO | F3 | The whole 10 Nov script with applicant, Lease Admin and RLM contexts; backend restart mid-review; continue |

The scenario classes from the assessment (§13.2) each get at least one backend or Playwright test:

| Class | Test |
| --- | --- |
| Failure | Document review times out → "check pending" → Lease Admin still decides (`test_document_review.py`) |
| Concurrency | Two Lease Admin tabs approve the same document → the second gets `invalid_payload` (already decided). The tenant re-uploads during approval → the approval with the old `file_id` is refused. |
| Authorization | RLM fires `document_approved` → `not_in_queue`. A Lease Admin from another region → refused. A tenant case link for another case → 404. A prompt injection inside a profile's mock fields → stored as data only (D9). |
| Interruption | FAQ question mid-upload; resume from the email link after uploading one profile |
| Stale context | A contact edited after approval → back to pending. A document replaced after approval → back to pending. |
| Recovery | Restart between `document_approved` and its audit or effects → state and timeline consistent after reload (`tests/durability/`) |

## 6. Evaluation

**New invariant INV8** (`I8` in `app/agent/invariants.py` and `e2e/support/invariants.ts`). On the self-service channel, no assistant text or card payload contains:
- a CR number;
- a company name or address that came from a CR lookup, as opposed to one the applicant typed or a document gave.

It's checked on every AGENT-LIVE and E2E-LIVE turn, and a breach fails the run.

**Live-eval groups** (`scripts/eval_live.py`, ×3, against the step 12 baseline):

| Group | Day | Scenarios |
| --- | --- | --- |
| `cr_privacy` | F1 | "Yes I have a CR" · "my CR is 1010000000" · "check these CRs for me: …" (refused) · a CR typed in Arabic digits · "No CR" then a full intake |
| `signatory` | F2 | "Yes, that's me" · "No, my partner Ahmed signs" (collects his details) · "I'm not sure" (explains the role, asks again) |
| `document_extract` | F4 | Offers the choice once · upload path with confirmations · typed path with a mismatch warning · never re-asks a value a document gave |

**Goldens.** New transcripts are added for `f1-cr-question` and `f4-contact-approval` (`tests/parity/golden/`) and exported as frontend fixtures.

**KPIs**, recorded by `scripts/eval_live.py` until step 22 builds `scripts/kpi_report.py`, and baselined on today's goldens:
- questions per submitted inquiry;
- the share of fields filled from documents and accepted unchanged;
- documents rejected at first review;
- `unnecessary_questions`: a question for a value the draft or a document already holds.

## 7. Contract changes to fold into `docs/spec.md`

| Day | Change |
| --- | --- |
| F1 | Card `cr_question`; action `cr_answer`; tool `record_cr_answer`; `cr_status: "none"`; `sign_in_prompt` wording and URL; policy `public_cr_check`, `first_level_review_role`; `ReviewRole.lease_admin`; `ReviewQueue.first_role`; `EVENT_LEVEL`; `DocumentReviewService`, `DocumentReviewResult`, `DocumentRef.review` |
| F2 | `DocumentDecision`, `Case.document_decisions`; events `document_expiry_confirmed`, `document_approved`, `document_rejected`; new `approved_first` blockers; policy `document_expiry`; `TenantContact` approval fields; card `signatory_question`; action `signatory_answer`; tool `record_signatory_answer`; events `contact_approved`, `contact_rejected` (and `contact_added`, Should); `CaseRequest.roles`; new `approved` blockers; `CaseDetail` document and contact rows |
| F3 | `POST /api/dev/reset` reseeds; `scripts/seed_demo.py` |
| F4 | `DocumentReviewResult.fields`; `draft.document_checks`; note `document_mismatch`; brief flags |
| F5 | `YardiService.company_by_cr`; `YardiLink.company_code`, `brand_code`; status page and `case_status` codes |

## 8. Assumptions and open questions

The assumptions are in [`docs/assumptions.md`](../assumptions.md), under "Demo feedback assumptions". Each row names the day it lands; until then, the older rows still describe `main`.

The questions for the client are M1–M12 in the tracker (section 6). The ones that could change this spec are:

| Question | Default we build |
| --- | --- |
| M1: is the CR certificate required? | Optional, nothing extracted |
| M2: CR without a login | Sign-in only |
| M3: request access | Not built |
| M7: is every signed-in inquiry a new brand? | Both profiles always |
| M8: is OTP enough for an applicant who is the signatory? | Approved on entry |
| M9: expiry gap | Under 14 days = expiring soon |

An answer that confirms a default is recorded in `docs/assumptions.md`. An answer that changes one is a PRD §11 change.

## 9. Out of scope

- Real document parsing, OCR, and the real document review agent (mocked until its owner shares the interface, M4).
- Request access.
- CR certificate extraction.
- A notification-agent entry for reviewers.
- Changes to the second-level steps other than contacts: estimated sales data and Yardi re-link are unchanged.
