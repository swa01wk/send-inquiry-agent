# Send Inquiry Agent — technical spec (source of truth)

Everything Cursor builds must match this file. If a contract here is missing or wrong, update this file in the same change.

## 1. Flow summary

1. User opens the chat from "Send us an inquiry" on the sign-in page. A session is created and the agent greets them.
2. **Gate**: the agent asks for the CR number. `verify_cr` → existing account: point to Sign In, stop. New: prefill company details as `verified` (unconfirmed). The user may skip.
3. **Collect**: brand, unit type, sales category, malls, space and budget, contact. The agent derives what it can and asks the user to confirm.
4. **Verify**: OTP to mobile and email (mock code from `OTP_MOCK_CODE`).
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

class DocumentRef(BaseModel):
    doc_type: DocType
    file_id: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime

class InquiryDraft(BaseModel):
    fields: dict[FieldKey, FieldValue]      # every FieldKey present; empty FieldValue when unknown
    cr_status: Literal["unknown", "new", "existing", "skipped"] = "unknown"
    documents: dict[DocType, DocumentRef] = {}
    otp_verified: bool = False
    otp_attempts_left: int = 3
    terms_accepted: bool = False
    reference: str | None = None
```

### Field keys

| Key | Label | Group | Type | Required | Rule |
| --- | --- | --- | --- | --- | --- |
| `cr_number` | CR number | company | str | no | 10 digits |
| `company_name` | Company name | company | str | yes | 2–120 chars |
| `company_address` | Company address | company | str | yes | 5–250 chars |
| `brand_name_en` | Brand name (EN) | brand | str | yes | 1–80 chars, Latin script |
| `brand_name_ar` | Brand name (AR) | brand | str | yes | 1–80 chars, contains Arabic script |
| `unit_type` | Unit type | brand | enum id | yes | master `unit_types` |
| `sales_category` | Sales category | brand | enum id | yes | master `sales_categories` |
| `malls` | Malls | space | list[mall id] | yes | ≥ 1, all in master `malls` |
| `area_min` | Area min (sqm) | space | int | no | default 10, source default |
| `area_max` | Area max (sqm) | space | int | no | default 25000, source default; 10 ≤ min ≤ max ≤ 25000 |
| `rent_period` | Rent period | space | enum id | no | master `rent_periods`; required if rent given |
| `rent_min` | Rent min (SAR) | space | int | no | ≥ 0 |
| `rent_max` | Rent max (SAR) | space | int | no | ≥ rent_min |
| `lease_period` | Lease period | space | enum id | no | master `lease_periods` |
| `first_name` | First name | contact | str | yes | 1–50 chars |
| `last_name` | Last name | contact | str | yes | 1–50 chars |
| `email` | Email | contact | str | yes | valid email |
| `mobile` | Mobile | contact | str | one of | `+9665XXXXXXXX` (normalised) |
| `landline` | Office landline | contact | str | one of | `+966` + 8 digits, not starting with 5 |
| `vat_number` | VAT number | documents | str | no | 15 digits, starts and ends with 3 |
| `national_id_number` | National ID / Iqama | documents | str | no | 10 digits starting with 1 or 2 |
| `national_address` | National address | documents | str | no | 5–250 chars |

"Required" for contact means `mobile` or `landline`. The pseudo key `contact_number` is accepted by `update_draft`: it is normalised and written to `mobile` or `landline` by prefix.

Display values: enum ids render as labels; `malls` as comma-joined names; area as `"25 – 35 sqm"`; rent as `"Up to SAR 250,000 / year"` or `"SAR 100,000 – 250,000 / year"`.

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
5. `otp_not_verified`.
6. `missing_document:<doc_type>`: each required document not uploaded.
7. `terms_not_accepted`.

### Phase (`domain/summary.py: compute_phase`)

`existing_account` if cr existing → `submitted` if reference → `gate` if cr unknown → `collecting` if any blocker 3–4 → `verifying` if otp not verified → `documents` if blocker 6 → `review`.

## 3. Agent tools (`backend/app/agent/tools.py`)

All tools return a short factual string for the LLM. Tools that change state return `Command(update=...)` with a `ToolMessage`, and emit `draft` (and cards) via the stream writer.

| Tool | Args | Behaviour |
| --- | --- | --- |
| `verify_cr` | `cr_number: str` | Validate format; call `CrService.verify`. Existing → `cr_status="existing"`. New → `cr_status="new"`, write `cr_number` (user) and any returned `company_name`/`company_address` as `verified`, unconfirmed; emit a `confirm_fields` card for them. |
| `skip_cr` | — | Only after the user agreed to skip. `cr_status="skipped"`. |
| `get_master_data` | `kind: str, city: str \| None` | Read-only lookup: `unit_types`, `sales_categories`, `cities`, `malls`, `lease_periods`, `rent_periods`. |
| `update_draft` | `fields: list[{key, value, source: "user" \| "derived"}]` | Validate each; write valid ones (user → confirmed, derived → unconfirmed); return per-field errors. Emit a `confirm_fields` card listing newly written derived values. The LLM can't write `verified`, `default`, `otp_verified`, `terms_accepted`, `documents` or `reference`. |
| `confirm_fields` | `keys: list[str]` | Mark those unconfirmed fields confirmed (only after the user agreed). Updates the existing confirm card. |
| `get_missing_fields` | — | Returns blockers from `can_submit` in plain words. |
| `show_mall_picker` | `city: str` | Emits a `mall_picker` card with that city's malls and the current selection. |
| `send_otp` | `resend: bool = False` | Requires `email` and a contact number. Calls `OtpService.send`, resets attempts on resend, emits `otp_input` card. |
| `request_documents` | — | Emits the `document_upload` card. |
| `show_review` | — | Only when the only remaining blocker is `terms_not_accepted`; emits the `review` card. Otherwise returns the blockers. |
| `suggest_replies` | `options: list[str]` (1–3, ≤ 60 chars each) | Emits a `quick_replies` card for this turn. |
| `search_faq` | `query: str` | Top 2 matches from `faq.json` (keyword score). The agent answers only from these. |
| `get_inquiry_status` | `reference: str` | Calls `StatusService.get`. |

There is no submit tool and no OTP-verify tool: both happen through UI actions, so the OTP code and consent never pass through the LLM.

## 4. UI actions (handled in the chat endpoint before the graph runs)

| Action | Payload | Backend does, then runs the graph with a `[ui_event]` note |
| --- | --- | --- |
| `select_malls` | `{mall_ids: list[str]}` | Validate; write `malls` as user, confirmed. Note: `malls_selected: <names>` |
| `submit_otp` | `{code: str}` | `OtpService.verify`; on success `otp_verified=True`; on failure decrement attempts (0 → auto resend, reset to 3). Note: `otp_verified` or `otp_failed attempts_left=N` or `otp_resent`. The code is never added to messages. |
| `resend_otp` | `{}` | Resend, reset attempts. Note: `otp_resent` |
| `edit_field` | `{key, value}` | Validate; write as user, confirmed. Note: `field_edited <key>` |
| `confirm_card` | `{card_id}` | Confirm all fields on that confirm card. Note: `fields_confirmed <keys>` |
| `accept_and_submit` | `{terms_accepted: true}` | Set `terms_accepted`; run `can_submit`; if clear, `SubmitService.submit` → set `reference`, emit `success` card. Note: `submitted reference=<ref>` or `submit_blocked <blockers>` |

`[ui_event]` notes are appended as a `HumanMessage` whose content starts with `[ui_event]`. They are never shown in the chat UI. The system prompt tells the agent they are system notifications, not the user's words.

## 5. Guard node (deterministic)

After the agent's final reply each turn:
1. Recompute `phase`; emit a `draft` event.
2. Attach the card for a phase the user just entered if it hasn't been shown: `documents` → `document_upload`, `review` → `review`. (`verifying` cards come from `send_otp`.)
3. If the reply claims the inquiry was submitted (regex on "submitted|sent your inquiry|reference") while `reference` is None → add a system note and route back to `agent` once.
4. If phase is `existing_account`, ensure the reply points to Sign In.
5. When `malls` is empty and the user's message names one or more seed malls (same mention rules as `filter_mall_ids`), write those mall ids as `user` (see `fill_mentioned_malls` in `mall_match.py`). Also runs after `update_draft` when malls were omitted. Mall mention: the full normalised mall name (or optional `aliases` on a mall in master data) must appear as whole words in the user message (`\b` boundaries, optional leading “the”); city or country tokens alone do not match.

## 6. REST API (`/api`)

Errors: `{"error": {"code": str, "message": str}}` with 4xx/5xx.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{status:"ok"}` |
| POST | `/api/sessions` | — | `{session_id, messages:[{id, role:"assistant", text}], cards:[UiCard], draft:DraftSummary}` (fixed welcome, see design spec) |
| POST | `/api/sessions/{id}/chat` | `ChatRequest` | `text/event-stream` (section 7) |
| POST | `/api/sessions/{id}/documents` | multipart: `doc_type`, `file` | `{document, card: UiCard(document_upload), draft}` · 400 `invalid_extension` / `too_large` / `unknown_doc_type` |
| DELETE | `/api/sessions/{id}/documents/{doc_type}` | — | `{card, draft}` |
| GET | `/api/sessions/{id}/draft` | — | `DraftSummary` |
| GET | `/api/master/{kind}` | `?city=` for malls | list of master items |
| GET | `/api/inquiries/{reference}` | — | `{reference, status:"under_review", submitted_at, steps:[{key, label, state:"done"\|"current"\|"upcoming"}]}` |

`ChatRequest`:
```json
{"type": "message", "text": "We run Bean Street, a specialty coffee brand"}
{"type": "action", "action": "select_malls", "payload": {"mall_ids": ["riyadh-mall-a"]}}
```

Unknown session → 404 `session_not_found`. Sessions expire after 2 hours idle. Rate limits: 30 chat requests/min per session, 60/min per IP → 429 `rate_limited`.

## 7. SSE events

Each event is `event: <type>` + `data: <json>`.

| Event | Data | Frontend |
| --- | --- | --- |
| `token` | `{message_id, text}` | Append to the assistant message `message_id` (create it if new) |
| `ui_card` | `UiCard` | Insert after the current assistant message, or replace in place if `card_id` exists |
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
| `confirm_fields` | `{title, fields:[{key, label, display, source, confirmed}], all_confirmed}` |
| `mall_picker` | `{city:{id,label}, malls:[{id,name}], selected:[id], min_select:1}` |
| `otp_input` | `{sent_to:{mobile_masked, email_masked}, attempts_left, verified, code_length:4}` |
| `document_upload` | `{docs:[{doc_type,label,required,uploaded,file_name,size_bytes}], required_uploaded, required_total, allowed_extensions (dotted, e.g. `.pdf`), max_mb}` |
| `review` | `{groups:[{title, rows:[{key,label,display,source,confirmed,required}]}], documents:[...], checks:Checks, can_submit, terms_accepted, blockers:[str]}` |
| `success` | `{reference, tracking_url, steps:[{label, detail, state}]}` |
| `quick_replies` | `{options:[{label, text, action?: "send" \| "focus_input", placeholder?: string}]}` — default `action` is `send` |

### `DraftSummary`
```json
{
  "phase": "collecting",
  "fields": [{"key": "company_name", "label": "Company name", "group": "company", "display": "Bean Street Trading Co.", "source": "verified", "confirmed": false, "required": true}],
  "documents": [{"doc_type": "company_profile", "label": "Company Profile", "required": true, "uploaded": false, "file_name": null, "size_bytes": null}],
  "checks": {"required_filled": 7, "required_total": 11, "unconfirmed": 2, "otp_verified": false, "required_docs_uploaded": 0, "required_docs_total": 2, "terms_accepted": false},
  "can_submit": false,
  "changed_keys": ["company_name", "company_address"]
}
```
Groups in order: company, brand, space, contact. Area shows as one row (`area`), rent as one row (`rent`), lease as one row.

## 8. Services (mocks, `backend/app/services/`)

| Interface | Mock behaviour |
| --- | --- |
| `CrService.verify(cr) -> CrResult` | `1010123456` → new, company "Bean Street Trading Co.", address "King Fahd Road, Al Olaya, Riyadh" · `1010222222` → new, company "Fawaz Alhokair Trading Co.", address "King Fahd Road, Riyadh" · `1010000000` → existing · any other valid number → new, no details |
| `OtpService.send(session, email, phone)` / `verify(session, code)` | Code = `OTP_MOCK_CODE`; logs "OTP sent" without the code |
| `StorageService.save(session, doc_type, upload) -> DocumentRef` | Writes to `UPLOAD_DIR/<session>/<uuid><ext>`; never opens content |
| `SubmitService.submit(draft) -> reference` | `GEO-{unit code}-{6 random digits}`; stores the payload in memory; logs it |
| `StatusService.get(reference)` | Known reference → `under_review`; else 404 |

Unit codes: store `STR`, media `MED`, specialty `SPC`, office `OFF`.

## 9. Seed data (`backend/app/data/`)

`master_data.json` (sample data — replace with real Cenomi data later):
```json
{
  "unit_types": [{"id": "store", "label": "Store", "code": "STR"}, {"id": "media", "label": "Media", "code": "MED"}, {"id": "specialty", "label": "Specialty", "code": "SPC"}, {"id": "office", "label": "Office", "code": "OFF"}],
  "sales_categories": [{"id": "fnb_cafe", "label": "Food & Beverage · Café"}, {"id": "fnb_restaurant", "label": "Food & Beverage · Restaurant"}, {"id": "fashion", "label": "Fashion & Apparel"}, {"id": "beauty", "label": "Health & Beauty"}, {"id": "electronics", "label": "Electronics"}, {"id": "entertainment", "label": "Entertainment"}, {"id": "services", "label": "Services"}],
  "cities": [{"id": "riyadh", "label": "Riyadh"}, {"id": "jeddah", "label": "Jeddah"}, {"id": "dammam", "label": "Dammam"}],
  "malls": [
    {"id": "riyadh-mall-a", "name": "Riyadh Mall A", "city": "riyadh"}, {"id": "riyadh-mall-b", "name": "Riyadh Mall B", "city": "riyadh"},
    {"id": "riyadh-mall-c", "name": "Riyadh Mall C", "city": "riyadh"}, {"id": "riyadh-mall-d", "name": "Riyadh Mall D", "city": "riyadh"},
    {"id": "jeddah-mall-a", "name": "Jeddah Mall A", "city": "jeddah"}, {"id": "jeddah-mall-b", "name": "Jeddah Mall B", "city": "jeddah"},
    {"id": "mall-of-arabia", "name": "Mall of Arabia", "city": "jeddah", "aliases": ["Arabia Mall"]},
    {"id": "dammam-mall-a", "name": "Dammam Mall A", "city": "dammam"},
    {"id": "mall-of-dhahran", "name": "Mall of Dhahran", "city": "dammam"}
  ],
  "lease_periods": [{"id": "1y", "label": "1 year"}, {"id": "2y", "label": "2 years"}, {"id": "3y", "label": "3 years"}, {"id": "5y", "label": "5 years"}],
  "rent_periods": [{"id": "monthly", "label": "Monthly"}, {"id": "yearly", "label": "Yearly"}]
}
```

`faq.json`: `[{id, question, keywords:[...], answer}]`, 8–10 entries (answers are placeholders marked `[to be confirmed]` where facts are unknown):
process steps · review time · required documents · what a CR number is · what a VAT certificate is · what each unit type means · editing after submit · how to track an inquiry · why we verify the phone/email · what happens to uploaded documents.

## 10. Configuration (`backend/.env`)

| Variable | Default |
| --- | --- |
| `OPENAI_API_KEY` | — (required) |
| `OPENAI_MODEL` | — (required; any OpenAI chat model with tool calling) |
| `OPENAI_TEMPERATURE` | `0.6` |
| `OTP_MOCK_CODE` | `1234` |
| `MAX_UPLOAD_MB` | `5` |
| `UPLOAD_DIR` | `./.uploads` |
| `SESSION_TTL_MINUTES` | `120` |
| `RATE_LIMIT_SESSION` | `30/minute` |
| `RATE_LIMIT_IP` | `60/minute` |
| `CORS_ORIGINS` | `http://localhost:5173` |
| `LOG_LEVEL` | `INFO` |

Frontend: `VITE_API_BASE` (default `http://localhost:8000`), `VITE_MOCK` (`1` = run on fixtures).

## 11. Changes from the POC plan doc

- Submit and OTP verification moved from agent tools to UI actions, so the OTP code and consent never pass through the LLM.
- Added `show_mall_picker`, `suggest_replies` and the `confirm_card` / `edit_field` actions.
- `DraftSummary.changed_keys` drives the draft panel's highlight and auto-scroll.
