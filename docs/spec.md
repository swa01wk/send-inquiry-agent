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

### Durable inquiry (`backend/app/store/models.py`, M0 §5)

The **inquiry** is the durable case; a **session handle** (`session_id` in the API) points at the current inquiry. In M0 they start as the same UUID; after `start_follow_on` a new inquiry row is created and the handle is repointed while the submitted row stays `submitted`.

`Inquiry` carries `InquiryDraft`, card bookkeeping (`cards_shown`, `confirm_card_keys`, `card_counter`), workflow `InquiryStatus`, optimistic `version`, `submit_key`, `reference`, and a `session_state` jsonb blob (transcript, cards, turn counters, form mode, and similar). Postgres columns match [m0-modular-core.md §5.3](specs/m0-modular-core.md); `inquiry_events.inquiry_id` is nullable for case-scoped events (step 15).

`InquiryRepository` (`memory` | `postgres`): `create(*, channel=…)`, `get`, `save` (bumps `version`; raises `VersionConflict`), `touch` (only `last_seen_at` / `expires_at`, no version bump), `acquire_turn` / `renew_turn` / `release_turn`, `purge_expired`. `SessionStore` adapts the repository; `begin_turn` returns a lease id and `end_turn(session_id, lease_id)` releases it. A failed save after one reload raises `turn_conflict` (409 or SSE `error` with code `turn_conflict`).

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

**Space values as people write them.** Area and rent accept a whole number written the usual ways — `250,000`, `250k`, `30 sqm`, `about 30`, `up to 250,000 SAR per year` — and keep only the number (`validation._normalised_number`); `30.5` or words still fail. `lease_period` and `rent_period` accept the id, its label or a common phrase (`3 years`, `three years`, `3-year` → `3y`; `per year`, `annual` → `yearly`; `a month` → `monthly`) and store the id (`validation._period_id`); a period not in master data (`4 years`, `weekly`) still fails. A lease may also be a number of years (`3`) or months (`36 months`).

**`area` and `rent` pseudo keys.** `write_fields` (so `update_draft`) also accepts `area` and `rent`, the names of the summary rows, which the model uses too (2 Nov live-eval trace). One value or a range (`30 sqm` → 30–30; `25-35 sqm`; `200-250k`) is split into the min and max fields and each side goes through its own validator. A one-sided rent is the budget cap (`rent_max`) unless it says "from" or "at least" (`rent_min`). "Per year" or "a month" in a rent fills `rent_period` unless the same write sets it. A derived `area` or `rent` is shown on the confirm card as the fields it wrote.
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
4. `unconfirmed_field:<key>`: each required or provided field whose source is derived/verified and `confirmed` is false. Document numbers (the documents group: VAT, national ID, national address) are not counted; the draft summary's `checks.unconfirmed` counts the same way.
5. `email_not_verified`, then `mobile_not_verified` (only when a mobile is given).
6. `missing_document:<doc_type>`: each required document not uploaded.
7. `terms_not_accepted`.

### Phase (`domain/summary.py: compute_phase`)

`existing_account` if cr existing → `submitted` if reference → `gate` if cr unknown → `collecting` if any blocker 3–4 → `verifying` if any blocker 5 → `documents` if blocker 6 → `review`.

### What's left (`domain/rules.py: remaining_steps`)

The phase is a single label; the user can still do things in any order (upload documents before opening the email link, correct a value after the verification card). `remaining_steps(draft)` lists everything still needed before submit, from the blockers, in the usual order: `cr`, `fields` (blockers 3–4), `verify_email`, `verify_mobile`, `documents`, `terms`. Empty once submitted or for an existing account. The agent's hint (`bundles.still_needed_line`), the guard (§5 rule 7), the `documents_complete` note and the draft checks (`remaining`, `next_step`) all read it, so nothing points to Submit while anything but the terms is left.

## 3. Agent tools (`backend/app/agent/tools.py`)

All tools return a short factual string for the LLM. Tools that change state return `Command(update=...)` with a `ToolMessage`, and emit `draft` (and cards) via the stream writer.

| Tool | Args | Behaviour |
| --- | --- | --- |
| `verify_cr` | `cr_number: str` | Validate format; call `CrService.verify`. Existing → `cr_status="existing"`. New → `cr_status="new"`, write `cr_number` (user) and any returned `company_name`/`company_address` as `verified`, unconfirmed; emit a `confirm_fields` card for them. |
| `skip_cr` | — | Only after the user agreed to skip. `cr_status="skipped"`. |
| `record_cr_answer` | `has_cr: bool` | Demo feedback §3.1, self-service only and only under policy `public_cr_check: ask_then_sign_in` (otherwise "Not used in this chat"). The user's typed answer to "Do you have a CR?"; same handler as the `cr_answer` action. `true` → `cr_status="existing"` (no CR number stored), `cr_question` card marked answered, `sign_in_prompt` card (reason `has_cr`), audit `inquiry_redirected {reason: has_cr}`; `false` → `cr_status="skipped"` and the company name and address are collected. Not in `ASSISTED_TOOLS`. Under `ask_then_sign_in`, `verify_cr` on the public page checks nothing and says lookups are off |
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

**Quiet actions.** When the card already shows the outcome, no agent turn runs: the endpoint streams the action's `ui_card` and `draft` events, then `done`, and adds no reply and no note to the graph. Quiet: `otp_failed` with attempts left, a manual `resend_email_link` or `resend_otp` (sent or `resend_throttled`), `email_verified` or `mobile_verified` while the other channel is still pending, and `document_number_set`. Everything else runs the graph as below — including `verification_complete`, the automatic resend after the last wrong code, `documents_complete`, errors and submit.

| Action | Payload | Backend does, then runs the graph with a `[ui_event]` note |
| --- | --- | --- |
| `select_malls` | `{mall_ids: list[str]}` | Validate (1 to `max_malls_per_inquiry` malls); write `malls` as user, confirmed. Note: `malls_selected: <name>` or `malls_invalid <code>` |
| `verify_email` | `{token: str}` | `EmailVerificationService.verify`; valid only for the link sent to the current email. Sets `email_verified`. Note: `email_verified` (+ ` verification_complete` when nothing else is pending, + ` documents_complete` when the required documents are already uploaded) or `email_link_invalid`. The token is never added to messages. |
| `resend_email_link` | `{}` | New link to the current email (the old one stops working), within the resend limits (policy `resend`). Note: `email_link_resent`, `resend_throttled <seconds>` or `service_error email <kind>` |
| `submit_otp` | `{code: str}` | Only for the code sent to the current mobile. `OtpService.verify`; on success `mobile_verified=True`; on failure decrement attempts (0 → auto resend within the resend limits, reset to 3). Note: `mobile_verified` (+ ` verification_complete`, + ` documents_complete` as for `verify_email`), `otp_failed attempts_left=N`, `otp_resent`, `resend_throttled <seconds>`, `service_error otp <kind>` or `otp_not_sent`. The code is never added to messages. |
| `resend_otp` | `{}` | Resend to the mobile within the resend limits, reset attempts. Note: `otp_resent`, `resend_throttled <seconds>`, `service_error otp <kind>` or `otp_send_blocked no_mobile` |
| `edit_field` | `{key, value}` | Validate; write as user, confirmed. Note: `field_edited <key>`. Once the review card is on screen, it is re-sent (same card id, updated in place); so are `confirm_card` and `documents_updated`, and the guard re-sends it after a turn that changed the draft |
| `confirm_card` | `{card_id}` | Confirm all fields on that confirm card. Note: `fields_confirmed <keys>`; `fields_already_confirmed` when everything on the card is already confirmed (the card is re-sent; not a failure); `confirm_failed` for an unknown card; `confirm_failed stale_card` for a card of an earlier inquiry in the chat |
| `accept_and_submit` | `{terms_accepted: true}` | **Submit once:** if a reference exists, re-emit the same `success` card (note `submitted reference=<ref> (repeat)`). Otherwise set `terms_accepted`; run `can_submit`; if clear, `SubmitService.submit` with idempotency key `inq:<session_id>:v<inquiry_seq>` (`v1`, then `v2`… for follow-on inquiries) → set `reference`, send `submission_email` (verified email) and `submission_sms` (verified mobile), emit `success` with the private `tracking_url`. Note: `submitted reference=<ref>`, `submit_blocked <blockers>`, `submit_pending timeout\|unavailable` (nothing lost; Submit again returns the same reference) or `submit_failed rejected\|invalid` |
| `documents_updated` | `{}` or `{doc_type}` | Recompute required documents from the draft. Note: `documents_complete` (+ ` still_needed=<items>` when `remaining_steps` has more than documents and terms, e.g. `still_needed=verify_email`; the `fields` step is spelled out as the missing field keys and `confirm:<key>` for unconfirmed ones, e.g. `still_needed=brand_name_ar`) or `documents_pending <doc_types>`. With `doc_type` (the profile just uploaded; the frontend sends it when the upload's `fields_filled` or `mismatches` is non-empty, demo feedback §3.7), the note starts with `document_fields <doc_type> filled=<keys>` and one `document_mismatch <field>` line per difference (` source=cenomi_record` when the draft value is `verified`, e.g. a signed-in tenant's company from Yardi, R4): field names only, never a value from the document |
| `set_document_number` | `{key, value}` | Validate and write the document number field as user, confirmed. Note: `document_number_set <key>` or `document_number_invalid <key> <code>` |
| `cr_check` | `{cr_number}` | The CR check from a card (form mode): same rules as `verify_cr` (existing account, `allow_inquiry`, or new with the company name and address prefilled on a confirm card). Note: `cr_checked existing\|existing_allowed\|new`, `cr_invalid <code>`, `cr_already_done` or `service_error cr <kind>` |
| `cr_skip` | `{}` | Skip the CR (form mode). Note: `cr_skipped` or `cr_already_done` |
| `cr_answer` | `{has_cr: bool}` | Demo feedback §3.1: the `cr_question` card's buttons (self-service, `public_cr_check: ask_then_sign_in`). Same as `record_cr_answer`; Yes also sets `Session.closed = "redirected_to_sign_in"`. Note: `cr_answer yes\|no`, `cr_already_done`, `cr_answer_invalid` (not a boolean) or `cr_answer_off`. Under `ask_then_sign_in`, `cr_check` on the public page answers `cr_lookup_off` |
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
2. Attach the card for a phase the user just entered if it hasn't been shown: `documents` → `document_upload`, `review` → `review`. (`verifying` cards come from `send_verification`.) On the upload path (the user said they'll upload the profiles, after CR = no), `document_upload` is attached in `collecting` or `verifying` too: the company and brand fields come from the profiles, so the phase can't reach `documents` before they're uploaded (`_documents_card_due` in `guard.py`). A signed-in tenant's new-brand question (the turn after `basic_info_confirmed`, no brand yet) gets `quick_replies` "I'll type it" / "I'll upload the Brand Profile" when the agent didn't suggest them (`_new_brand_choice_due`); the upload choice then brings `document_upload` the same way.
3. If the reply claims the inquiry was submitted (`claims_submission` in `guard.py`: "has been submitted", "I've sent your inquiry", "your reference is …"; conditional mentions such as "once the inquiry is sent" don't count) while `reference` is None → add a system note and route back to `agent` once. After a follow-on, a reply about the earlier inquiry (it names `follow_on_of`, or `start_follow_on` ran this turn) is allowed.
4. If phase is `existing_account`, ensure the reply points to Sign In.
5. Doubt: when the user doubts a derived or prefilled value ("not sure about the category", «مو متأكد من الفئة»), that field is un-confirmed (values the user typed are left alone). Doubt is attributed to the nearest field named after the doubt phrase, else before it, in the same sentence.
6. When `malls` is empty and the user's message names exactly one seed mall (same mention rules as `filter_mall_ids`), write that mall id as `user` (naming two or more writes nothing, so the agent asks which one) (see `fill_mentioned_malls` in `mall_match.py`). Also runs after `update_draft` when malls were omitted. Mall mention: the full normalised mall name (or optional `aliases` on a mall in master data) must appear as whole words in the user message (`\b` boundaries, optional leading “the”); city or country tokens alone do not match.
7. Not ready to submit (`_premature_submit_note`): after collection, if verification or documents are still open (`remaining_steps`) and the reply sends the user to Submit ("last step", "everything's in", "press Submit", "submit when you're ready", "the review card") without naming what's open (email or link; code or SMS; documents or upload) → add a note with `still_needed_line` and route back to `agent` once. Not in assisted mode.

## 6. REST API (`/api`)

Errors: `{"error": {"code": str, "message": str}}` with 4xx/5xx.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{status:"ok"}` |
| POST | `/api/sessions` | — | `{session_id, messages:[{id, role:"assistant", text}], cards:[UiCard], draft:DraftSummary}` (fixed welcome, see design spec) |
| POST | `/api/sessions/resume` | `{token}` (purpose `resume`) | Same shape as `POST /api/sessions` for the same `session_id`: the last 20 messages (`role` `user` or `assistant`), the latest version of each card, the draft. 400 `token_invalid` / `token_expired`; 404 `inquiry_not_found` |
| POST | `/api/verifications/email` | `{token}` (purpose `verify_email`, from the emailed link) | `{status:"verified", session_id, email_masked, resume_token}`. 400 `token_invalid` / `token_expired` / `token_used` / `email_changed`. A link works once; only the latest link works. Honors `X-Test-Scenario` in scripted mode for `complete` tokens (applicant session only) |
| POST | `/api/sessions/{id}/chat` | `ChatRequest` | `text/event-stream` (section 7) |
| POST | `/api/sessions/{id}/documents` | multipart: `doc_type`, `file` | `{document, card: UiCard(document_upload), draft, fields_filled: [key], mismatches: [key]}` · 400 `invalid_extension` / `too_large` / `unknown_doc_type` · 409 `turn_in_progress` only if a chat turn is still running after `UPLOAD_TURN_WAIT_SECONDS` (default 30; the upload and the removal wait for it first). Intake only: a Company or Brand Profile fills empty fields from `DocumentReview.fields` (`source: derived`, unconfirmed, evidence `"<label>: <file name>, uploaded <time>"`; `domain/document_fill.py`), never overwrites a value, and lists the fields it filled on `DocumentRef.filled_fields`. A replaced profile first takes back the values it filled that are unchanged (ADR-R4). `mismatches`: fields this profile disagrees with (`domain/document_checks.py`; never a blocker). Audit `document_fields_filled` / `document_mismatch` `{doc_type, fields}` |
| DELETE | `/api/sessions/{id}/documents/{doc_type}` | — | `{card, draft}`. Intake: a removed profile takes back the values it filled (ADR-R4) |
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

Test hooks: when `AGENT_MODE=scripted`, `POST /api/sessions`, `POST /api/callcentre/inquiries`, `POST /api/tenant/opportunities/{id}/inquiry`, and `POST /api/cases/open` accept an `X-Test-Scenario` header naming a script in `backend/tests/e2e_scripts/`; the session then replays that script (intake tools on inquiry sessions, assisted tools on assisted sessions, case tools on case-mode sessions). `POST /api/verifications/email` with a `complete` token also accepts the header and sets `test_scenario` on the **new applicant** session (not the staff session). Unknown or missing headers leave `test_scenario` unset. Reopening a case chat with a different script starts that script from its first step; the same script carries on. It also accepts `X-Mock-Faults` (`service:kind[:count],…`; services `cr`, `email`, `otp`, `notifications`, `submit`, `status`, `storage`, `call_centre`, `llm` (the chat model); kinds `timeout`, `unavailable`, `rejected`) for faults in that session only; a bad spec is 400 `bad_mock_faults`. Both headers are ignored in `openai` mode.

Unknown session → 404 `session_not_found`. Sessions expire after 2 hours idle; a signed link (verification, resume) reaches an idle session again. A connected system that fails surfaces as 503 `<service>_<kind>`. Rate limits: 30 chat requests/min per session, 60/min per IP → 429 `rate_limited`.

## 7. SSE events

Each event is `event: <type>` + `data: <json>`.

| Event | Data | Frontend |
| --- | --- | --- |
| `token` | `{message_id, text}` | Append to the assistant message `message_id` (create it if new) |
| `ui_card` | `UiCard` | Insert after the current assistant message, or replace in place if `card_id` exists. After a follow-on (`inquiry_seq` ≥ 2) card ids carry the inquiry's number (`review~2`, `confirm-1~2`), so the earlier inquiry's cards stay as they were; actions send the id back as received |
| `draft` | `DraftSummary` | Replace draft state; flash and scroll to `changed_keys` |
| `message_remove` | `{message_id}` | Remove the assistant bubble with that id (guard retracted a rejected reply) |
| `done` | `{phase}` | Stop typing indicator, enable composer. Sent only after the session is saved and the turn lease released, so the client's next request (a queued action) never gets 409 `turn_in_progress`. A save conflict's `error` follows it. |
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
| `form_mode` | `{active, message, next_step: "existing_account"\|"cr"\|"details"\|"verification"\|"documents"\|"review"\|"submitted", fields:[{key, label, kind: "text"\|"select", master_kind}], can_skip_cr, cr_question}` (card id `form_mode`; `cr_question: true` when the CR step is the `cr_question` card; `fields` are the required values still empty, saved with `edit_field`, `contact_number` saved as mobile or landline; `active: false` once the assistant is back) |
| `cr_question` | `{prompt, yes_label, no_label, answered: "yes"\|"no"\|null}` (card id `cr_question`; demo feedback §3.1). Under `public_cr_check: ask_then_sign_in`, `POST /api/sessions` returns it on the self-service channel in place of the welcome quick replies, with the welcome text asking whether the company has a CR; the buttons send `cr_answer`. In form mode it is the CR step, and the `form_mode` payload carries `cr_question: true` with no CR input |
| `sign_in_prompt` | `{message, sign_in_url, button_label}` — `sign_in_url` is `<PUBLIC_BASE_URL>/tenant` (sign in, then Leasing Opportunities). The message depends on why it's shown: an existing CR found by a lookup, or a Yes to "Do you have a CR?" |
| `handoff` | `{phone, email, hours, short_ref, case_id, reason}` (call-centre details from `CALL_CENTRE_*`; `short_ref` is the reference, or `INQ-XXXXXX` before submit; `case_id` is empty when the case system was down) |

### `DraftSummary`
```json
{
  "phase": "collecting",
  "fields": [{"key": "company_name", "label": "Company name", "group": "company", "display": "Bean Street Trading Co.", "source": "verified", "confirmed": false, "required": true}],
  "documents": [{"doc_type": "company_profile", "label": "Company Profile", "required": true, "uploaded": false, "file_name": null, "size_bytes": null}],
  "checks": {"required_filled": 7, "required_total": 11, "unconfirmed": 2, "email_verified": false, "mobile_verified": false, "contact_verified": false, "required_docs_uploaded": 0, "required_docs_total": 2, "terms_accepted": false, "remaining": ["fields", "verify_email", "verify_mobile", "documents", "terms"], "next_step": "fields"},
  "can_submit": false,
  "changed_keys": ["company_name", "company_address"],
  "follow_on_of": null
}
```
`checks.remaining` is `remaining_steps(draft)` and `checks.next_step` its first item (`null` when nothing is left); the UI uses them for the step tabs and the next-step prompt, so a stage done out of order still shows as done.
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
| `DocumentReviewService.review(ref, content) -> DocumentReview` | Demo feedback §3.3; the only place document content is checked (golden rule 5). Called through the gateway (service `document_review`, timeout 15 s) after a Company Profile or Brand Profile upload; the result is stored on `DocumentRef.review` = `{status: done\|pending\|failed, expiry_date, fields: {key: {value, page}}, checked_at}` (typed values only, no document text). A timeout or outage stores `pending` and the upload still succeeds. Audit `document_reviewed {doc_type, status, has_expiry}`. The mock (`MockDocumentReviewService`) answers from the file name: `expired` → 30 days ago, `soon` → in 7 days, otherwise in 365 days; `timeout` / `unavailable` → the matching outage. Fields (day R3): from `mock_world/document_review.json`, keyed by file name (`company_profile_match.pdf`, `company_profile_mismatch.pdf`, `brand_profile_match.pdf`, `company_profile_injection.pdf`); company profile → `company_name`, `company_address`; brand profile → `brand_name_en`, `sales_category` (a master-data id). Any other file gives no fields |
| `SubmitService.submit(draft, master, idempotency_key) -> reference` / `lookup(key)` | `GEO-{unit code}-{6 random digits}`; the same key returns the same reference |
| `StatusService.get(reference)` | Known reference → `under_review`, stage `first_review`, owner role by product line (Regional Sales Manager (Store, Office), Regional Product Line Manager (Media / Specialty); `workflow/labels.py`, flow v2 §3.5); else 404 |
| `ResendLimiter` | Policy `resend`: `cooldown_seconds` between sends on a channel, at most `max_per_hour` per channel per inquiry; the first send is never delayed |
| `AuditLog.record(inquiry_id, type, actor, payload)` | Append-only, numbered, redacted at write (allowlist per event type; never codes, tokens, contact details, file names or message text). Types: `inquiry_created`, `user_message`, `ui_action`, `tool_called` (agent tools and service calls), `field_written`, `field_confirmed`, `guard_verdict`, `card_shown`, `verification_sent`, `verification_result`, `document_added`, `document_removed`, `submit_attempt`, `submit_result`, `notification_sent`, `error`, `handoff_created` (reason, case_id, created, via), `follow_on_started` (from_reference, inquiry_seq, reused_verification), `form_mode_entered` (kind), `form_mode_left`, `document_reviewed` (doc_type, status, has_expiry), `document_fields_filled` (doc_type, fields), `document_mismatch` (doc_type, fields), `identity_revoked` (invitation_id, role; flow v2 §3.6). Each model call is a `tool_called` record (layer `service`, name `llm.invoke`). `field_written` keeps `evidence` for derived values (never for personal fields) |

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
| `public_cr_check` | `ask_then_sign_in` (demo feedback §3.1; self-service default). `lookup` remains for scripted scenarios not listed in `CR_QUESTION_SCRIPTS` and for tests that override policy: the self-service chat asks "Do you have a CR?" and never takes, checks or repeats a CR number (a typed one is replaced with `[CR number removed]` before the transcript, audit and model, and counts as Yes). Staff channels keep the lookup | `cr_question.cr_question_active`, sessions, chat, `verify_cr`, `cr_check`, `record_cr_answer`, form mode, bundle hint |
| `first_level_review_role` | `lease_admin` (null: the `review_routing` role does both levels) | Routing (`ReviewQueue.first_role`), the state machine's actor check, effects, console, status |
| `document_approval` | `true`: the first-level reviewer approves or rejects each document; `approved_first` waits for them (demo feedback §3.4) | `workflow/documents.document_blockers`, `legal_events`, brief |
| `document_expiry` | `{expiring_soon_days: 14, doc_types: [company_profile, brand_profile]}` | `workflow/expiry`, `document_approved`, brief |
| `contacts` | `{approval_required: true, ask_signatory: true, applicant_signatory_needs_approval: false}` (demo feedback §3.5) | `contacts_provided`, `approval_blockers`, `legal_events`, contacts and signatory cards, `contacts_received` effect |
| `identity.revoke_on_lead_rejection` | `true`: Reject Lead revokes the first-approval invitation (flow v2 §3.6) | effect `revoke_primary` |
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
| `LLM_PROVIDER` | — (`openai` \| `azure`; unset → `azure` if `AZURE_OPENAI_ENDPOINT` is set, else `openai`) |
| `OPENAI_API_KEY` | — (required when `LLM_PROVIDER=openai`) |
| `OPENAI_MODEL` | — (OpenAI chat model with tool calling; alias for deployment name when `LLM_MODEL` unset) |
| `LLM_MODEL` | — (model or Azure deployment name; wins over `OPENAI_MODEL` when both set) |
| `OPENAI_TEMPERATURE` / `LLM_TEMPERATURE` | `0.6` (`LLM_TEMPERATURE` wins; empty = omit temperature, needed for GPT-5) |
| `LLM_REASONING_EFFORT` | — (`minimal` \| `low` \| `medium` \| `high`; reasoning models only) |
| `AZURE_OPENAI_ENDPOINT` | — (required when `LLM_PROVIDER=azure`) |
| `AZURE_OPENAI_API_KEY` | — (required when `LLM_PROVIDER=azure`) |
| `AZURE_OPENAI_API_VERSION` | `2025-04-01-preview` |
| `ROUTER_MODEL` | — (defaults to the LLM model; structured-output intent classifier) |
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
| `DEMO_SEED` | `false`; with `DEV_TOOLS`, seeds the three demo cases (`app/demo_seed.py`) on start when there is no case, and after `POST /api/dev/reset`. `make demo` sets it. The seeds use their own personas, so nothing reaches the live demo applicant's inbox |
| `MOCK_FAULTS` | empty; `service:kind[:count],…` injects faults into the simulated systems |
| `DATA_DIR` | empty = memory only; a directory = restart-safe JSON snapshots of sessions, the simulated systems' state (outbox, submissions, links, OTP, sends) and the audit log |
| `STATE_BACKEND` | `memory` (`postgres` for docker-compose dev) |
| `DATABASE_URL` | — (required when `STATE_BACKEND=postgres`; SQLAlchemy URL `postgresql+psycopg://…`) |
| `TEST_DATABASE_URL` | — (pytest `@pytest.mark.postgres` only) |
| `TURN_LEASE_SECONDS` | `120` |
| `DRAFT_RETENTION_DAYS` | `30` (`expires_at = last_seen_at + retention`; refreshed on `touch`) |
| `AGENT_HISTORY_MESSAGES` | `40` (model input trimmed at user / `[ui_event]` turn boundaries) |
| `PUBLIC_BASE_URL` | `http://localhost:5173` (links in emails and SMS) |
| `RESUME_TOKEN_SECRET` | `dev-only-change-me` (signs verification, resume and tracking links; set a real secret outside dev) |
| `EMAIL_LINK_TTL_HOURS` / `RESUME_TTL_DAYS` / `TRACK_TTL_DAYS` | `72` / `7` / `365` |
| `REVIEWER_CONSOLE` | `false`; `true` mounts `/api/review/*` (refused unless `INTEGRATIONS=mock`) |
| `YARDI_MAX_ATTEMPTS` | `3` (then the case is flagged for operations) |
| `PUBLIC_API_URL` | `http://localhost:8000` (links that hit the API, e.g. the mock Azure AD accept link) |
| `CASE_TTL_DAYS` | `30` (case links) |
| `FORM_MODE` | `false`; `true` (testing) treats the model as unavailable, so every turn runs in form mode |
| `CALLCENTRE_CONSOLE` | `false`; `true` mounts `/api/callcentre/*` (refused unless `INTEGRATIONS=mock`) |
| `TENANT_PORTAL` | `false`; `true` mounts `/api/tenant/*`, the simulated Tenant Central (refused unless `INTEGRATIONS=mock`) |
| `PROACTIVE_ENABLED` | `false`; `true` runs the proactive tick in the background (L5, §14) |
| `PROACTIVE_TICK_SECONDS` | `60`; how often the background tick runs |
| `CALL_CENTRE_PHONE` / `CALL_CENTRE_EMAIL` / `CALL_CENTRE_HOURS` | `+966 11 000 0000` / `leasing-callcentre@example.com` / `Sunday to Thursday, 9 am to 5 pm (Riyadh time)` — placeholders until Cenomi confirms; shown on the `handoff` card; mock cases are emailed to `CALL_CENTRE_EMAIL` |

Frontend: `VITE_API_BASE` (default `http://localhost:8000`), `VITE_MOCK` (`1` = run on fixtures; with `?scenario=<name>` on the inquiry page, replays a named fixture from `frontend/src/mocks/scenarios/*.json`; default / unknown name = interactive `demo` flow), `VITE_E2E` (`1` = capture SSE and mock requests for Playwright; send the `X-Test-Scenario` header when not in mock mode).

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
| `make test-agent` | `pytest -m agent` (tools, guard, actions, bundles, scenarios; excludes `sandbox` and `live`) |
| `make e2e-fe` | Playwright `@fe` suites, frontend only (`VITE_MOCK=1`, `e2e/playwright.fe.config.ts`) |
| `make e2e-int` | Playwright `@scripted` suites, real frontend + backend, `AGENT_MODE=scripted` (`make e2e` is an alias) |
| `make eval-live` | `scripts/eval_live.py` with the real model; optional `GROUP=` (default all scenarios; ungrouped scenarios are `intake`), `EVAL_REPEATS` (default 3, 2-of-3 pass rule), `EVAL_TOLERANCE` (default 5 percentage points vs baseline in `docs/eval-notes.md`). Writes JSON + Markdown to `backend/eval-results/` (gitignored). |
| `make e2e-live` | Playwright `@live` suites with the real model |
| `make ci` | `check`, `test`, `e2e-fe`, `e2e-int` (Playwright layers run locally before every PR) |
| `make ci-remote` | `check`, `test` (what CI runs on every PR) |
| `make gate` | `ci`, `eval-live`, `e2e-live` |

CI: `.github/workflows/ci.yml` runs `backend` (`check-be`, `test-be`) and `frontend` (`check-fe`, `test-fe`) on every PR and push to `main`. Playwright and live eval run locally (`make e2e-fe`, `make e2e-int`, `make e2e-live`, `make eval-live`), or in CI on demand from `e2e.yml` (`suite: scripted | live | eval`; uploads `backend/eval-results/` for `eval`). Dev-only `GET /api/dev/audit/{inquiry_id}` (with `/api/dev/outbox`) is documented in §10; INT and later steps assert on it via `e2e/support/events.ts`. Nightly live runs need the repository variable `NIGHTLY_LIVE=true` (runs `playwright-live` and `eval-live`). Safety invariants I1–I7: `app/agent/invariants.py` (AGENT-LIVE + pytest), `e2e/support/invariants.ts` (E2E-LIVE when `E2E_LIVE=1`).

## 13. Review lifecycle (L4, Day 4)

Contracts for [L4](specs/l4-outcome-assistance.md) at Day 4 depth. Code: `backend/app/workflow/` (models, machine, service, effects, store, contacts), `app/domain/case_brief.py`, `app/domain/payload.py`, `app/api/review.py`, `app/api/cases.py`, `app/api/case_cards.py`.

**Case** (`workflow/models.py`, one per submitted inquiry, keyed by its reference; JSON snapshots in `<DATA_DIR>/cases/`): `status` (`CaseStatus`: draft, submitting, submitted, first_review, reupload_requested, second_review, approved, sent_to_yardi, rejected, abandoned, redirected), `draft` (the inquiry as submitted; re-uploads replace documents), `review_queue {product_line, region, role, first_role}` (`role`: the final reviewer for the product line; `first_role`: the first-level reviewer, policy `first_level_review_role`, null on cases routed before 5 Nov 2026), `requests [{id, kind: reupload|contacts|sales_data, status: open|fulfilled|withdrawn, doc_types, roles, remarks, requested_by, requested_at, closed_at}]` (`roles`: a contacts request opened by a rejected contact asks only for these), `decisions [{level, outcome, remarks, reason_category, by, at}]`, `tenant_contacts [TenantContact]` (`FieldValue` per name, email, mobile, landline; `same_as_primary`; `contact_id`, `approval`, `approval_remarks`, `approved_by`, `added_by`, §13.1), `document_decisions {doc_type: DocumentDecision}` (§13.1), `sales_data`, `document_history`, `onboarding.invitations`, `yardi {company_id, brand_id, lead_ref, sent_at, attempts, needs_operations}`, `events` (applied transitions), `effects_done`, `case_session_id`. Created on submit (audit `case_created`) and routed at once.

**State machine** (`workflow/machine.py`): `transition(case, event, actor=, now=)` is pure and implements every row of M0 §6; it raises `IllegalTransition(code)` with `illegal_transition`, `not_allowed`, `not_in_queue`, `invalid_payload`, `stale_file` or `stale_contact` (§13.1). Reviewer events need a reviewer whose regions include the queue's region and whose role is the queue's role for that event's review level: `REVIEW_LEVEL[(status, event)]` is `first` for rows from `first_review` and `reupload_requested` and for the events in `FIRST_LEVEL_EVENTS` (`contact_approved`, `contact_rejected`), otherwise `final` (demo feedback §3.2), and `ReviewQueue.role_for(level)` names the role. Both roles see the case in their queue. `legal_events(case, actor)` lists what an actor can do now (the console's actions). `workflow/service.apply_event` is the only way a case changes: transition, save, audit `case_transition {event, from_status, to_status, by, outcome, subject?}` (refusals too; `subject` is the document type or contact role of a per-item decision), then effects.

**Routing:** policy `review_routing` maps the unit type to a role (store → `rlm_store`, media → `rplm_media`, specialty → `rplm_specialty`); the region is the mall's region in master data. Policy `first_level_review_role` (`lease_admin`) reviews first in every product line; the reviewer directory has one Lease Admin per region and a manager (`lease_admin-central`, `-western`, `-eastern`, `-manager`).

**Effects** (`workflow/effects.py`, inline, keyed `(case, event seq, effect)`, audit `effect_run`; a failure is audited and never rolls back the transition):

| Event | Effects |
| --- | --- |
| `routed` | `review_assigned` → the first-level reviewers (the Lease Admin of the region): subject "Inquiry for approval: …", link `<PUBLIC_BASE_URL>/review/cases/<ref>?as=<reviewer id>` (with dev tools, `?as=` signs that mock reviewer in; demo feedback F7) |
| `reupload_requested` | `reupload_request` → applicant, with a case link for the request |
| `documents_resubmitted` | `reupload_received` → first-level reviewers |
| `rejected` | `inquiry_rejected` → applicant (remarks, policy `after_rejection`) |
| `approved_first` | Azure AD invite of the primary contact (role `primary_contact`) unless `has_account`; `first_level_approved`; a system `contacts_requested` when policy `auto_request_contacts_after_first_approval`; `review_assigned` → the final reviewers when another role does the first level |
| `contacts_requested` / `sales_data_requested` | `contacts_request` / `sales_data_request` → applicant, with a case link |
| `contacts_provided` / `sales_data_provided` | `contacts_received` (final reviewers, and the first-level reviewers when `contacts.approval_required`) / `sales_data_received` → reviewers |
| `contact_rejected` | `contacts_request` → applicant when the rejection opened a new contacts request (not when it only added a role to an open one) |
| `request_withdrawn` | `request_withdrawn` → applicant |
| `approved` | invite each additional contact without an account (role = contact role); `inquiry_accepted`; `send_lead` to Yardi (`lead:<reference>`), each failure a `yardi_failed` event, up to `YARDI_MAX_ATTEMPTS`, then `needs_operations` |

**Applicant actions** (case chats only, §4 table style):

| Action | Payload | Does | Note |
| --- | --- | --- | --- |
| `resubmit_documents` | `{}` | Every requested document re-uploaded after the request → `documents_resubmitted` | `documents_resubmitted`, or `resubmit_blocked <doc_types>` (the re-upload card is re-sent) |
| `submit_contacts` | `{}` | Pressing Send accepts the values on the contacts card (`confirm_contacts`); required roles complete → `contacts_provided` | `contacts_submitted`, or `contacts_blocked <reasons>` |
| `submit_sales_data` | `{}` | A `sales_data` file uploaded after the request → `sales_data_provided` | `sales_data_submitted`, or `sales_data_blocked missing_file` |
| `signatory_answer` | `{is_signatory: bool}` | "Are you the authorised signatory?" (§13.1). Yes: `authorized_signatory` = the verified primary contact (`same_as_primary`); No: a same-as-primary signatory is cleared. Stores `Session.signatory_answer`, audits `signatory_answered {answer}`, returns the answered `signatory_question` card and the refreshed contacts card | `signatory_answer yes` / `signatory_answer no`, or `signatory_answer no_request` / `signatory_answer_invalid` |

Contacts being collected live on the case session (`Session.contacts_draft`); `workflow/contacts.write_contacts(current, entries, primary_draft)` is the deterministic writer for the case agent's `update_contacts` tool (entries `{role, first_name?, last_name?, email?, contact_number?, same_as_primary?, source?}`; "that's me" copies the primary contact as `verified`, unconfirmed; Arabic digits normalised). `contacts_blockers` lists `missing_contact:<role>`, `incomplete_contact:<role>`, `unconfirmed_contact:<role>`.

**Case links:** token purpose `case` (subject the reference, `data.r` the request id, `CASE_TTL_DAYS`); links `<PUBLIC_BASE_URL>/inquiry/case?t=…`. `POST /api/cases/open {token}` accepts a `case` or `track` token, reopens the case's chat (`Session.mode = "case"`, `case_id`) or starts one seeded with the submitted inquiry, adds a short assistant message, and returns the `POST /api/sessions` shape with a `case_status` card and the card for each open request. 400 `token_invalid` / `token_expired`; 404 `inquiry_not_found`.

**Cards:**

| `card_type` | `payload` |
| --- | --- |
| `case_status` | `{reference, status, stage: submitted\|first_review\|second_review\|outcome, stage_label, status_headline?, owner_role, last_change, open_requests:[{id, kind, label, remarks, doc_types, requested_at}], outcome: approved\|rejected\|null, outcome_remarks, next_step}` — `status_headline` is set for `approved` and `sent_to_yardi` (see `FINAL_APPROVAL_LABELS` in `services/status.py`) (card id `case_status`) |
| `document_upload` | gains `mode: "intake"\|"reupload"`, `requested_doc_types`, `remarks`; in re-upload mode `docs` lists only the requested types and `uploaded` means uploaded after the request; the button is Resubmit (`resubmit_documents`) |
| `contacts` | `{request_id, remarks, rows:[{role, label, required, first_name, last_name, email, phone, source, confirmed, same_as_primary, approval, approval_remarks}], can_submit, blockers, roles, signatory_answer}` (card id `contacts`). `approval`: Cenomi's decision on the contact as sent (`pending` "Waiting for Cenomi", `approved`, `rejected` with `approval_remarks`), null when not sent or changed since; `roles`: a request opened by a rejection asks only for these; `signatory_answer`: `yes` \| `no` \| null |
| `signatory_question` | `{prompt, yes_label, no_label, answered: yes\|no\|null}` (card id `signatory_question`): shown before the contacts card when a contacts request covering every role opens, until answered (policy `contacts.ask_signatory`); the buttons send `signatory_answer {is_signatory}` |
| `sales_data_upload` | `{request_id, remarks, uploaded, file_name, size_bytes, allowed_extensions, max_mb}`; upload with `doc_type=sales_data` (card id `sales_data`) |
| `reviewer_suggestion` | `{kind, action, payload, text}` — console assistant only; **Use** prefills the matching action form or Yardi re-link pickers (never submits). `kind`: `yardi_company`, `yardi_brand`, `reupload_remarks`, `rejection_remarks`, `contacts_request`, `tenant_reminder`. `action`: `request_reupload`, `reject`, `request_contacts`, `relink_company`, `relink_brand`, or empty for `tenant_reminder`. `payload`: e.g. `{remarks}`, `{company_id}`, `{brand_id}` |

**Reviewer assistant** (`REVIEWER_CONSOLE`, L4 §3.6): third LangGraph from `build_agent_graph` (`app/agent/reviewer_graph.py`, `reviewer_tools.py`, `reviewer_prompt.md`). Thread id `review:{case_id}:{reviewer_id}`. Tools (read-only, no `apply_event`, no case save): `get_case_brief`, `search_yardi_companies`, `list_company_brands`, `draft_reviewer_note`. Each suggestion tool emits a `reviewer_suggestion` card; audit `assistant_suggestion {kind, action}` per card (`used` when the reviewer submits from it, later).

**Documents:** `DocType.sales_data` exists only for case chats (`POST …/documents` with it in an intake chat is 400 `unknown_doc_type`); it isn't in the intake checklist or the policy's document lists. In a case chat, an upload returns the re-upload or sales-data card.

**Reviewer console API** (`REVIEWER_CONSOLE=true`, `INTEGRATIONS=mock`; header `X-Reviewer-Id`, unknown → 401; a case outside the reviewer's queue → 404):

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/review/reviewers` | Reviewers for the mock sign-in `[{id, name, role, regions, manager}]` |
| GET | `/api/review/me` | The signed-in reviewer |
| GET | `/api/review/cases?waiting_on=` | Queue `[{reference, brand, company, mall, product_line, region, status, stage_label, waiting_on, age_days, last_change, open_requests, possible_duplicate, follow_on_of, needs_operations}]` |
| GET | `/api/review/cases/{reference}` | `{brief: CaseBrief, timeline:[{at, actor, type, summary}], legal_actions, approval_blockers, first_approval_blockers, rejection_categories, reupload_doc_types}` |
| GET | `/api/review/cases/{reference}/documents/{file_id}` | The file |
| GET | `/api/review/yardi/companies?q=` | Active Yardi companies by the first word of the name `[{id, name}]`: the options for `relink_company` |
| GET | `/api/review/yardi/companies/{company_id}/brands` | `[{id, name, source}]` (`lease` \| `proposal`): the options for `relink_brand`. 404 `company_not_found` |
| POST | `/api/review/cases/{reference}/actions` | `{action, payload}` → the updated detail. Actions: `request_reupload {doc_types, remarks}`, `reject {remarks, reason_category?}`, `approve_first`, `request_contacts {remarks?}`, `request_sales_data {remarks?}`, `withdraw_request {kind}`, `relink_company {company_id}`, `relink_brand {brand_id}`, `remove_contact {role}`, `approve`, and (§13.1) `confirm_document_expiry {doc_type, file_id, expiry_date}`, `approve_document {doc_type, file_id, remarks?}`, `reject_document {doc_type, file_id, remarks}`, `approve_contact {contact_id}`, `reject_contact {contact_id, remarks}`. `request_reupload` with `doc_types: []` asks for the rejected documents. Errors: 400 `unknown_action` / `invalid_payload`, 403 `not_in_queue` / `not_allowed`, 409 `illegal_transition` / `stale_file` / `stale_contact` |
| POST | `/api/review/cases/{reference}/assistant` | `{text}` → SSE (`token`, `ui_card`, `done`, same as applicant chat). Honors `X-Test-Scenario` in scripted mode (one script step sequence per request, `step_index=0`; reviewer tools only). 401 `unknown_reviewer`; 404 `case_not_found` when the case is not in the reviewer's queue |

**Case brief** (`domain/case_brief.py`, deterministic): applicant, company, brand, product line, mall, region, CR status, every field with source, confirmation and evidence, verification, documents with replaced versions, sales data, contacts, requests, decisions, follow-on, Yardi link, stage ages, and a next-decision checklist from the policy.

**Services:** `ReviewerDirectory` (`data/mock_world/reviewers.json`: a reviewer per role × region, a manager per role, call-centre and guest-service staff), `IdentityService` (`invite(email, role, context)` sends `azure_ad_invitation` with an accept link `<PUBLIC_API_URL>/api/dev/identity/accept/{id}`; `has_account`; `status`; `accept` (refused for a revoked invitation); `revoke(invitation_id)` (flow v2 §3.6: marks `Invitation.revoked_at` and removes the account only if this invitation created it); seeded accounts in `data/mock_world/identity.json`), `YardiService` (`search_companies` by the first word, active only; `brands_for_company`; `company_by_cr(cr_number)` → the active company registered under that CR, or `None` (demo feedback §3.8; companies carry `cr_number` and `address`, linked to `tenants.json`); `send_lead(payload, idempotency_key)` → `YL-NNNNNN`; `data/mock_world/yardi.json`). Gateway services `identity`, `yardi`.

**Status page:** `GET /api/inquiries/{reference}?t=` follows the case: `status` is `under_review`, `approved`, `sent_to_yardi` or `rejected`; `summary` is applicant-facing copy (including `FINAL_APPROVAL_LABELS` when approved or sent to Yardi); stages Inquiry submitted → With the Leasing Admin → Tenant Qualified → Outcome (chart names, flow v2 §3.5); once decided, the Outcome stage is `done` and labelled "Outcome — Approved" (approved, sent to Yardi), "Outcome — Tenant Not Qualified" (first-level rejection) or "Outcome — Lead Rejected" (final-level rejection) (`status_stages`, `InquiryStatus.rejection_label`); `owner_role` from the queue; `waiting_on_you` lists open requests ("Re-upload documents", "Add company contacts", "Upload forecasted sales data").

**Chart names** (flow v2 §3.5, day F1): `app/workflow/labels.py` is the one place for display names. `status_label(case)` (console `stage_label`, case brief, tenant portal, reviewer assistant): Submitted, With the Leasing Admin, With the Leasing Admin — waiting for re-upload, Tenant Qualified, Approved — sending to Yardi, Approved and sent to Yardi, and for `rejected` "Tenant Not Qualified" (first level) or "Lead Rejected" (final level). `ROLE_LABELS`: `lease_admin` Leasing Admin, `rlm_store` Regional Sales Manager, `rplm_*` Regional Product Line Manager (Media / Specialty). Ids don't change (ADR-V3). "Forecasted Sales Data" replaces "estimated sales data" in templates, cards, console and the case brief; `inquiry_rejected` carries `Outcome: <label>`; `first_level_approved` says "Tenant Qualified".

**Reject Lead revokes** (flow v2 §3.6, V9): effect `revoke_primary` on a final-level `rejected` (policy `identity.revoke_on_lead_rejection`, default true) revokes the case's `primary_contact` invitation through the gateway (`identity.revoke`) and records audit `identity_revoked {invitation_id, role}`. An email that already had an account was never invited (`_invite`), so it's never revoked (A1).

**Policy:** `review_routing`, `second_level_contacts {required, optional}`, `rejection_categories`, `after_rejection`, `require_contacts_before_approval`, `auto_request_contacts_after_first_approval`, `document_approval`, `document_expiry`, `contacts`.

### 13.1 Per-document and per-contact approval (demo feedback §3.4, §3.5; day R2)

**Profile checks** (demo feedback §3.7, D12): `CaseBrief.document_checks = [{field, label, typed, document_value, doc_type, doc_label}]`, computed from the case's draft (`domain/document_checks.document_mismatches`) rather than stored, so a value the applicant later corrects stops being flagged: a typed or chat-derived value that an uploaded profile disagrees with (case, spacing and punctuation ignored, Arabic normalised, categories by master-data id). The text brief lists them under "Profile checks"; at first review the checklist adds "The profiles differ from what was typed: <labels>." Never a blocker.

**Document decisions** (`workflow/models.DocumentDecision`, `workflow/documents.py`): `Case.document_decisions[doc_type] = {doc_type, file_id, status: pending|approved|rejected, remarks, review_status, expiry_extracted, expiry_confirmed, expiry_confirmed_by, by, at}`, one per intake document, created at submit from the upload's `DocumentRef.review`. A decision names the upload it was made on: when the case's document is replaced (`documents_resubmitted`), the decision for that type starts again as pending with the new file and review result. `current_decisions(case)` fills in any that are missing (cases saved before 5 Nov 2026).

**Expiry** (`workflow/expiry.expiry_status(decision, today)`, pure): the date in force is `expiry_confirmed`, else `expiry_extracted`. `expired` before today; `expiring_soon` less than `document_expiry.expiring_soon_days` away; otherwise `valid`, or `unknown` with no date. Today comes from the app clock. Only the types in `document_expiry.doc_types` carry an expiry.

**First-level events** (state `first_review`, also `reupload_requested`; the first-level reviewer). Each names the `file_id`: one that isn't the current upload is refused with `stale_file` (409); a document whose re-upload is awaited, or that's already decided, with `invalid_payload`.

| Event | Payload | Guard |
| --- | --- | --- |
| `document_expiry_confirmed` | `doc_type, file_id, expiry_date` (ISO date) | A past date on an approved document sends it back to pending |
| `document_approved` | `doc_type, file_id, remarks?` | Pending; not `expired`; an `unknown` expiry is confirmed first |
| `document_rejected` | `doc_type, file_id, remarks` (required) | Pending |

`reupload_requested` with no `doc_types` asks for the rejected documents, with `"<label>: <remarks>"` lines as the request's remarks unless others are given. With `doc_types` and no remarks, the request takes those lines from the ticked documents when every one was rejected with remarks; otherwise remarks are required. `approved_first` is refused while `first_approval_blockers(case)` isn't empty: `document_pending:<type>` (a required document not approved), `document_rejected:<type>`, `expiry_unconfirmed:<type>`. Nothing changes a decision on its own (ADR-R6): an expired document stays pending until the reviewer rejects it.

**Contact decisions.** `TenantContact` gains `contact_id`, `approval` (pending | approved | rejected), `approval_remarks`, `approved_by` (a reviewer id or `system:<reason>`) and `added_by` (tenant | reviewer | system). The state machine sets them and ignores what a payload says.
- `contacts_provided`: an unchanged contact that was approved or pending keeps its id and state; a new, changed or previously rejected one is pending under a new id. The applicant as signatory (`authorized_signatory` with `same_as_primary`) is approved on entry (`system:verified_primary`) unless `contacts.applicant_signatory_needs_approval`.
- Contacts prefilled from the tenant record are approved on entry (`system:tenant_record`, `added_by: system`).

First-level events at `second_review`:

| Event | Payload | Does |
| --- | --- | --- |
| `contact_approved` | `contact_id` | Pending → approved. A changed contact's old id → `stale_contact` (409) |
| `contact_rejected` | `contact_id, remarks` (required) | Pending → rejected; opens a contacts request with `roles: [role]` and remarks `"<label>: <remarks>"`, or adds the role to an open one |

With `contacts.approval_required`, the `approved` blockers gain `contact_not_approved:<role>` for each required role that isn't approved.

**Signatory question.** `Session.signatory_answer` (`yes` | `no` | null) is persisted with the session and passed to the agent state as `signatory_answer`. `workflow/contacts.apply_signatory_answer(contacts, primary, is_signatory)` is shared by the `signatory_answer` action and the case agent's tool; `actions.signatory_answer_result(session, runtime, is_signatory)` returns the cards.

**Brief.**
- `BriefDocument` gains `approval, approval_remarks, decided_by, decided_at, expiry_tracked, expiry, expiry_extracted, expiry_confirmed, expiry_status, review_status, suggested_reject_remarks`. The last is set for an expired pending document: "This document expired on {date}. Please upload a current one."
- `BriefContact` gains `contact_id, approval, approval_remarks, approved_by, added_by`.
- The checklist lists "Approve or reject: …", "Rejected: … Request a re-upload.", "Confirm the expiry date: …" and "… waiting for the Lease Admin's approval."

**Console.**
- Document rows (`doc-row-<type>`): viewer link, expiry chip (`doc-expiry-status-<type>`), date input (`doc-expiry-<type>`, **Save date**), approval chip (`doc-approval-<type>`), **Approve** (`doc-approve-<type>`, disabled when expired or unknown) and **Reject** (`doc-reject-<type>`, remarks required, prefilled for an expired document).
- Contact rows (`contact-row-<role>`): approval chip (`contact-approval-<role>`), **Approve** (`contact-approve-<role>`) and **Reject** (`contact-reject-<role>`, remarks required).
- The buttons show only for the role whose actions they are; the final reviewer sees the chips.
- **Approve first level** is disabled, with the `first-approval-blockers` list, until the documents are decided. **Request re-upload** with nothing ticked asks for the rejected documents. Ticking only rejected documents also enables it with no remarks typed (`reupload-ticked-rejected-hint` names the rejection remarks that will be sent).

## 14. Proactive work and demo operability (L5 core, Day 5)

**Clock** (`app/clock.py`). `clock.now()` stamps every business record: case transitions and requests, document uploads, invitations, audit events, outbox messages, queue and brief ages. With `DEV_TOOLS=true` it's a `SimulatedClock` (real time plus an offset that only moves forward); otherwise `SystemClock`. Session idle timeouts, rate limits and signed-link expiry stay on real time. The offset isn't persisted; a restart or a reset puts it back to 0.

**Triggers** (`app/proactive/engine.py`, thresholds in `policy.proactive`). `tick()` evaluates every case; each firing is an `AttentionItem` keyed `(case, trigger, period)`, so a repeated tick or a restart doesn't fire twice:

| Trigger | Condition | Action | Tier |
| --- | --- | --- | --- |
| `stalled_review` | `first_review` or `second_review` for `review_stall_hours` (48) since entering the stage | Item for the queue; `review_stalled` email to the queue's reviewers (not managers) | 0 |
| `escalation` | Same stage for `review_escalate_hours` (96) | Item for the role's managers; `review_escalated` email to them | 0 |
| `applicant_reminder` | A request (re-upload, contacts, sales data) open for `tenant_reminder_hours` (72) | Item with a drafted reminder (`text`: what's missing and the reviewer's note); waits for approval | 2 (1 when `reminder_pre_approved`) |

The period is one stay in a stage (the stage plus its start time) or one request. A tick also sends held reminders whose time has come, and marks open items `dismissed` with reason `resolved` when their condition passed (the case moved on, the request was answered or withdrawn). No proactive path calls `transition()` or saves a case.

**Notification policy** (`app/proactive/notification_policy.py`, `NotificationPolicy.check`): tier 0 sends at any hour; tier 2 waits for approval; an approved or tier-1 applicant message is held during quiet hours (`22:00–08:00 Asia/Riyadh`, `policy.proactive.quiet_hours`) until the window closes, and throttled to one proactive message per case per `tenant_proactive_min_hours` (48). Each decision is audited as `proactive_decision {item_id, trigger, decision, reason, by}` (`sent`, `awaiting_approval`, `held_quiet_hours`, `throttled`, `dismissed`, `resolved`); each firing as `proactive_raised {item_id, trigger, tier, stage, hours}`.

**Templates:** `review_stalled`, `review_escalated` (information, staff), `applicant_reminder` (action required; `$message` is the approved text, `$case_url` opens the case scoped to the request).

**Needs attention API** (review router, `X-Reviewer-Id`):

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/review/attention` | `{items: [AttentionOut], counts: {open, raised, sent, dismissed: {reason: n}}, dismiss_reasons}`. Items are those still actionable (`open`, `awaiting_approval`, `held`) for the reviewer's queues, plus escalations for managers of that role; escalations first, then by age against the threshold |
| POST | `/api/review/attention/{id}/approve` | `{text?}` (edited reminder, 1–1000 chars) → the item, `sent` or `held` (with `send_after`). 409 `not_awaiting_approval` / `request_closed`, 400 `invalid_text` |
| POST | `/api/review/attention/{id}/dismiss` | `{reason}` from `policy.proactive.dismiss_reasons` → the item. 400 `invalid_reason`, 409 `already_closed` |

`AttentionOut`: `{id, trigger, label, recommended, reference, brand, mall, stage_label, status, audience (queue | manager), tier, age_hours, threshold_hours, request_kind, request_label, text, raised_at, send_after, sent_at, dismissed_reason}`. An item outside the reviewer's queues → 404 `item_not_found`.

**Dev tools** (`DEV_TOOLS=true`):

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/dev/clock` | `{now, offset_hours, simulated, timezone}` |
| POST | `/api/dev/clock/advance` | `{hours}` (0 < h ≤ 720) → moves the clock, runs a tick → `{clock, raised, sent, resolved}` |
| POST | `/api/dev/clock/to-morning` | Moves to the end of the next quiet-hours window, runs a tick |
| POST | `/api/dev/proactive/tick` | Runs a tick now |
| POST | `/api/dev/reset` | Deletes sessions, cases, audit, outbox, invitations, Yardi leads, attention items (every folder under `DATA_DIR` the app writes) and uploads; resets the clock; rebuilds services and graphs → `{reset: true}`; with `DEMO_SEED=true`, seeds the three demo cases again |
| GET | `/api/dev/demo-cases` | Day R5: the seeded cases `[{key, title, reference, status, first_reviewer, final_reviewer}]` (A first review: expired Company Profile with a profile mismatch, Brand Profile expiring soon; B second review: signatory Yes, billing contact pending; C sent to Yardi). Empty when `DEMO_SEED` is off. `/dev` lists them with "as Lease Admin" / "as RLM" links |

With `PROACTIVE_ENABLED=true` a background task runs `tick()` every `PROACTIVE_TICK_SECONDS`. Moving the clock always runs a tick.

**Frontend:** `/dev` (with `VITE_DEV_TOOLS=1`): one link per persona (applicant chat, dev inbox, each reviewer queue via `/review?as=<reviewer id>`, Needs attention), **Reset demo**, and the clock (+24 h, +48 h, to morning). `/review/attention`: the Needs attention view (approve, edit and dismiss reminders; dismiss flags with a reason; open the case); the queue page shows its count as a badge.

**Policy:** `proactive {review_stall_hours, review_escalate_hours, tenant_reminder_hours, tenant_proactive_min_hours, reminder_pre_approved, quiet_hours {start, end, timezone}, dismiss_reasons}`.

## 15. Intake channels (Day 5)

Spec: `docs/specs/intake-channels.md`. Every channel ends in the same draft, rules, submit and lifecycle.

**Who entered a value.** `Source.staff`: typed by a call-centre executive or the Guest Service desk for the applicant. Like `derived` and `verified` it is unconfirmed until the applicant confirms it (`NEEDS_CONFIRMATION = {derived, verified, staff}`), and `can_submit` blocks on it. In assisted mode every `user` write in a turn (tool, guard capture, card edit) is restamped `staff` (`agent/channels.restamp_staff`).

**Channel on the session and the case.** `Session.channel` and `Case.channel`: `self_service | assisted | existing_tenant`; `created_by` (staff id, tenant id, or null for the applicant); `tenant_id`. The case brief, the queue (`QueueItem.channel`) and the console show it. When `channel` is `assisted`, `CaseBrief.staff_role` and `QueueItem.staff_role` are the staff member's role (`customer_care` | `guest_service`) so the console can distinguish the call centre from Guest Service. `Session.staff_id` is set while staff drive the chat (assisted mode).

**Tenant Central, simulated.** `TenantDirectory` (`data/mock_world/tenants.json`: `T-1001` Oasis Coffee Company, CR `1010000000`, one brand; `T-1002` Al Noor Retail Group, CR `1010444444`, two brands) and `OpportunityCatalogue` (`opportunities.json`). `domain/tenant_prefill.prefill_from_tenant(draft, tenant, master, brand_id?)` writes company, CR, VAT, National Address, the brand (when one is chosen or there's only one), its sales category and the primary contact as `verified`, unconfirmed, and sets `cr_status: "tenant"` (submit isn't blocked). `prefill_for_new_brand(draft, tenant, master, company_name, company_address)` (Leasing Opportunities, demo feedback §3.8) writes the same company and contact fields with the given company name and address and no brand. `agent/channels.attach_documents_on_file(…, skip)` copies the documents on file into the inquiry (`DocumentRef.on_file`, `DraftDocumentRow.on_file`), except the types in `skip` (`NEW_BRAND_UPLOADS`: Company and Brand Profile).

**Cards:**

| `card_type` | Payload | Action |
| --- | --- | --- |
| `basic_info_review` | `{title, started_by, rows: [{key, label, display, source, confirmed, required}], missing, can_proceed, proceeded}` | Edit per field = `edit_field`; **Proceed** = `proceed_basic_info` (confirms every derived, verified or staff basic-info value in one step; audit `field_confirmed via=basic_info_review`). On the `existing_tenant` channel the card leaves out the brand (name, Arabic name, sales category): it's asked for in the chat and confirmed on its own card (R4) |
| `send_link` | `{email_masked, can_send, missing, sent_to_masked}` | **Send application link** = `send_application_link` |
| `existing_cr_choice` | `{cr_number, company_name, options: [{value: sign_in \| continue, label}], chosen}` | `existing_cr_choice {choice}` |
| `sign_in_prompt` | `{message, sign_in_url, button_label}` | A link to `/tenant` |

**Assisted mode** (call centre and Guest Service, `CALLCENTRE_CONSOLE=true`):

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/callcentre/staff` | Staff for the mock sign-in `[{id, name, role, role_label}]` (roles `customer_care`, `guest_service`) |
| POST | `/api/callcentre/inquiries` | Header `X-Staff-Id`. A new inquiry, `channel: assisted`, `created_by` and `staff_id` = the staff id → `CreateSessionResponse`. Honors `X-Test-Scenario` in scripted mode |
| GET | `/api/callcentre/handoffs` | Open handoff cases `[{case_id, inquiry_id, short_ref, reason, reason_label, summary, created_at}]` |
| POST | `/api/callcentre/handoffs/{case_id}/open` | The same inquiry, now driven by the staff member (`staff_id` set), with a summary message → resume payload |

Unknown or non-staff `X-Staff-Id` → 401 `unknown_staff`. In assisted mode the chat uses `app.state.assisted_graph`: the intake tools minus `send_verification`, `request_documents`, `show_review` and `start_follow_on`, plus `show_application_link` (shows the `send_link` card; it never sends). The router is skipped. The guard doesn't require `send_verification` or the sign-in wording. `verify_cr` on an existing CR shows `existing_cr_choice`:
- `sign_in` → `Session.closed = "redirected_to_sign_in"`, audit `inquiry_redirected {reason: sign_in}`;
- `continue` → the tenant record is prefilled and its documents attached, `Session.tenant_id` set, audit `tenant_prefill`.

**Application link.** `send_application_link` (staff only; needs the CR checked or skipped and every required basic-info field) emails `complete_application` with `<PUBLIC_BASE_URL>/inquiry/verify?t=<complete token>` (valid `EMAIL_LINK_TTL_HOURS`). The staff session keeps the token's nonce (`complete_nonce`): a resend makes the old link stop working, and the link is single use. Audit `application_link_sent {by, resend}`. `POST /api/verifications/email` accepts a `complete` token:
- checks the nonce (400 `token_used`) and that the email is still the one it was sent to (400 `email_changed`);
- creates a new chat session for the applicant (same draft with `email_verified: true`, same `channel`, `created_by` and `tenant_id`, uploads copied over) starting with a greeting and the `basic_info_review` card;
- marks the staff session `closed: "handed_to_applicant"`;
- returns `{session_id, resume_token}` as for the email link.
Then the self-service flow continues: mobile OTP, documents, review, submit.

**Existing tenant, signed in** (`TENANT_PORTAL=true`, header `X-Tenant-Id`; unknown → 401 `unknown_tenant`):

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/tenant/tenants` | For the mock sign-in `[{id, company_name, contact_name, brands: [{id, name}]}]` |
| GET | `/api/tenant/me` | The signed-in tenant |
| GET | `/api/tenant/opportunities?city=&unit_type=` | `[{id, mall_id, mall, city_id, city, unit_type, unit_type_label, unit_ref, area_min, area_max}]` |
| POST | `/api/tenant/opportunities/{id}/inquiry` | `{}` (a `brand_id` is accepted and ignored) → a new inquiry for a **new brand** (demo feedback §3.8, R4), `channel: existing_tenant`: company name and address from `YardiService.company_by_cr(tenant.cr_number)` (the tenant record if no match), CR, VAT, National Address and contact from the record, all `verified` and unconfirmed; no brand; mall and unit type from the opportunity (`user`); area range (`default`); with `policy.signed_in_skips_verification` the email and mobile are verified (audit `verification_result result=signed_in`); documents on file attached except the Company and Brand Profiles; audit `tenant_prefill {…, company_source: yardi\|tenant_record, yardi_company_id}`; a greeting by name (details from your Cenomi record; then the new brand, typed or from the Brand Profile) and the `basic_info_review` card. Honors `X-Test-Scenario` in scripted mode. 404 `opportunity_not_found` |
| GET | `/api/tenant/inquiries` | My inquiries: cases with this `tenant_id`, newest first `[{reference, brand, mall, product_line, stage_label, submitted_at, last_change, tracking_url}]` |

**Public page with an existing CR.** `existing_tenant_policy: sign_in`: `verify_cr` shows `sign_in_prompt` (button to `/tenant`) and audits `inquiry_redirected`; no inquiry is made. `allow_inquiry`: the tenant record is prefilled and `basic_info_review` shown; the email link and OTP still apply.

**Lifecycle.** On `approved_first`, an existing tenant's case gets its contacts from the record (`verified`, unconfirmed; effect `prefill_tenant_contacts`, before the automatic contacts request). Reviewers can remove one (`remove_contact`). Invitations still skip anyone with an account (`has_account`).

**Policy:** `signed_in_skips_verification` (default `true`). **Audit:** `application_link_sent`, `inquiry_redirected`, `tenant_prefill`. **Templates:** `complete_application`. **Token purpose:** `complete`.

**Frontend (this PR):**
- `/tenant`: mock sign-in;
- `/tenant/opportunities`: filters, **Raise inquiry** opens the chat;
- `/tenant/inquiries`: My inquiries;
- `/dev`: links to the call centre, Guest Service and each tenant;
- the console: channel labels.
The chat cards above, the `/callcentre` page and the assisted and existing-tenant prompts are Day 5 part B.
