# 18 Nov demo feedback: friendlier intake and tracking without a login

**Status:** drafted 23 Nov 2026 (MS1) · **Delivery:** days B1–B5 (Wed 25 Nov – Thu 3 Dec, weekends off), gate Fri 4 Dec, `prompts/demo-18nov/` · **Tracker:** [18 Nov demo tracker](https://claude.ai/artifact/4KmQbw2D1bwVzw7TGKTnJd) (N1–N19, X1–X5, M27–M35, MS1–MS18) · **Baseline:** `main` at `f66cd28` (#113), demoed to Muzammil on 18 Nov 2026

This spec takes in the feedback from the 18 Nov demo of the flow v2 build. It changes what [`flow-v2-alignment.md`](flow-v2-alignment.md) built; it doesn't replace it. Where it changes a contract, the build day's PR folds the change into `docs/spec.md` (§7). Unit matching (X1–X3) has its own spec, [`unit-matching.md`](unit-matching.md) (MS3), and is built from 7 Dec.

## 1. Why

Muzammil closed the demo with two points: a prospective tenant with no login must be able to **track the inquiry and come back to it**, and in the reviewer screens **the action must sit next to the information it acts on**. He also asked for a friendlier intake: value buttons instead of "Looks right", the agent speaking as the leasing team, Property Details asked one at a time, and a verification card that can't be used to verify someone else's email.

He also set the scope: Tenant Central already has the Lease Admin and RSM screens, so our reviewer console is for internal testing only. *"We just want you to automate the inquiry part and the tenant without login."* Console work this round is N19 and nothing more.

**Rule for this round.** The flow v2 chart still sets the steps and their order (ADR-V1). This round changes how a step is asked or shown, adds the Track page in front of the existing case chat, and moves the email check later (M29, a noted departure, like M2).

**Naming.** N1–N19 are the feedback items, X1–X5 the enhancements (X4 is built here), M27–M35 the decisions, G6–G8 the gaps found in the code (§8), B0–B5 the build days, MS1–MS18 the milestones, NG1–NG19 this spec's gate rows, NV01–NV11 the Playwright stories and ADR-N1–N6 its design rules. Timestamps such as (6:58) point to the 18 Nov transcript.

**In scope:**

| Item | What | Day |
| --- | --- | --- |
| N1 | Unit type offers Store, Office, Media and Specialty; Media and Specialty go to the RPLM at the final level (M34) | B1 |
| N2 | "What do you sell" reworded, with examples; Office asks what the company does (M28) | B1 |
| N3 | Sales category chosen from option buttons built from master data (one, two or three side by side; a broad answer gives its group) | B1 |
| N4 | No "Looks right" anywhere: each confirm row shows its value as the button, plus Change (M27) | B1 |
| N5 | Basic Info opens with "Tell me a bit more about you and your company", with an example answer | B1 |
| N6 | The agent speaks as the leasing team; no "our leasing team will contact you", no "we'll move to the mall" | B1 |
| N7 | No "Open verification link" button in the chat; the card shows status only | B1 |
| N8 | The SMS code expires after 60 s, with a countdown and Resend after expiry (M30) | B2 |
| N9 | The email link no longer blocks intake or Submit; it must be used before the Lease Admin's first-level approval. Landline-only applicants still verify the email before Submit (M29) | B2 |
| N10 | Property Details asked one question at a time: size, budget, lease length, start date, then the mall; "flexible" is an answer (M31) | B3 |
| N11 | New field: desired start (a month, or as soon as possible) | B3 |
| N12 | Mall names matched in code, with aliases and close spellings; an ambiguous match gives buttons | B3 |
| N13 | The first-approval email no longer says "qualified tenant" | B1 |
| N14 | "Track your inquiry" page: reference + email, then a 6-digit code to the email on file (M33) | B4 |
| N15 | The status sits on the case page, as a compact strip above the chat | B4 |
| N16 | The status names who holds the inquiry: "With you" whenever a request waits on the applicant | B4 |
| N17 | Case mode is action-only: per item upload and comment; "Send a follow-up" when nothing is pending; no text box (M35) | B4 |
| N18 | Authorized Signatory and Billing Contact given on cards, with "Same as primary contact" | B4 |
| N19 | Console: Request re-upload on each document card; contact details next to the Approve Lead action | B5 |
| X4 | Status for the General Inquiry agent: the Track endpoints plus the existing status endpoint, documented as its contract | B4 |

**Not in this round:** unit matching, the counter-offer and the RSM's suggested unit (X1–X3, [`unit-matching.md`](unit-matching.md), from 7 Dec); the agent test panel (X5, its own plan); changes to the Tenant Central review screens (they exist in the platform); lookup by phone on the Track page (M33).

## 2. Gate

All rows are Must and due by Fri 4 Dec. A row's test must pass in CI, or for Playwright locally with the result in the PR. Every layer in [`docs/testing/flow-v2-test-plan.md`](../testing/flow-v2-test-plan.md) §1 runs; this round's matrix is in `docs/testing/demo-18nov-test-plan.md` (MS2).

| # | Criterion | Proved by | Day |
| --- | --- | --- | --- |
| NG1 | Unit type offers the four `flow_v2_intake.product_lines`. A Media or Specialty inquiry gets a `GEO-MED-…` or `GEO-SPC-…` reference, goes to the Leasing Admin first and the RPLM (Media or Specialty) at the final level. | `tests/policy/test_product_lines.py`; `tests/lifecycle/test_routing.py`; NV01 | B1 |
| NG2 | The sales category is set only by a tap on a `choice` card, or by the user typing an exact category name. Options come from master data (1–4, ids checked in code; a group id expands to its categories). The tap writes `source: user`, `confirmed: true`. Labels follow the conversation language. | `tests/agent/test_choice_card.py`; `tests/api/test_choose_option.py`; eval `category_options`; NV01, NV02 | B1 |
| NG3 | No card shows "Looks right" or a card-level confirm. Each `confirm_fields` row has a value button (`confirm_field`) and Change (`edit_field`); a tap confirms that field only. | `tests/api/test_confirm_field.py`; Vitest `ConfirmFieldsCard`; `e2e-fe` baselines; NV01 | B1 |
| NG4 | Replies never refer to "our leasing team" in the third person or announce the next section ("we'll move to …"). Basic Info opens with the N5 question and an example. | eval `leasing_team_tone` (EN, AR); guard test `tests/agent/test_guard_tone.py` | B1 |
| NG5 | The verification card payload has no `demo_token`, in every mode; the card has no link button. Tests and demos open the link from the outbox. | `tests/api/test_verification_card.py`; Vitest `VerificationCard`; NV01 | B1 |
| NG6 | An SMS code expires `otp.ttl_seconds` (60) after it was sent. An expired code is refused (`otp_expired`) and doesn't use an attempt. The card counts down from `code_expires_at` and offers Resend once the code expires, within the resend limits. | `tests/services/test_otp_expiry.py` (dev clock); Vitest; NV03 | B2 |
| NG7 | With a verified mobile, the inquiry becomes `pending` and can be submitted without the email link. Landline only: Submit stays blocked until the email is verified. A case submitted with the email unverified carries `email_unverified`; `approved_first` is refused until the email is verified (link, resume link or Track code), which records `contact_email_verified`. | `tests/domain/test_verification_rules.py`; `tests/lifecycle/test_email_after_submit.py`; NV04, NV05 | B2 |
| NG8 | Property Details asks one item per turn in the order area → budget → lease length → start → malls; the next item is computed in code. A value given early or a "flexible" answer is never asked again. None of the four blocks Submit. | `tests/agent/test_property_sequence.py`; eval `property_sequence`; NV06 | B3 |
| NG9 | `desired_start` holds `YYYY-MM` or `asap`; a derived value ("from January") needs confirmation; it shows on the review card, in the case brief and in the submission payload. | `tests/domain/test_desired_start.py`; NV06 | B3 |
| NG10 | Mall names go through `match_mall` in code: an exact or alias match or one close spelling → the id; two or more close → a `choice` card; none → the mall picker. The model's own id guesses are checked, never trusted. | `tests/domain/test_mall_matcher.py`; eval `mall_fuzzy`; NV07 | B3 |
| NG11 | `POST /api/inquiries/track` always answers the same, whatever the reference and email. A code goes only to the email on file, is 6 digits, lasts 10 minutes, is single use with 3 attempts and is rate limited. `POST /api/inquiries/track/verify` returns a `track` token for that reference only. Codes never reach the model, logs or audit payloads. | `tests/api/test_track.py`; `tests/security/test_track.py`; NV08 | B4 |
| NG12 | The case page shows the status strip (reference, who holds it, waiting items). Whenever a request is open, the holder is "With you". The tracking link in every email opens the case page. | `tests/services/test_status_owner.py`; Vitest `StatusStrip`; NV08, NV09 | B4 |
| NG13 | Case mode has no text box. Each waiting item has its own actions (upload or replace; comment). With nothing waiting, "Send a follow-up" sends one comment. Comments reach the reviewer word for word and are audited; the model sees only that a comment was sent. | `tests/api/test_case_actions.py`; eval `case_actions`; NV09, NV10 | B4 |
| NG14 | Contacts are given on the contacts card; "Same as primary contact" fills a role from the verified primary contact; nothing is typed in chat. | `tests/api/test_contacts_card.py`; NV10 | B4 |
| NG15 | Console: Request re-upload is on each rejected document's card; the contact details sit beside Approve Lead. | Vitest `DocumentDecisions`, `ActionsPanel`; NV11 | B5 |
| NG16 | The GI agent contract (X4) is documented in `docs/spec.md`: the two Track endpoints and `GET /api/inquiries/{reference}?t=`, with `owner_label`. | `tests/api/test_status_contract.py` | B4 |
| NG17 | The first-approval email has no "qualified"; no template links to `/inquiry/status/`. | `tests/flow/test_labels.py` (template grep) | B1, B4 |
| NG18 | No regression: S1–S24 and CC1–CC3 pass on INT, updated only where they clicked "Looks right" or the demo link; the full `eval-live` stays within `EVAL_TOLERANCE` of the 10 Nov results; each new group passes 3/3 in English and Arabic. | `make e2e-int`; `make eval-live` | B1–B5 |
| NG19 | `e2e-live` personas pass on desktop and mobile; one manual run of the demo with only the tenant tab and the Track tab on screen. | `make e2e-live`; `docs/demo-script.md` | B5 |

## 3. Work items

### 3.1 Unit types (B1; N1, M34)

- `policy.yaml`: `flow_v2_intake.product_lines: [store, office, media, specialty]`. Master data already has all four (`app/data/master_data.json`, codes STR, OFF, MED, SPC), and `review_routing` already maps `media → rplm_media` and `specialty → rplm_specialty` (`app/policy/config.py`).
- The agent offers the four as quick replies (`suggest_replies`), in the language of the chat. The prompt's "Store or Office" lines read the list from Rules in force.
- First level stays the Leasing Admin for all four. The final level's label comes from `ROLE_LABELS` ("Regional Product Line Manager (Media)" or "(Specialty)"), already used by `services/status.py`.
- Same questions and documents as Store. Kishna's media pipeline can plug in later behind the routing; nothing in intake depends on it.

### 3.2 Option buttons and value buttons (B1; N3, N4, M27)

**The `choice` card (new).** One card for any value picked from a list: the sales category now, an ambiguous mall in §3.5, later anything else with a list.

```json
{"card_type": "choice", "payload": {
  "key": "sales_category",
  "prompt": "Which fits best?",
  "options": [{"value": "fnb_cafe", "label": "Food & Beverage · Café", "label_ar": "أغذية ومشروبات · مقهى"}],
  "lang": "en",
  "chosen": null
}}
```

- **Tool `show_category_options(candidates: list[str], evidence: str)`.** The model passes category or group ids from what the user said they sell (never from a brand name alone; the `category_needs_what_you_sell` check stays). Code drops unknown ids, expands a group id to its categories, removes duplicates and keeps at most 4, in the model's order. With none left it answers `no_category_match` and the model asks what they sell, or offers the nearest group.
- **Groups.** Master data gains `sales_category_groups` (`{id, label, label_ar, categories: [ids]}`). Seed: `fnb` (fnb_cafe, fnb_restaurant), `retail` (fashion, electronics), `beauty`, `entertainment`, `services`. When Cenomi shares the app's list it's a data change (G6).
- **UI action `choose_option {card_id, key, value}`.** The value must be one of the card's options (checked in code). It writes the field with `source: user`, `confirmed: true`, refreshes the card with `chosen`, and the model gets `[ui_event] option_chosen sales_category=fnb_cafe`.
- A typed answer that exactly names one option (either language) is the same as a tap; anything else goes back to the model.
- `lang` is set by code from the last typed message (the check `guard._wrong_language_note` already uses), so Arabic chats get Arabic buttons ("drive CTAs from the selectable items", 10:30).

**Value buttons on `confirm_fields` (M27).**

- The card-level "Looks right" button goes (`ConfirmFieldsCard.tsx:45`). Each unconfirmed row shows its value as a button ("Use «بين ستريت»", "Use Sara Ali") and Change. A confirmed row shows a tick.
- **UI action `confirm_field {card_id, key}`** confirms that one key (`draft_ops.confirm` with one key) and returns `[ui_event] fields_confirmed <key>`. `confirm_card` stays accepted for old sessions, but no card sends it.
- Values filled from a profile get one button per field; there is no "accept all".
- The model's `confirm_fields` tool is unchanged: a typed "yes, that's right" still confirms what the card showed (system prompt §5).
- Golden rule 2 holds: a derived value is confirmed only by the user's tap or words.

### 3.3 How the agent speaks (B1; N2, N5, N6, M28)

`system_prompt_v2.md` changes, with eval checks behind each (§6):

- **Unit Type and Sales Category:** "Are you looking for a store, an office, media space or a specialty unit?", then, once the unit type is known: "Tell me a little about the business. What will customers come to you for? For example coffee and pastries, women's fashion, or a pharmacy." For Office: "What does the company do?" The example lists live in `policy.yaml` (`flow_v2_intake.examples`), so Cenomi can change them without a prompt change.
- **Basic Info:** "Tell me a bit more about you and your company: your name, the company name and address, your brand, an email and a phone number." The prompt gives an example answer for the agent to show once (a sample name, "Riyadh", a sample `+9665…` number, `name@company.com`).
- **Voice:** the agent is the leasing team. Never "our leasing team will contact you" or "who should our leasing team contact"; say "we'll contact you". No announcing the next section ("we'll move to the mall"); ask the next question as an interviewer would.
- **Guard rule 9, `_third_person_team`** (self-service and case): a reply that says "our leasing team" or "the leasing team will" → route back once with a note. An eval check backs it.
- The 7 Nov example lines that the old phrasing came from (`system_prompt_v2.md` lines 32, 123, 129) are rewritten.

### 3.4 Verification (B1 for N7, B2 for N8 and N9; M29, M30)

**No link in the chat (N7).**
- `build_verification_card` drops `demo_token` from the payload, in every mode; `AgentRuntime.email_demo_token` and the `EMAIL_LINK_DEMO` setting are removed.
- `VerificationCard.tsx` loses the "Open verification link (demo)" button. The card says where the link was sent and offers Resend.
- Playwright and the live personas open the link from `GET /api/dev/outbox` (new helper `e2e/support/outbox.ts: openEmailLink(page, email)`). `invariants.ts` stops reading `demo_token`.
- The demo opens the link from the dev inbox in a tab kept off screen.

**Code expiry (N8, M30).**
- `policy.yaml`: `verification.otp_ttl_seconds: 60`.
- `MockOtpService.send` records `sent_at` per session; `verify` returns `expired` once `clock.now() > sent_at + ttl`. The protocol's `verify` returns `Literal["ok", "wrong", "expired"]`.
- `_submit_otp`: `expired` → `[ui_event] otp_expired`, attempts unchanged, the card refreshed.
- The verification card's `mobile` gains `code_expires_at` (ISO). The card counts down ("Code expires in 0:42") and, at zero, shows "Code expired" with Resend. Resend keeps today's limits (`resend.cooldown_seconds: 60`, `max_per_hour: 5`); with a 60 s code, Resend is ready as the code dies.
- The email link keeps its 72 h (`email_verification.py`, `ttl_hours`).

**The email doesn't block (N9, M29).**
- `policy.yaml`: `verification.email_required_before: first_approval` (or `submit`, today's behaviour).
- `app/domain/rules.py` gains `intake_verified(draft)`: the mobile verified when one was given; the email verified when only a landline was given. `verification_blockers` reads the policy: with `first_approval`, the email blocker applies only to a landline-only draft.
- The `verification` section is done when `intake_verified`. The pending save (`agent/pending.py: note_verification`, the repository's pending status) uses `intake_verified`, so the inquiry is saved when the SMS code succeeds (changes A2).
- **Submitted with the email unverified.** The case keeps the draft's `email_verified: false`. `first_approval_blockers` adds `email_unverified`. The console shows it as "Applicant hasn't confirmed their email yet" with the date the link was sent, and offers Resend link.
- **Verifying after submit.** The link (`/inquiry/verify`), the resume link or a Track code (§3.6) proves the email. When the session has a case, new case event `contact_email_verified` (actor system, any status before `second_review`) sets `case.draft.email_verified`, clears the blocker and audits it.
- **Reminder.** The case's status strip shows "Waiting on you: confirm your email". At `verification.email_reminder_hours` (48, before the 72 h link expires) the link is sent again once, through the proactive tick. An expired link never rejects the inquiry; the applicant gets a new one with Resend or the Track page.
- **Landline only.** Unchanged from today: email link before Submit (`email_required_before` doesn't apply).
- The prompt's "Saving and coming back" lines change: the inquiry is saved once the mobile is verified; the email can be confirmed later from the link.

### 3.5 Property Details (B3; N10, N11, N12, M31)

**One question at a time (N10).**
- `bundles.still_needed_line` for `property_details` names one item: the first of `area`, `budget`, `lease_period`, `desired_start`, `malls` that has no value and isn't marked flexible. The prompt's Property Details line changes to "ask the item the hint names; one question per turn".
- **Tool `mark_flexible(items: list[Literal["area", "budget", "lease_period", "desired_start"]])`.** Records `draft.flexible` (new, list of items, set only from the user's words; `evidence` required). A flexible item isn't asked again and leaves its fields empty.
- Anything given early is saved by `update_draft` as today and skipped by the hint.
- Only `malls` is required. `can_submit` doesn't change.
- **Budget basis.** New field `rent_basis` (`total` | `per_sqm`, default `total`). When the user's figure doesn't say ("250 per year"), the agent asks once whether that's the total or per square metre.

**Desired start (N11).**
- New `FieldKey.DESIRED_START`, value `YYYY-MM` or `asap`, in the `property` group, optional. "From January" → derived `2027-01` (evidence: their words), confirmed with a value button; "as soon as possible" → `asap`, source user.
- The review card, the case brief and the submission payload (`domain/payload.py`) show it. Yardi's payload carries it as `desired_start` (mock; G8).

**Mall matching (N12).**
- `MasterData.match_mall(text) -> MallMatch` (`app/domain/master.py`): normalise (case, spaces, "mall", Arabic letters), then exact id, name or `aliases`; then close spellings with `difflib.SequenceMatcher` (standard library), ratio ≥ 0.8.
- `update_draft` passes every `malls` entry through it. One match → the id. Two or more → nothing written, a `choice` card for `malls` with the candidates, and `[tool] mall_ambiguous`. None → `mall_not_found` and the model calls `show_mall_picker` (unchanged).
- Master data malls gain `aliases` (seed: common short forms, and Arabic names). Nakheel Mall isn't in the seed (G7); the tests use Mall of Arabia and Riyadh Mall A with misspellings.
- Watch item from 10 Nov ("Mall of Arabia" passed as a city) is closed by this.

### 3.6 Track your inquiry (B4; N14, M33, X4)

**Page.** `/inquiry/track` (`TrackPage.tsx`): reference and email → "If those details match an inquiry, we've sent a 6-digit code to that email." → code field → on success, opens the case page (§3.7). Linked from the public page's footer and from every email.

**API.**
- `POST /api/inquiries/track {reference, email}` → always `202 {"sent": true}`. If the reference exists and the email equals the case's primary email (case-insensitive), a code goes to that email (template `track_code`). Rate limit: 5 per hour per reference and 20 per hour per IP (`slowapi`, `app/api/limiter.py`).
- `POST /api/inquiries/track/verify {reference, email, code}` → `200 {"token": "<track token>"}` or `400 track_code_invalid` (the same error for a wrong code, an unknown reference and an expired code). The token is the existing `track` token (`tokens.issue(..., "track", reference)`), which `POST /api/cases/open` already accepts.
- **Codes.** New `TrackCodeService` (`app/services/track_code.py`, mock): 6 random digits, valid 10 minutes, single use, 3 attempts, then a new code is needed. Stored hashed. Never logged, never in an audit payload (only `track_code_sent` and `track_code_verified` with the reference).
- **Verifying the email.** A verified code proves the email; if the case still has `email_unverified`, it applies `contact_email_verified` (§3.4).

**X4: the General Inquiry agent's contract.** The GI agent asks the user for the reference and email, calls `track`, lets the user type the code into its own UI, calls `track/verify`, then reads `GET /api/inquiries/{reference}?t=<token>` (existing). The response gains `owner_label` (§3.7). The contract goes in `docs/spec.md` §API with an example. Building it into the GI agent is that team's work.

### 3.7 The case page: status, actions, follow-up (B4; N15, N16, N17, N18, M35)

**Status on the case page (N15, N16).**
- The tracking link (`actions.tracking_url`, used by `submission_email` and `submission_sms`) points to `/inquiry/case?t=<track token>`, like the request links (`workflow/service.py: case_url`) already do. `/inquiry/status/:reference` redirects there with the same token.
- `CasePage.tsx` shows a `StatusStrip` above the chat: reference, `owner_label`, the waiting items, last update. The full stage timeline (`ProgressStages`) folds under "Show progress".
- `services/status.py: _from_case`: when any request is open, `owner_role` is `applicant` and `owner_label` "With you"; otherwise `owner_label` is "With the " + the role's name from `ROLE_LABELS` (`workflow/models.py`): Leasing Admin, Regional Sales Manager, or Regional Product Line Manager (Media or Specialty). `email_unverified` adds "Confirm your email" to `waiting_on_you`.

**Action-only case mode (N17, M35).**
- In `mode: case` the `Composer` isn't rendered. The case agent still writes the opening and acknowledgement messages.
- Each open request's card carries its own actions:
  - Re-upload: per document, Upload or Replace, and "Add a comment" (`document_upload` card, existing `resubmit_documents`).
  - Forecasted Sales Data: Upload and comment (`sales_data_upload`).
  - Contacts: see "Contacts on cards" below.
- **UI action `case_comment {request_id | null, doc_type | null, text}`** (max 1,000 characters). New case event `applicant_comment` (actor applicant, any status before `sent_to_yardi`, no status change), `case.comments` (new list), audit `applicant_comment` (text kept on the case, not in the audit payload), reviewer email `applicant_comment`. The console shows it in the timeline and under the document it's about.
- **"Send a follow-up"** shows when nothing is waiting: the same action with no request. At most 3 a day (policy `case.max_follow_ups_per_day: 3`).
- The model gets `[ui_event] comment_sent` (with the document type, not the text). `case_prompt.md` changes: never invite typing; point to the buttons; acknowledge comments in one line.

**Contacts on cards (N18).**
- The contacts card (`build_contacts_card`) is the only way to give them: Authorized Signatory first (the existing signatory question card: "Yes, it's me" fills it from the primary contact), then Billing Contact with "Same as primary contact" or "Same as the signatory" buttons and the form fields.
- `submit_contacts` is unchanged. `update_contacts` (the model's tool) is removed from case mode, since nothing is typed.

### 3.8 Emails (B1, B4; N13)

- `first_level_approved.txt`: drop "a qualified tenant (Tenant Qualified)"; say the first review is done and the Regional Sales Manager (or RPLM) is reviewing next.
- `submission_email` and `submission_sms`: the tracking link opens `/inquiry/case?t=` (B4).
- New templates: `track_code`, `applicant_comment` (to the reviewer).

### 3.9 Console (B5; N19)

- `DocumentDecisions.tsx`: a rejected document's row gets "Request re-upload" (with the remarks field), which sends `request_reupload` with that document. The separate block in `ActionsPanel.tsx` stays for several documents at once.
- `ActionsPanel.tsx`: on `lead_approved`, the contact details (`ContactList`) render inside the Approve Lead action, not in the left column.
- The console stays internal; this is the only console change this round.

## 4. Design rules (ADRs)

ADR-R1–R7 and ADR-V1–V6 still apply.

| ADR | Decision | Where it shows |
| --- | --- | --- |
| N1 | **Buttons carry values.** A button names what it sets ("Food & Beverage · Café", "Use Sara Ali"), never a generic "Looks right" or "Confirm". Labels come from data, so they're right in Arabic. | §3.2 |
| N2 | **Code picks the options.** The model proposes candidates; code checks ids, expands groups, caps the list and matches mall names. A tap is a UI action, never model output. | §3.2, §3.5 |
| N3 | **Codes and links stay out of the chat.** No verification link, SMS code or Track code is shown in, typed into or passed through the chat or the model. | §3.4, §3.6 |
| N4 | **The holder is whoever must act next.** The status says "With you" whenever a request waits on the applicant. | §3.7 |
| N5 | **No text box after submit.** Case mode is buttons and per-item comments; comments go to the reviewer as written. | §3.7 |
| N6 | **Ask in order, save in any order.** One property question per turn, chosen in code; anything given early is kept. | §3.5 |

## 5. Stories (Playwright)

All in `e2e/tests/demo-18nov/`, tagged `@demo-18nov` and `@scripted`; those marked live are also `@live`. Each ends with `expectFlowPath` where it crosses chart steps.

| Story | What it proves | Live | Day |
| --- | --- | --- | --- |
| NV01 | Media unit type; "coffee and breakfast" gives two category buttons; tap one; the Basic Info opener; value buttons for the Arabic brand name; through to Submit with a `GEO-MED-…` reference | yes | B1 |
| NV02 | The same journey in Arabic: Arabic option and value buttons | yes | B1 |
| NV03 | The SMS code expires (dev clock +61 s); the countdown reaches zero; Resend; the new code works | no | B2 |
| NV04 | Email left unverified: Submit works; the Lease Admin's Approve is refused with `email_unverified`; the link from the outbox clears it; Approve goes through | no | B2 |
| NV05 | Landline only: Submit stays blocked until the email link is used | no | B2 |
| NV06 | Property one at a time; "around 40 sqm and three years" saves both and skips them; "flexible" for budget; start "January"; start date on the review card | yes | B3 |
| NV07 | "mall of arbia" matches Mall of Arabia; "riyadh mall" gives buttons for the Riyadh malls | yes | B3 |
| NV08 | Track: reference + email, code from the outbox, the case page with its status strip. A wrong email gets the same reply and no code | no | B4 |
| NV09 | Re-upload on the action-only case page: replace the Brand Profile, comment on it, resubmit; the strip goes from "With you" to "With the Leasing Admin"; no text box | no | B4 |
| NV10 | Nothing waiting: Send a follow-up. After Approve Lead?: signatory "Yes, it's me", billing "Same as primary contact" | no | B4 |
| NV11 | Console: Request re-upload from the document's own card | no | B5 |

### 5.3 Stories this spec changes

| Story | Change |
| --- | --- |
| `flow-v2/*`, `t1-lifecycle-to-yardi`, `t2-reupload-loop`, `demo.spec.ts` | Tap value buttons instead of "Looks right"; open the email link from the outbox; the case page instead of the status page. Fixed in the milestone whose change breaks them |
| `e2e/tests/fe/cards-confirm-fields.spec.ts`, `cards-verification.spec.ts`, `card-screenshots.spec.ts` | New cards and baselines (B1, B2) |
| `scenario-queries` (`@qa`) | Wording in `docs/scenario-queries.md` (B5) |

## 6. Evaluation

- **New invariant I10.** No reply or card in self-service or case mode contains a verification link, an SMS code or a Track code, and no reply invites the user to type one into the chat. (Extends I2 to Track codes.)
- **New live-eval groups** (`scripts/eval_live.py`, ×3, pass 3/3, each in English and Arabic): `category_options`, `leasing_team_tone`, `email_pending`, `property_sequence`, `mall_fuzzy`, `case_actions`, `track_privacy`. `GROUP=nov18` runs all seven. Their checks are listed in the test plan (MS2).
- **Regression.** The full `eval-live` runs after every prompt change (MS7, MS9, MS11, MS13, MS15); no group may fall below its 10 Nov result beyond `EVAL_TOLERANCE`.
- **KPI.** `questions_per_section` keeps its targets for `unit_and_category` (≤ 2) and `basic_info` (≤ 3); `property_details` is expected to rise to one question per item, by design (N10).
- **Goldens.** Re-recorded for the intake scripts whose wording or cards change, with the reason in the PR.

## 7. Contract changes to fold into `docs/spec.md`

| Day | Change |
| --- | --- |
| B1 | Policy `flow_v2_intake.product_lines` (four), `flow_v2_intake.examples`; card `choice`; tool `show_category_options` (error `no_category_match`); master `sales_category_groups`; actions `choose_option`, `confirm_field`; `confirm_fields` payload without card-level confirm; verification card without `demo_token`; setting `EMAIL_LINK_DEMO` removed; guard rule 9; template `first_level_approved` wording |
| B2 | Policy `verification.otp_ttl_seconds`, `verification.email_required_before`, `verification.email_reminder_hours`; `OtpService.verify` result; note `otp_expired`; verification card `mobile.code_expires_at`; `intake_verified`; blocker `email_unverified` (first approval); case event `contact_email_verified`; audit `contact_email_verified` |
| B3 | `FieldKey.DESIRED_START`, `rent_basis`, `draft.flexible`; tool `mark_flexible`; `MasterData.match_mall`, mall `aliases`; tool notes `mall_ambiguous`, `mall_not_found`; property hint order; payload `desired_start` |
| B4 | `POST /api/inquiries/track`, `POST /api/inquiries/track/verify`; `TrackCodeService`; templates `track_code`, `applicant_comment`; status `owner_label`, `owner_role: applicant`; tracking URLs to `/inquiry/case`; action `case_comment`; case event `applicant_comment`, `case.comments`; policy `case.max_follow_ups_per_day`; case mode without composer; `update_contacts` out of case mode; invariant I10 |
| B5 | Console: document-level `request_reupload`; contacts inside Approve Lead |

## 8. Decisions, assumptions and gaps

All nine questions from the demo were answered from the transcript (M27–M35, 23 Nov). M29, M30 and M31 go to Muzammil to confirm; the rest stand unless he objects. They're in `docs/assumptions.md` ("18 Nov demo decisions").

| Code | Decision |
| --- | --- |
| M27 | No "Looks right" on any card; buttons carry the value (§3.2) |
| M28 | Our wording for "what do you sell", with examples in config (§3.3) |
| M29 | The email doesn't block intake or Submit; it must be verified before the Lease Admin's first-level approval. Landline only: before Submit (§3.4). *To confirm* |
| M30 | The SMS code is valid 60 s, with a countdown and Resend after expiry (§3.4). *To confirm* |
| M31 | Size, budget, lease length and start date are each asked once, in order; "flexible" is an answer; none blocks Submit; the budget basis is asked when unclear (§3.5). *To confirm* |
| M32 | Inventory from Yardi behind `InventoryService`; the tenant sees filtered malls only ([`unit-matching.md`](unit-matching.md)) |
| M33 | "Track your inquiry": reference + email, a code to the email on file; no phone lookup (§3.6) |
| M34 | Media and Specialty offered now; RPLM at the final level (§3.1) |
| M35 | Case mode is buttons and per-item comments; a follow-up when nothing is waiting (§3.7) |

Gaps found in the code, decided 23 Nov:

| Gap | Decision |
| --- | --- |
| G6: master data has 7 flat categories, so "retail" can't open into "lifestyle, fashion, sportswear" yet | Add `sales_category_groups` over the 7 seed categories now; the app's full list is a data change when Cenomi shares it (follows G4) |
| G7: Nakheel Mall, Muzammil's example, isn't in the seed malls | Tests use seed malls with misspellings; real mall names and aliases come with Cenomi's master data |
| G8: the Yardi mock has no start-date field | The mock payload carries `desired_start`; the real mapping comes with Yardi access |

## 9. Out of scope

- Unit matching, the counter-offer, the RSM's suggested unit (X1–X3, from 7 Dec).
- The agent test panel (X5).
- The Tenant Central review screens; our console stays internal.
- Lookup by phone on the Track page.
- The General Inquiry agent's own UI for X4.
- Real Tenant Central, Azure AD, SMS, email and Yardi integrations (mocked, golden rule 5).
