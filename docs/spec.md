# Send Inquiry Agent — technical spec (source of truth)

Everything Cursor builds must match this file. If a contract here is missing or wrong, update this file in the same change.

## 1. Flow summary

1. User opens the chat from "Send us an inquiry" on the sign-in page. A session is created and the agent greets them.
2. **Gate**: the agent asks for the CR number. `verify_cr` → existing account: point to Sign In, stop. New: prefill company details as `verified` (unconfirmed). The user may skip.
3. **Collect**: brand, unit type, sales category, one mall, space and budget, contact. The agent derives what it can and asks the user to confirm.
4. **Verify**: a one-time link to the email (mocked; a demo button stands in for the click) and, when a mobile was given, an SMS code (mock code from `OTP_MOCK_CODE`). A landline-only applicant is verified by email alone.
5. **Documents**: Company Profile and Brand Profile are required; others optional. Presence, type and size only.
6. **Review**: review card with every field and its source, edit, consent checkbox, Submit.
7. **Submit**: deterministic, from the review card. Returns a reference `GEO-{UNIT}-{6 digits}` and a success card.

## 2. Data model (`backend/app/domain/models.py`)

```python
class Source(str, Enum):
    USER = "user"          # the user stated it, or picked it in a card
    DERIVED = "derived"    # the agent inferred it from conversation
    VERIFIED = "verified"  # returned by verify_cr
    DEFAULT = "default"    # system default

class FieldValue(BaseModel):
    value: Any | None = None
    source: Source | None = None
    confirmed: bool = False      # USER and DEFAULT values are confirmed on write
    evidence: str | None = None  # derived values only: the user's words (≤ 80 chars, L3 §3.9)

class DocumentRef(BaseModel):
    doc_type: DocType
    file_id: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime
    copied_from: str | None = None   # reused from that reference by a follow-on inquiry

class InquiryDraft(BaseModel):
    fields: dict[FieldKey, FieldValue]      # every FieldKey present; empty FieldValue when unknown
    cr_status: Literal["unknown", "new", "existing", "skipped"] = "unknown"
    documents: dict[DocType, DocumentRef] = {}
    email_verified: bool = False            # one-time link
    mobile_verified: bool = False           # SMS code; only needed when a mobile is given
    email_link_sent_to: str | None = None   # address the live link went to
    otp_sent_to: str | None = None          # mobile the live code went to
    otp_attempts_left: int = 3
    terms_accepted: bool = False
    reference: str | None = None
    verified_at: datetime | None = None     # when the contact became fully verified
    follow_on_of: str | None = None         # the submitted reference this inquiry follows on from
```

**Arabic digits.** Every numeric rule (CR, phone numbers, VAT, National ID, area, rent, the OTP code) runs on `validation.normalise_digits(text)`, which maps Arabic-Indic (`٠–٩`) and Eastern Arabic-Indic (`۰–۹`) digits to ASCII. Contact detection (`contact_infer`), the guard's checks and the tools see normalised text too (L3 §3.10).

### Field keys

| Key | Label | Group | Type | Required | Rule |
| --- | --- | --- | --- | --- | --- |
| `cr_number` | CR number | company | str | no | 10 digits |
| `company_name` | Company name | company | str | yes | 2–120 chars |
| `company_address` | Company address | company | str | yes | 5–250 chars |
| `brand_name_en` | Brand name (EN) | brand | str | yes | 1–80 chars, Latin script |
| `brand_name_ar` | Brand name (AR) | brand | str | yes | 1–80 chars, contains Arabic script |
| `unit_type` | Unit type | brand | enum id | yes | master `unit_types` and a policy `product_lines` entry |
| `sales_category` | Sales category | brand | enum id | yes | master `sales_categories` |
| `malls` | Mall | space | list[mall id] | yes | 1 to policy `max_malls_per_inquiry` (default 1: `one_mall_per_inquiry`; above 1: `too_many_malls`), in master `malls` |
| `area_min` | Area min (sqm) | space | int | no | default 10, source default |
| `area_max` | Area max (sqm) | space | int | no | default 25000, source default; 10 ≤ min ≤ max ≤ 25000 |
| `rent_period` | Rent period | space | enum id | no | master `rent_periods`; required if rent given |
| `rent_min` | Rent min (SAR) | space | int | no | ≥ 0 |
| `rent_max` | Rent max (SAR) | space | int | no | ≥ rent_min |
| `lease_period` | Lease period | space | enum id | no | master `lease_periods` |
| `first_name` | First name | contact | str | yes | 1–50 chars |
| `last_name` | Last name | contact | str | yes | 1–50 chars |
| `email` | Email | contact | str | yes | valid email |
| `mobile` | Mobile | contact | str | one of | `+9665XXXXXXXX`, or a non-Saudi number in E.164 (`+` + 8–15 digits) from a country the policy allows (`phone_country_not_allowed`) |
| `landline` | Office landline | contact | str | one of | `+966` + 8 or 9 digits, not starting with 5, or a non-Saudi number in E.164 from a country the policy allows |
| `vat_number` | VAT number | documents | str | no | 15 digits, starts and ends with 3 |
| `national_id_number` | National ID / Iqama | documents | str | no | 10 digits starting with 1 or 2 |
| `national_address` | National address | documents | str | no | 5–250 chars |

"Required" for contact means `mobile` or `landline`. The pseudo key `contact_number` is accepted by `update_draft`: it is normalised and written to `mobile` or `landline` by prefix. Saudi numbers are classified by prefix; a non-Saudi number defaults to `mobile` (no numbering-plan library in the POC), so a foreign landline must be written to `landline` explicitly.

Changing `email` clears `email_verified` and `email_link_sent_to`; changing `mobile` clears `mobile_verified`, `otp_sent_to` and resets `otp_attempts_left`.

Display values: enum ids render as labels; `malls` as the mall name; area as `"25 – 35 sqm"`; rent as `"Up to SAR 250,000 / year"` or `"SAR 100,000 – 250,000 / year"`.

### Document types

| `doc_type` | Label | Required |
| --- | --- | --- |
| `company_profile` | Company Profile | yes |
| `brand_profile` | Brand Profile | yes |
| `cr_certificate` | CR certificate | no |
| `vat_certificate` | VAT certificate | no |
| `national_id` | National ID / Iqama | no |
| `national_address` | National Address | no |
| `articles_of_association` | Article of Association | no |

Allowed extensions: `pdf, jpg, jpeg, png, doc, docx, xlsx, zip`. Max size `MAX_UPLOAD_MB` (5). Content is never read.

### `can_submit(draft) -> list[Blocker]` (empty list = can submit)

Blockers, in this order:
1. `cr_existing`: `cr_status == "existing"`.
2. `cr_pending`: `cr_status == "unknown"` (neither verified as new nor skipped).
3. `missing_field:<key>`: each required field without a value (contact counts once as `missing_field:contact`).
4. `unconfirmed_field:<key>`: each required or provided field whose source is derived/verified and `confirmed` is false.
5. `email_not_verified`, then `mobile_not_verified` (only when a mobile is given).
6. `missing_document:<doc_type>`: each required document not uploaded.
7. `terms_not_accepted`.

### Phase (`domain/summary.py: compute_phase`)

`existing_account` if cr existing → `submitted` if reference → `gate` if cr unknown → `collecting` if any blocker 3–4 → `verifying` if any blocker 5 → `documents` if blocker 6 → `review`.

## 3. Agent tools (`backend/app/agent/tools.py`)

All tools return a short factual string for the LLM. Tools that change state return `Command(update=...)` with a `ToolMessage`, and emit `draft` (and cards) via the stream writer.

| Tool | Args | Behaviour |
| --- | --- | --- |
| `verify_cr` | `cr_number: str` | Validate format; call `CrService.verify`. Existing → `cr_status="existing"`. New → `cr_status="new"`, write `cr_number` (user) and any returned `company_name`/`company_address` as `verified`, unconfirmed; emit a `confirm_fields` card for them. |
| `skip_cr` | — | Only after the user agreed to skip. `cr_status="skipped"`. |
| `get_master_data` | `kind: str, city: str \| None` | Read-only lookup: `unit_types`, `sales_categories`, `cities`, `malls`, `lease_periods`, `rent_periods`. |
| `update_draft` | `fields: list[{key, value, source: "user" \| "derived", evidence?: str}]` | Validate each; write valid ones (user → confirmed, derived → unconfirmed); return per-field errors. Emit a `confirm_fields` card listing newly written derived values. `evidence` (derived only) quotes the user's words the value came from, ≤ 80 chars; it is kept only if the user really wrote it (case and spacing ignored), otherwise the result says `Evidence ignored …`. The LLM can't write `verified`, `default`, `email_verified`, `mobile_verified`, `terms_accepted`, `documents` or `reference`. |
| `confirm_fields` | `keys: list[str]` | Mark those unconfirmed fields confirmed (only after the user agreed and the key was on a confirm card shown before this turn). Skips others with `not_shown`, and with `user_expressed_doubt` when the user doubted that field (English or Arabic, `confirm_policy.py`) or sent only a short message of doubt ("hmm, not sure", «مو متأكد»). Updates the existing confirm card. |
| `get_missing_fields` | — | Returns blockers from `can_submit` in plain words. |
| `show_mall_picker` | `city: str` | Emits a `mall_picker` card with that city's malls and the current selection. |
| `send_verification` | `resend: bool = False` | Requires `email` and a contact number. Emails a link via `EmailVerificationService.send_link` unless one already went to the current address; texts a code via `OtpService.send` when a mobile is given and no code went to it yet (`resend` forces both). Emits the `verification` card. |
| `request_documents` | — | Emits the `document_upload` card. |
| `show_review` | — | Only when the only remaining blocker is `terms_not_accepted`; emits the `review` card. Otherwise returns the blockers. |
| `suggest_replies` | `options: list[str]` (1–3, ≤ 60 chars each) | Emits a `quick_replies` card for this turn. |
| `search_faq` | `query: str` | Top 2 matches from `faq.json` (keyword score). The agent answers only from these. |
| `get_inquiry_status` | `reference: str` | Only this conversation's own references (the current inquiry and, after a follow-on, the one it follows); a reference alone must not expose an applicant's case, so others point to the tracking link. Calls `StatusService.get` through the gateway. |
| `start_follow_on` | `mall_id: str \| None` | Only after this inquiry was submitted (L3 §3.11). Starts the next inquiry in the same chat (`inquiry_seq` + 1) with `follow_on_of=<reference>`: company, brand, unit type, sales category and contact copied as `verified`, unconfirmed, on one `confirm_fields` card titled "Same details as <reference>"; Company Profile and Brand Profile reused by reference (`copied_from`); the contact stays verified when it was verified within policy `follow_on_reuse_hours`. `mall_id` is saved only when the user named that mall, and never the submitted inquiry's mall. Result starts `follow_on_started from=<ref>`; audit `follow_on_started`. |

There is no submit tool and no verify tool: both happen through UI actions, so the link token, the SMS code and consent never pass through the LLM.

## 4. UI actions (handled in the chat endpoint before the graph runs)

| Action | Payload | Backend does, then runs the graph with a `[ui_event]` note |
| --- | --- | --- |
| `select_malls` | `{mall_ids: list[str]}` | Validate (1 to `max_malls_per_inquiry` malls); write `malls` as user, confirmed. Note: `malls_selected: <name>` or `malls_invalid <code>` |
| `verify_email` | `{token: str}` | `EmailVerificationService.verify`; valid only for the link sent to the current email. Sets `email_verified`. Note: `email_verified` (+ ` verification_complete` when nothing else is pending) or `email_link_invalid`. The token is never added to messages. |
| `resend_email_link` | `{}` | New link to the current email (the old one stops working), within the resend limits (policy `resend`). Note: `email_link_resent`, `resend_throttled <seconds>` or `service_error email <kind>` |
| `submit_otp` | `{code: str}` | Only for the code sent to the current mobile. `OtpService.verify`; on success `mobile_verified=True`; on failure decrement attempts (0 → auto resend within the resend limits, reset to 3). Note: `mobile_verified` (+ ` verification_complete`), `otp_failed attempts_left=N`, `otp_resent`, `resend_throttled <seconds>`, `service_error otp <kind>` or `otp_not_sent`. The code is never added to messages. |
| `resend_otp` | `{}` | Resend to the mobile within the resend limits, reset attempts. Note: `otp_resent`, `resend_throttled <seconds>`, `service_error otp <kind>` or `otp_send_blocked no_mobile` |
| `edit_field` | `{key, value}` | Validate; write as user, confirmed. Note: `field_edited <key>` |
| `confirm_card` | `{card_id}` | Confirm all fields on that confirm card. Note: `fields_confirmed <keys>`; `fields_already_confirmed` when everything on the card is already confirmed (the card is re-sent; not a failure); `confirm_failed` for an unknown card; `confirm_failed stale_card` for a card of an earlier inquiry in the chat |
| `accept_and_submit` | `{terms_accepted: true}` | **Submit once:** if a reference exists, re-emit the same `success` card (note `submitted reference=<ref> (repeat)`). Otherwise set `terms_accepted`; run `can_submit`; if clear, `SubmitService.submit` with idempotency key `inq:<session_id>:v<inquiry_seq>` (`v1`, then `v2`… for follow-on inquiries) → set `reference`, send `submission_email` (verified email) and `submission_sms` (verified mobile), emit `success` with the private `tracking_url`. Note: `submitted reference=<ref>`, `submit_blocked <blockers>`, `submit_pending timeout\|unavailable` (nothing lost; Submit again returns the same reference) or `submit_failed rejected\|invalid` |
| `documents_updated` | `{}` | Recompute required documents from the draft. Note: `documents_complete` or `documents_pending <doc_types>` |
| `set_document_number` | `{key, value}` | Validate and write the document number field as user, confirmed. Note: `document_number_set <key>` or `document_number_invalid <key> <code>` |
| `cr_check` | `{cr_number}` | The CR check from a card (form mode): same rules as `verify_cr` (existing account, `allow_inquiry`, or new with the company name and address prefilled on a confirm card). Note: `cr_checked existing\|existing_allowed\|new`, `cr_invalid <code>`, `cr_already_done` or `service_error cr <kind>` |
| `cr_skip` | `{}` | Skip the CR (form mode). Note: `cr_skipped` or `cr_already_done` |
| `request_handoff` | `{reason?: "user_asked" \| "model_unavailable"}` | Human handoff (L3 §3.6): `CallCentreService.create_case` with the inquiry, the reason and a summary built from the draft and the last three user messages (no model call); emit the `handoff` card. One open case per inquiry: asking again shows the same case. Needs no model, so form mode uses it. The router's `human_help` intent calls the same handler. Note: `handoff_created <reason>`, `handoff_created <reason> (repeat)`, or `handoff_created <reason> service_error call_centre <kind>` (the card still shows the phone number and hours) |

**Form mode (L3 §3.14).** When the model fails twice in one turn (provider timeout or outage, or an `llm` fault), or always with `FORM_MODE=true`, the session enters form mode (`Session.form_mode`, audit `form_mode_entered`): the turn ends with a fixed bubble ("Our assistant isn't available right now…"), the `form_mode` card and the card for the next step. In form mode a UI action applies its change and emits its cards, then the phase decides the next card — no agent turn runs: CR (`cr_check` / `cr_skip`), details (missing values typed into the form-mode card and saved with `edit_field`; a `confirm-form` card for derived or prefilled values still unconfirmed; a mall picker listing every mall), verification (sent without the model, then the `verification` card), documents, review. Values the tools saved before the failure are kept. The next typed message tries the model again with a `[ui_event] form_mode_resume` note; if it answers, the session leaves form mode (audit `form_mode_left`) and the `form_mode` card is re-sent with `active: false`. A bug in our own code is still an `error` event, never form mode.

Every service call goes through the gateway (`app/gateway/`). A failure becomes one of four kinds, `timeout`, `unavailable`, `rejected` or `invalid`, and reaches the agent as `service_error <service> <kind>` (in a note, or at the start of a tool result) — never as a raw error.

`[ui_event]` notes are appended as a `HumanMessage` whose content starts with `[ui_event]`. They are never shown in the chat UI. The system prompt tells the agent they are system notifications, not the user's words.

### Intent router (`app/agent/router.py`, L3 §3.5)

Before the agent graph runs on a typed message (not a UI action, not while the session is in form mode), `route_message(text, session) -> RouteDecision` chooses an intent:

| Intent | Handling |
| --- | --- |
| `inquiry_intake` | Run the agent graph (default) |
| `inquiry_status` | Run the agent graph (`get_inquiry_status` tool) |
| `human_help` | `request_handoff` with `{reason: "user_asked"}` (handoff card + case), then run the graph with one `HumanMessage`: the user's text plus the `[ui_event] handoff_created …` note |
| `general_inquiry`, `existing_tenant_new_space`, `off_topic` | Short redirect reply from a small prompt with no write tools, streamed as `token` events, then `done` (no graph turn) |

Rules (in order): a `GEO-{STR\|MED\|SPC}-{6 digits}` reference → `inquiry_status`; an explicit request for a person (English or Arabic; not a contact line like "call me on …") → `human_help`; with `existing_tenant_policy: sign_in`, only in phase `gate` and when the inquiry has no `reference` or `follow_on_of`, phrasing about already leasing → `existing_tenant_new_space`. Otherwise, only in phase `gate`, a structured-output classifier (`ROUTER_MODEL`, default `OPENAI_MODEL`) returns `{intent, confidence}`. Below `ROUTER_MIN_CONFIDENCE` (default `0.6`), or when phase is not `gate`, the router defaults to `inquiry_intake` without calling the classifier. In `AGENT_MODE=scripted`, rules apply and redirects use fixed copy (no classifier or redirect model). Classifier and redirect calls use the gateway as service `llm_router` (separate from the agent's `llm` budget). Each decision is recorded as audit type `routing_decision` `{intent, via, confidence?}`.

## 5. Guard node (deterministic)

After the agent's final reply each turn:
1. Recompute `phase`; emit a `draft` event.
2. Attach the card for a phase the user just entered if it hasn't been shown: `documents` → `document_upload`, `review` → `review`. (`verifying` cards come from `send_verification`.)
3. If the reply claims the inquiry was submitted (`claims_submission` in `guard.py`: "has been submitted", "I've sent your inquiry", "your reference is …"; conditional mentions such as "once the inquiry is sent" don't count) while `reference` is None → add a system note and route back to `agent` once. After a follow-on, a reply about the earlier inquiry (it names `follow_on_of`, or `start_follow_on` ran this turn) is allowed.
4. If phase is `existing_account`, ensure the reply points to Sign In.
5. Doubt: when the user doubts a derived or prefilled value ("not sure about the category", «مو متأكد من الفئة»), that field is un-confirmed (values the user typed are left alone). Doubt is attributed to the nearest field named after the doubt phrase, else before it, in the same sentence.
6. When `malls` is empty and the user's message names exactly one seed mall (same mention rules as `filter_mall_ids`), write that mall id as `user` (naming two or more writes nothing, so the agent asks which one) (see `fill_mentioned_malls` in `mall_match.py`). Also runs after `update_draft` when malls were omitted. Mall mention: the full normalised mall name (or optional `aliases` on a mall in master data) must appear as whole words in the user message (`\b` boundaries, optional leading “the”); city or country tokens alone do not match.

## 6. REST API (`/api`)

Errors: `{"error": {"code": str, "message": str}}` with 4xx/5xx.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{status:"ok"}` |
| POST | `/api/sessions` | — | `{session_id, messages:[{id, role:"assistant", text}], cards:[UiCard], draft:DraftSummary}` (fixed welcome, see design spec) |
| POST | `/api/sessions/resume` | `{token}` (purpose `resume`) | Same shape as `POST /api/sessions` for the same `session_id`: the last 20 messages (`role` `user` or `assistant`), the latest version of each card, the draft. 400 `token_invalid` / `token_expired`; 404 `inquiry_not_found` |
| POST | `/api/verifications/email` | `{token}` (purpose `verify_email`, from the emailed link) | `{status:"verified", session_id, email_masked, resume_token}`. 400 `token_invalid` / `token_expired` / `token_used` / `email_changed`. A link works once; only the latest link works |
| POST | `/api/sessions/{id}/chat` | `ChatRequest` | `text/event-stream` (section 7) |
| POST | `/api/sessions/{id}/documents` | multipart: `doc_type`, `file` | `{document, card: UiCard(document_upload), draft}` · 400 `invalid_extension` / `too_large` / `unknown_doc_type` |
| DELETE | `/api/sessions/{id}/documents/{doc_type}` | — | `{card, draft}` |
| GET | `/api/sessions/{id}/draft` | — | `DraftSummary` |
| GET | `/api/master/{kind}` | `?city=` for malls | list of master items |
| GET | `/api/inquiries/{reference}` | `?t=<token>` (purpose `track`, required) | `{reference, status:"under_review", submitted_at, steps:[…], stages:[{key, label, state}] (submitted → first_review → second_review → outcome), current_stage, owner_role (a role, never a person), waiting_on_you:[], last_change}`. A missing, wrong or expired token gets the same 404 `reference_not_found` as an unknown reference |
| GET / DELETE | `/api/dev/outbox?to=` | — | `DEV_TOOLS=true` only: `{messages:[{id, inquiry_id, channel, to, template, kind, subject, body, links, created_at}]}`, newest first; DELETE clears it |
| GET | `/api/dev/audit/{inquiry_id}` | — | `DEV_TOOLS=true` only: `{inquiry_id, events:[{seq, at, type, actor, payload}]}` (redacted) |

`ChatRequest`:
```json
{"type": "message", "text": "We run Bean Street, a specialty coffee brand"}
{"type": "action", "action": "select_malls", "payload": {"mall_ids": ["riyadh-mall-a"]}}
```

Test hooks: when `AGENT_MODE=scripted`, `POST /api/sessions` and `POST /api/cases/open` accept an `X-Test-Scenario` header naming a script in `backend/tests/e2e_scripts/`; the session then replays that script (intake tools on inquiry sessions, case tools on case-mode sessions). Unknown or missing headers leave `test_scenario` unset. It also accepts `X-Mock-Faults` (`service:kind[:count],…`; services `cr`, `email`, `otp`, `notifications`, `submit`, `status`, `storage`, `call_centre`, `llm` (the chat model); kinds `timeout`, `unavailable`, `rejected`) for faults in that session only; a bad spec is 400 `bad_mock_faults`. Both headers are ignored in `openai` mode.

Unknown session → 404 `session_not_found`. Sessions expire after 2 hours idle; a signed link (verification, resume) reaches an idle session again. A connected system that fails surfaces as 503 `<service>_<kind>`. Rate limits: 30 chat requests/min per session, 60/min per IP → 429 `rate_limited`.

## 7. SSE events

Each event is `event: <type>` + `data: <json>`.

| Event | Data | Frontend |
| --- | --- | --- |
| `token` | `{message_id, text}` | Append to the assistant message `message_id` (create it if new) |
| `ui_card` | `UiCard` | Insert after the current assistant message, or replace in place if `card_id` exists. After a follow-on (`inquiry_seq` ≥ 2) card ids carry the inquiry's number (`review~2`, `confirm-1~2`), so the earlier inquiry's cards stay as they were; actions send the id back as received |
| `draft` | `DraftSummary` | Replace draft state; flash and scroll to `changed_keys` |
| `message_remove` | `{message_id}` | Remove the assistant bubble with that id (guard retracted a rejected reply) |
| `done` | `{phase}` | Stop typing indicator, enable composer |
| `error` | `{code, message}` | Show a friendly error bubble with Retry |

At the start of each turn the frontend clears the previous `quick_replies` chips.

### `UiCard`
```json
{"card_id": "confirm-1", "card_type": "confirm_fields", "message_id": "m_12", "payload": {}}
```

| `card_type` | `payload` |
| --- | --- |
| `confirm_fields` | `{title, fields:[{key, label, display, source, confirmed, evidence}], all_confirmed}` (`evidence`: the user's words a derived value came from, shown as "from: '…'"; else null. `title` is "Same details as <reference>" for a follow-on prefill) |
| `mall_picker` | `{city:{id,label}, malls:[{id,name}], selected:[id], min_select:1, max_select}` (`max_select` = policy `max_malls_per_inquiry`, default 1) |
| `verification` | `{email:{masked, link_sent, verified, demo_token, resend_available_at}, mobile:{masked, code_sent, verified, attempts_left, code_length:4, resend_available_at} \| null, all_verified}` (`mobile` is null for a landline-only applicant; `demo_token` only when `EMAIL_LINK_DEMO`; `resend_available_at` is an ISO time while the resend cooldown or hourly cap applies, else null) |
| `document_upload` | `{docs:[{doc_type,label,required,uploaded,file_name,size_bytes}], numbers:[{key,label,value,editable,error}], required_uploaded, required_total, allowed_extensions (dotted, e.g. `.pdf`), max_mb}` |
| `review` | `{groups:[{title, rows:[{key,label,display,source,confirmed,required}]}], documents:[...], checks:Checks, can_submit, terms_accepted, blockers:[str]}` |
| `success` | `{reference, tracking_url, steps:[{label, detail, state}]}` (`tracking_url` = `<PUBLIC_BASE_URL>/inquiry/status/<reference>?t=<track token>`, the private tracking page) |
| `quick_replies` | `{options:[{label, text, action?: "send" \| "focus_input", placeholder?: string}]}` — default `action` is `send` |
| `form_mode` | `{active, message, next_step: "existing_account"\|"cr"\|"details"\|"verification"\|"documents"\|"review"\|"submitted", fields:[{key, label, kind: "text"\|"select", master_kind}], can_skip_cr}` (card id `form_mode`; `fields` are the required values still empty, saved with `edit_field`, `contact_number` saved as mobile or landline; `active: false` once the assistant is back) |
| `handoff` | `{phone, email, hours, short_ref, case_id, reason}` (call-centre details from `CALL_CENTRE_*`; `short_ref` is the reference, or `INQ-XXXXXX` before submit; `case_id` is empty when the case system was down) |

### `DraftSummary`
```json
{
  "phase": "collecting",
  "fields": [{"key": "company_name", "label": "Company name", "group": "company", "display": "Bean Street Trading Co.", "source": "verified", "confirmed": false, "required": true}],
  "documents": [{"doc_type": "company_profile", "label": "Company Profile", "required": true, "uploaded": false, "file_name": null, "size_bytes": null}],
  "checks": {"required_filled": 7, "required_total": 11, "unconfirmed": 2, "email_verified": false, "mobile_verified": false, "contact_verified": false, "required_docs_uploaded": 0, "required_docs_total": 2, "terms_accepted": false},
  "can_submit": false,
  "changed_keys": ["company_name", "company_address"],
  "follow_on_of": null
}
```
`follow_on_of` is the earlier reference on a follow-on inquiry; the chat shows a "New inquiry" divider when it changes.
Groups in order: company, brand, space, contact. Area shows as one row (`area`), rent as one row (`rent`), lease as one row.

## 8. Services (simulated Cenomi, `backend/app/services/`)

Every call goes through the gateway (`app/gateway/`): a timeout per service, four error kinds, fault injection (`MOCK_FAULTS`, `X-Mock-Faults`) and an audit record per call. With `DATA_DIR` set, each simulated system keeps its state across restarts (`<DATA_DIR>/mock_world/`), as a real one would.

| Interface | Simulated behaviour |
| --- | --- |
| `CrService.verify(cr) -> CrResult` | Scenario data `app/data/mock_world/cr_registry.json`: `1010123456` → new, "Bean Street Trading Co.", "King Fahd Road, Al Olaya, Riyadh" · `1010222222` → new, "Fawaz Alhokair Trading Co.", "King Fahd Road, Riyadh" · `1010333333` → new, Arabic company name and address · `1010000000` → existing · `1010999991` → timeout · `1010999992` → unavailable · any other valid number → new, no details |
| `EmailVerificationService.send_link(session, email, context)` / `verify(session, token)` / `verify_link(token)` / `demo_token(session)` | Issues a signed `verify_email` token (inquiry id, address fingerprint, nonce, expiry) and emails `<PUBLIC_BASE_URL>/inquiry/verify?t=<token>` (template `email_verification_link`). Only the latest link works, once. Logs "Email verification link sent" without the token |
| `OtpService.send(session, mobile, context)` / `verify(session, code)` | Mobile only. Code = `OTP_MOCK_CODE`, delivered to the outbox as an SMS (`sms_otp`); logs "OTP sent" without the code |
| `NotificationService.send(template, to, context, inquiry_id) -> message id` | Renders `app/notifications/templates/<template>.txt` (`kind`, `channel`, `subject`, `string.Template` body) into the outbox. Templates: `email_verification_link`, `sms_otp`, `resume_link`, `submission_email`, `submission_sms`, `call_centre_case` |
| `CallCentreService.create_case(inquiry_id, payload, reason, transcript_summary, short_ref, context) -> (case, created)` / `open_case(inquiry_id)` | Opens a case (`CC-NNNNNN`) a customer-care executive continues in the Tenant Admin Platform (§7.1.1 a2); one open case per inquiry. The mock keeps cases in `mock_world/cases.json` and emails each to `CALL_CENTRE_EMAIL` (template `call_centre_case`), so it shows in the dev inbox |
| `StorageService.save(session, doc_type, upload) -> DocumentRef` | Writes to `UPLOAD_DIR/<session>/<uuid><ext>`; never opens content |
| `SubmitService.submit(draft, master, idempotency_key) -> reference` / `lookup(key)` | `GEO-{unit code}-{6 random digits}`; the same key returns the same reference |
| `StatusService.get(reference)` | Known reference → `under_review`, stage `first_review`, owner role by product line (Regional Leasing Manager (Store), Regional Property Leasing Manager (Media / Specialty)); else 404 |
| `ResendLimiter` | Policy `resend`: `cooldown_seconds` between sends on a channel, at most `max_per_hour` per channel per inquiry; the first send is never delayed |
| `AuditLog.record(inquiry_id, type, actor, payload)` | Append-only, numbered, redacted at write (allowlist per event type; never codes, tokens, contact details, file names or message text). Types: `inquiry_created`, `user_message`, `ui_action`, `tool_called` (agent tools and service calls), `field_written`, `field_confirmed`, `guard_verdict`, `card_shown`, `verification_sent`, `verification_result`, `document_added`, `document_removed`, `submit_attempt`, `submit_result`, `notification_sent`, `error`, `handoff_created` (reason, case_id, created, via), `follow_on_started` (from_reference, inquiry_seq, reused_verification), `form_mode_entered` (kind), `form_mode_left`. Each model call is a `tool_called` record (layer `service`, name `llm.invoke`). `field_written` keeps `evidence` for derived values (never for personal fields) |

**Sessions** (`app/sessions.py`) keep `inquiry_seq` (1, then 2, 3… after follow-ons), the transcript (`{id, role, text}`) and the latest version of each card, for resume. With `DATA_DIR`, each session is saved after every turn, action, upload and verification and reloaded at start-up; the first turn after a restart gives the model the last 20 messages again, since the graph's checkpointer is in memory.

Unit codes: store `STR`, media `MED`, specialty `SPC`.

## 9. Seed data and policy

### Master data (`backend/app/data/master_data.json`)

Generated by `backend/scripts/generate_master_data.py` (deterministic; `--check` fails if the committed file is stale). Synthetic until Cenomi supplies its own (assumption 6). Shape:

```json
{
  "regions": [{"id": "central", "label": "Central", "label_ar": "المنطقة الوسطى"}, "… western, eastern"],
  "unit_types": [{"id": "store", "label": "Store", "label_ar": "متجر", "code": "STR"}, "… media MED, specialty SPC"],
  "sales_categories": [{"id": "fnb_cafe", "label": "Food & Beverage · Café", "label_ar": "أغذية ومشروبات · مقهى"}, "… 7 in all"],
  "cities": [{"id": "riyadh", "label": "Riyadh", "label_ar": "الرياض", "region": "central"}, "… 8 in all"],
  "malls": [
    {"id": "riyadh-mall-a", "name": "Riyadh Mall A", "name_ar": "الرياض مول أ", "city": "riyadh", "region": "central",
     "aliases": ["مول الرياض أ", "الرياض مول ا"]},
    "… 20 in all"
  ],
  "lease_periods": [{"id": "1y", "label": "1 year", "label_ar": "سنة واحدة"}, "…"],
  "rent_periods": [{"id": "monthly", "label": "Monthly", "label_ar": "شهري"}, "…"]
}
```

- **Ids are stable.** Today's ids (the 9 malls in Riyadh, Jeddah and Dammam, 3 cities, 7 categories) never change; new malls are in new cities (Buraidah, Makkah, Madinah, Al Khobar, Jubail).
- **Matching.** Mall matching uses the English name, the Arabic name and every alias.
- **Source.** `MasterDataSource` (`app/domain/master.py`): `SeedMasterDataSource` (this file) or `CenomiMasterDataSource` (stub until access; falls back to the seed), chosen by `MASTER_DATA_SOURCE`. Cached with a daily refresh; a failed refresh keeps the last good copy.
- The REST endpoint `GET /api/master/{kind}` keeps its response shape (no Arabic fields) and lists only the policy's product lines.

### Policy (`backend/app/policy/policy.yaml`)

Business rules, validated at start-up into `PolicyConfig` (`app/policy/config.py`); a bad file stops the app with a readable error (`PolicyError`), and so does a product line missing from master data. Read by the validators, `can_submit`, the cards and `verify_cr`; rendered into the prompt as the "Rules in force" block (`prompts.rules_in_force`). Keys:

| Key | Default | Read by |
| --- | --- | --- |
| `product_lines` | `[store, media, specialty]` | Unit type validator, `get_master_data`, `GET /api/master/unit_types` |
| `existing_tenant_policy` | `sign_in` (`allow_inquiry`: an existing CR continues with `cr_status="new"`) | `verify_cr` |
| `max_malls_per_inquiry` | `1` | `validate_malls`, `update_draft`, mall auto-fill, `mall_picker.max_select` |
| `phone.allowed_countries` | `any` (or calling codes, e.g. `["971"]`; +966 always allowed) | Phone normalisers, `classify_contact_number` |
| `verification` | `{email: link, mobile: otp}` (the only supported values) | Prompt block |
| `resend` | `{cooldown_seconds: 60, max_per_hour: 5}` | Step 19 |
| `documents.required` / `optional` | Company and Brand Profile required; the rest optional; every type listed once | `can_submit`, `documents_updated`, document card, review, draft checks |
| `duplicate_policy` | `warn` | Step 21b |
| `follow_on_reuse_hours` | `24` | Step 21b |

`faq.json`: `[{id, question, keywords:[...], answer}]`, 8–10 entries (answers are placeholders marked `[to be confirmed]` where facts are unknown):
process steps · review time · required documents · what a CR number is · what a VAT certificate is · what each unit type means · editing after submit · how to track an inquiry · why we verify the phone/email · what happens to uploaded documents.

## 10. Configuration (`backend/.env`)

| Variable | Default |
| --- | --- |
| `OPENAI_API_KEY` | — (required) |
| `OPENAI_MODEL` | — (required; any OpenAI chat model with tool calling) |
| `OPENAI_TEMPERATURE` | `0.6` |
| `ROUTER_MODEL` | — (defaults to `OPENAI_MODEL`; structured-output intent classifier) |
| `ROUTER_MIN_CONFIDENCE` | `0.6` (below this, or mid-intake, → `inquiry_intake`) |
| `OTP_MOCK_CODE` | `1234` |
| `EMAIL_LINK_DEMO` | `true` (the verification card carries the link token for a demo button) |
| `MAX_UPLOAD_MB` | `5` |
| `UPLOAD_DIR` | `./.uploads` |
| `SESSION_TTL_MINUTES` | `120` |
| `RATE_LIMIT_SESSION` | `30/minute` |
| `RATE_LIMIT_IP` | `60/minute` |
| `CORS_ORIGINS` | `http://localhost:5173` |
| `LOG_LEVEL` | `INFO` |
| `AGENT_MODE` | `openai`; `scripted` runs `ScriptedChatModel` for the Playwright e2e suite (never set in a deployed environment) |
| `POLICY_PATH` | — (the packaged `app/policy/policy.yaml`) |
| `MASTER_DATA_SOURCE` | `seed` (`cenomi` is a stub that falls back to the seed) |
| `INTEGRATIONS` | `mock` (the only tier until Cenomi gives access; `sandbox`/`live` refuse to start) |
| `DEV_TOOLS` | `false`; `true` mounts `/api/dev/outbox` and `/api/dev/audit/{id}` (refused unless `INTEGRATIONS=mock`) |
| `MOCK_FAULTS` | empty; `service:kind[:count],…` injects faults into the simulated systems |
| `DATA_DIR` | empty = memory only; a directory = restart-safe JSON snapshots of sessions, the simulated systems' state (outbox, submissions, links, OTP, sends) and the audit log |
| `PUBLIC_BASE_URL` | `http://localhost:5173` (links in emails and SMS) |
| `RESUME_TOKEN_SECRET` | `dev-only-change-me` (signs verification, resume and tracking links; set a real secret outside dev) |
| `EMAIL_LINK_TTL_HOURS` / `RESUME_TTL_DAYS` / `TRACK_TTL_DAYS` | `72` / `7` / `365` |
| `REVIEWER_CONSOLE` | `false`; `true` mounts `/api/review/*` (refused unless `INTEGRATIONS=mock`) |
| `YARDI_MAX_ATTEMPTS` | `3` (then the case is flagged for operations) |
| `PUBLIC_API_URL` | `http://localhost:8000` (links that hit the API, e.g. the mock Azure AD accept link) |
| `CASE_TTL_DAYS` | `30` (case links) |
| `FORM_MODE` | `false`; `true` (testing) treats the model as unavailable, so every turn runs in form mode |
| `CALL_CENTRE_PHONE` / `CALL_CENTRE_EMAIL` / `CALL_CENTRE_HOURS` | `+966 11 000 0000` / `leasing-callcentre@example.com` / `Sunday to Thursday, 9 am to 5 pm (Riyadh time)` — placeholders until Cenomi confirms; shown on the `handoff` card; mock cases are emailed to `CALL_CENTRE_EMAIL` |

Frontend: `VITE_API_BASE` (default `http://localhost:8000`), `VITE_MOCK` (`1` = run on fixtures), `VITE_E2E` (`1` = send the `X-Test-Scenario` header; e2e only).

## 11. Changes from the POC plan doc

- Submit and OTP verification moved from agent tools to UI actions, so the OTP code and consent never pass through the LLM.
- Added `show_mall_picker`, `suggest_replies` and the `confirm_card` / `edit_field` actions.
- `DraftSummary.changed_keys` drives the draft panel's highlight and auto-scroll.
- POC assumptions (Oct 2026, requirements §7.1.1): email verified by link and mobile by OTP as separate checks (`send_otp` → `send_verification`, `otp_input` card → `verification`, `otp_verified` → `email_verified` + `mobile_verified`); one mall per inquiry; international phone numbers accepted, OTP to mobile only.

## 12. Commands and CI

Test layers and when each runs: `docs/specs/testing-strategy.md`.

| Command | Runs |
| --- | --- |
| `make check-be` | `ruff check` and `ruff format --check` over `app` and `tests`; `mypy --strict` over `app` |
| `make check-fe` | ESLint, `tsc -b --noEmit`, Prettier `--check` (frontend) |
| `make check` | `check-be`, `check-fe` (`make lint` is an alias) |
| `make test-be` / `make test-fe` / `make test` | pytest / Vitest / both |
| `make test-agent` | `pytest tests/agent tests/scenarios tests/test_e2e_scripts.py` (moves to `pytest -m agent` in step 11d) |
| `make e2e-int` | Playwright `@scripted` suites, real frontend + backend, `AGENT_MODE=scripted` (`make e2e` is an alias) |
| `make eval-live` | `scripts/eval_live.py` with the real model; `GROUP=` is passed through for step 11d |
| `make e2e-live` | Playwright `@live` suites with the real model |
| `make ci` | `check`, `test`, `e2e-int` (run locally before every PR) |
| `make ci-remote` | `check`, `test` (what CI runs on every PR) |
| `make gate` | `ci`, `eval-live`, `e2e-live` |

CI: `.github/workflows/ci.yml` runs `backend` (`check-be`, `test-be`) and `frontend` (`check-fe`, `test-fe`) on every PR and push to `main`. Playwright runs locally (`make e2e-int`, `make e2e-live`; Playwright flags via `ARGS=…`), or in CI on demand from `e2e.yml` (`suite: scripted | live`). Nightly live runs need the repository variable `NIGHTLY_LIVE=true`. Step 11d (B1) adds `e2e-fe`, coverage, `scripts/` linting and the `eval-live` job.

## 13. Review lifecycle (L4, Day 4)

Contracts for [L4](specs/l4-outcome-assistance.md) at Day 4 depth. Code: `backend/app/workflow/` (models, machine, service, effects, store, contacts), `app/domain/case_brief.py`, `app/domain/payload.py`, `app/api/review.py`, `app/api/cases.py`, `app/api/case_cards.py`.

**Case** (`workflow/models.py`, one per submitted inquiry, keyed by its reference; JSON snapshots in `<DATA_DIR>/cases/`): `status` (`CaseStatus`: draft, submitting, submitted, first_review, reupload_requested, second_review, approved, sent_to_yardi, rejected, abandoned, redirected), `draft` (the inquiry as submitted; re-uploads replace documents), `review_queue {product_line, region, role}`, `requests [{id, kind: reupload|contacts|sales_data, status: open|fulfilled|withdrawn, doc_types, remarks, requested_by, requested_at, closed_at}]`, `decisions [{level, outcome, remarks, reason_category, by, at}]`, `tenant_contacts [TenantContact]` (`FieldValue` per name, email, mobile, landline; `same_as_primary`), `sales_data`, `document_history`, `onboarding.invitations`, `yardi {company_id, brand_id, lead_ref, sent_at, attempts, needs_operations}`, `events` (applied transitions), `effects_done`, `case_session_id`. Created on submit (audit `case_created`) and routed at once.

**State machine** (`workflow/machine.py`): `transition(case, event, actor=, now=)` is pure and implements every row of M0 §6; it raises `IllegalTransition(code)` with `illegal_transition`, `not_allowed`, `not_in_queue` or `invalid_payload`. Reviewer events need a reviewer whose role and regions match `review_queue`. `legal_events(case, actor)` lists what an actor can do now (the console's actions). `workflow/service.apply_event` is the only way a case changes: transition, save, audit `case_transition {event, from_status, to_status, by, outcome}` (refusals too), then effects.

**Routing:** policy `review_routing` maps the unit type to a role (store → `rlm_store`, media → `rplm_media`, specialty → `rplm_specialty`); the region is the mall's region in master data.

**Effects** (`workflow/effects.py`, inline, keyed `(case, event seq, effect)`, audit `effect_run`; a failure is audited and never rolls back the transition):

| Event | Effects |
| --- | --- |
| `routed` | `review_assigned` → the queue's reviewers |
| `reupload_requested` | `reupload_request` → applicant, with a case link for the request |
| `documents_resubmitted` | `reupload_received` → reviewers |
| `rejected` | `inquiry_rejected` → applicant (remarks, policy `after_rejection`) |
| `approved_first` | Azure AD invite of the primary contact (role `primary_contact`) unless `has_account`; `first_level_approved`; a system `contacts_requested` when policy `auto_request_contacts_after_first_approval` |
| `contacts_requested` / `sales_data_requested` | `contacts_request` / `sales_data_request` → applicant, with a case link |
| `contacts_provided` / `sales_data_provided` | `contacts_received` / `sales_data_received` → reviewers |
| `request_withdrawn` | `request_withdrawn` → applicant |
| `approved` | invite each additional contact without an account (role = contact role); `inquiry_accepted`; `send_lead` to Yardi (`lead:<reference>`), each failure a `yardi_failed` event, up to `YARDI_MAX_ATTEMPTS`, then `needs_operations` |

**Applicant actions** (case chats only, §4 table style):

| Action | Payload | Does | Note |
| --- | --- | --- | --- |
| `resubmit_documents` | `{}` | Every requested document re-uploaded after the request → `documents_resubmitted` | `documents_resubmitted`, or `resubmit_blocked <doc_types>` (the re-upload card is re-sent) |
| `submit_contacts` | `{}` | Pressing Send accepts the values on the contacts card (`confirm_contacts`); required roles complete → `contacts_provided` | `contacts_submitted`, or `contacts_blocked <reasons>` |
| `submit_sales_data` | `{}` | A `sales_data` file uploaded after the request → `sales_data_provided` | `sales_data_submitted`, or `sales_data_blocked missing_file` |

Contacts being collected live on the case session (`Session.contacts_draft`); `workflow/contacts.write_contacts(current, entries, primary_draft)` is the deterministic writer for the case agent's `update_contacts` tool (entries `{role, first_name?, last_name?, email?, contact_number?, same_as_primary?, source?}`; "that's me" copies the primary contact as `verified`, unconfirmed; Arabic digits normalised). `contacts_blockers` lists `missing_contact:<role>`, `incomplete_contact:<role>`, `unconfirmed_contact:<role>`.

**Case links:** token purpose `case` (subject the reference, `data.r` the request id, `CASE_TTL_DAYS`); links `<PUBLIC_BASE_URL>/inquiry/case?t=…`. `POST /api/cases/open {token}` accepts a `case` or `track` token, reopens the case's chat (`Session.mode = "case"`, `case_id`) or starts one seeded with the submitted inquiry, adds a short assistant message, and returns the `POST /api/sessions` shape with a `case_status` card and the card for each open request. 400 `token_invalid` / `token_expired`; 404 `inquiry_not_found`.

**Cards:**

| `card_type` | `payload` |
| --- | --- |
| `case_status` | `{reference, status, stage: submitted\|first_review\|second_review\|outcome, stage_label, owner_role, last_change, open_requests:[{id, kind, label, remarks, doc_types, requested_at}], outcome: approved\|rejected\|null, outcome_remarks, next_step}` (card id `case_status`) |
| `document_upload` | gains `mode: "intake"\|"reupload"`, `requested_doc_types`, `remarks`; in re-upload mode `docs` lists only the requested types and `uploaded` means uploaded after the request; the button is Resubmit (`resubmit_documents`) |
| `contacts` | `{request_id, remarks, rows:[{role, label, required, first_name, last_name, email, phone, source, confirmed, same_as_primary}], can_submit, blockers}` (card id `contacts`) |
| `sales_data_upload` | `{request_id, remarks, uploaded, file_name, size_bytes, allowed_extensions, max_mb}`; upload with `doc_type=sales_data` (card id `sales_data`) |

**Documents:** `DocType.sales_data` exists only for case chats (`POST …/documents` with it in an intake chat is 400 `unknown_doc_type`); it isn't in the intake checklist or the policy's document lists. In a case chat, an upload returns the re-upload or sales-data card.

**Reviewer console API** (`REVIEWER_CONSOLE=true`, `INTEGRATIONS=mock`; header `X-Reviewer-Id`, unknown → 401; a case outside the reviewer's queue → 404):

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/review/reviewers` | Reviewers for the mock sign-in `[{id, name, role, regions, manager}]` |
| GET | `/api/review/me` | The signed-in reviewer |
| GET | `/api/review/cases?waiting_on=` | Queue `[{reference, brand, company, mall, product_line, region, status, stage_label, waiting_on, age_days, last_change, open_requests, possible_duplicate, follow_on_of, needs_operations}]` |
| GET | `/api/review/cases/{reference}` | `{brief: CaseBrief, timeline:[{at, actor, type, summary}], legal_actions, approval_blockers, rejection_categories, reupload_doc_types}` |
| GET | `/api/review/cases/{reference}/documents/{file_id}` | The file |
| GET | `/api/review/yardi/companies?q=` | Active Yardi companies by the first word of the name `[{id, name}]`: the options for `relink_company` |
| GET | `/api/review/yardi/companies/{company_id}/brands` | `[{id, name, source}]` (`lease` \| `proposal`): the options for `relink_brand`. 404 `company_not_found` |
| POST | `/api/review/cases/{reference}/actions` | `{action, payload}` → the updated detail. Actions: `request_reupload {doc_types, remarks}`, `reject {remarks, reason_category?}`, `approve_first`, `request_contacts {remarks?}`, `request_sales_data {remarks?}`, `withdraw_request {kind}`, `relink_company {company_id}`, `relink_brand {brand_id}`, `remove_contact {role}`, `approve`. Errors: 400 `unknown_action` / `invalid_payload`, 403 `not_in_queue` / `not_allowed`, 409 `illegal_transition` |

**Case brief** (`domain/case_brief.py`, deterministic): applicant, company, brand, product line, mall, region, CR status, every field with source, confirmation and evidence, verification, documents with replaced versions, sales data, contacts, requests, decisions, follow-on, Yardi link, stage ages, and a next-decision checklist from the policy.

**Services:** `ReviewerDirectory` (`data/mock_world/reviewers.json`: a reviewer per role × region, a manager per role, call-centre and guest-service staff), `IdentityService` (`invite(email, role, context)` sends `azure_ad_invitation` with an accept link `<PUBLIC_API_URL>/api/dev/identity/accept/{id}`; `has_account`; `status`; `accept`; seeded accounts in `data/mock_world/identity.json`), `YardiService` (`search_companies` by the first word, active only; `brands_for_company`; `send_lead(payload, idempotency_key)` → `YL-NNNNNN`; `data/mock_world/yardi.json`). Gateway services `identity`, `yardi`.

**Status page:** `GET /api/inquiries/{reference}?t=` follows the case: `status` is `under_review`, `approved`, `sent_to_yardi` or `rejected`; stages Submitted → First review → Lead — second review → Outcome; `owner_role` from the queue; `waiting_on_you` lists open requests ("Re-upload documents", "Add company contacts", "Upload estimated sales data").

**Policy:** `review_routing`, `second_level_contacts {required, optional}`, `rejection_categories`, `after_rejection`, `require_contacts_before_approval`, `auto_request_contacts_after_first_approval`.
