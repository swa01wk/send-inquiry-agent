# Spec: UI and agent bugs from the demo run (2026-10-14)

Found in a manual browser run on `main` (`d62eba6`). Screenshots: `docs/specs/screenshots/demo-run-01.png` … `07.png`.

Demo queries used:

```text
Marhaba
My CR number is 1010123456
Yes, that's correct
Bean Street specialty coffee kiosk at Riyadh Mall A — about 30 sqm, budget up to 250,000 SAR per year, 3-year lease. Sara Ali, sara@beanstreet.example, +966501234567
Yes, all correct
Actually we want a full store unit, not specialty or kiosk.
What documents do I need to upload?
Can I review and submit now?
```

Plus uploading a real PDF to Company Profile and Brand Profile.

## Summary

| ID | Bug | Severity | Area |
| --- | --- | --- | --- |
| B1 | Valid PDFs rejected: "That file type isn't supported." | Blocker | Frontend + API contract |
| B2 | Two confirm cards per step; second shows wrong badge; first stays stale | High | Backend (draft_ops, tools, actions) + frontend safeguard |
| B3 | Bot text loses line breaks and bullets; replies repeat what the card shows | Medium | Frontend + prompt |
| B4 | Agent assumes details the user never gave ("specialty coffee" before the user said it) | Medium | Prompt |
| B5 | Documents reply never says Company Profile and Brand Profile are required | Medium | Prompt |
| B6 | Welcome chip "I have my CR number" gets a robotic reply | Medium | Frontend + API |
| B7 | Draft panel shows "Office landline: Not yet collected" when a mobile was given | Low | Frontend |

---

## B1 — Valid PDFs rejected

**Seen:** screenshots 06, 07. A real `.pdf` shows "That file type isn't supported." on both required documents. Nothing reaches the backend.

**Cause:** format mismatch on `allowed_extensions`.
- Backend `app/api/cards.py` sends `sorted(ALLOWED_EXTENSIONS)` → `["doc", "docx", "jpeg", "jpg", "pdf", "png", "xlsx", "zip"]` (no dots).
- Frontend `components/cards/documentFileCheck.ts` compares `fileExtension(name)` → `".pdf"` (with dot). Never matches.
- The same list feeds `<input accept>`, which needs dots (`.pdf`).
- Mock fixtures (`frontend/src/mocks/fixtures.ts`) use dotted values, so tests and `VITE_MOCK=1` passed while the real backend fails.

**Fix:**
1. `backend/app/api/cards.py`: card payload sends dotted extensions (`[".doc", ".docx", …]`). Keep `ALLOWED_EXTENSIONS` in `validation.py` undotted; convert only in the payload.
2. `frontend/.../documentFileCheck.ts`: normalise both sides (lowercase, add leading dot if missing) so either format works.
3. `accept` attribute receives dotted values.
4. Update `docs/spec.md` §7 (`document_upload.allowed_extensions` are dotted).

**Acceptance:**
- Backend test: `document_upload` payload contains `".pdf"`.
- Frontend tests: `Company_Profile.PDF` passes with `["pdf"]` and with `[".pdf"]`; `notes.txt` fails; a 6 MB file fails with "That file is over 5 MB."
- Manual: upload a real PDF to both required rows → "Uploaded · <name> · <size>"; "2 of 2 required uploaded".

---

## B2 — Duplicate confirm cards, wrong badge, stale card

**Seen:** screenshots 02–05.
- After "Yes, that's correct": the original company card still shows "From CR · confirm" + "Looks right", and a **second** card appears with the same fields marked "Suggested · confirmed".
- Same for the brand card after "Yes, all correct".
- Company fields now show "Suggested" instead of "From your CR".

**Cause:**
1. On the confirmation turn the model calls `update_draft` again with the **same** values as `derived`.
2. `domain/draft_ops._apply_field` always overwrites: source drops from `verified` to `derived`, `confirmed` resets to false.
3. `agent/tools.update_draft` creates a **new** confirm card for every derived key written (`allocate_confirm_card_id`).
4. `confirm_fields` then confirms and updates the *last* confirm card (the new one), so the original card is never updated.

**Fix (backend, root cause):**
1. `_apply_field`: if the validated value equals the current value, do nothing — keep source and `confirmed`, do not add to `written_keys`.
2. Never replace a `user` or `verified` value with a `derived` write of the same value (covered by 1). A `derived` write with a *different* value over a `verified` value is allowed (correction) but is reported in the tool result.
3. `update_draft`: create or update a confirm card only for derived keys whose value actually changed. If an existing confirm card already lists any of those keys, update that card (same `card_id`) instead of allocating a new one.
4. `confirm_fields` tool and `confirm_card` action: find the card(s) containing the confirmed keys via `session.confirm_card_keys` and update those cards in place. Never create a card when confirming.

**Fix (frontend safeguard):**
5. `state/chatStore.tsx` `applyUiCard`: if a `confirm_fields` card arrives with a **new** `card_id` whose field keys overlap an existing confirm card, merge into the existing card (rows by key, newest wins) instead of adding a card.
6. `ConfirmFieldsCard`: when `all_confirmed` is true, hide "Looks right".

**Expected card lifecycle:**

| Step | Cards visible |
| --- | --- |
| CR verified | One company card: "From CR · confirm" + "Looks right" |
| "Yes, that's correct" | Same card → "From your CR", no button |
| Brand summary | One brand card: "Suggested · confirm" |
| "Yes, all correct" | Same card → "Suggested · confirmed" |
| "Actually … full store unit" | Same card, Unit type → Store, badge "You said" |

**Acceptance:**
- Backend: `verify_cr` then `update_draft(company_name, same value, derived)` → source stays `verified`, no new card, tool result says "unchanged".
- Backend: `confirm_fields([company_name, company_address])` emits `confirm-1` with `all_confirmed: true`, no `confirm-2`.
- Backend: correcting `unit_type` to `store` (user) updates the brand card in place.
- Frontend: confirm-1 `[company_name, company_address]` then confirm-2 same keys confirmed → one card, confirmed.
- E2E scenario 18 (see `e2e-playwright.md`).

---

## B3 — Bot text formatting and repetition

**Seen:** screenshot 01. "…pulled in the company details. – Company name: … – Company address: King Fahd Road, Al Olaya, Riyadh A specialty coffee brand…" — newlines and list markers collapsed; the sentence after the address runs into it. The same values are also shown in the card below.

**Cause:** `components/chat/BotBubble` renders plain text with default `white-space`. Prompt doesn't tell the agent not to repeat card contents.

**Fix:**
1. `BotBubble.module.css` `.bubble`: `white-space: pre-line;`
2. Render a safe markdown subset: paragraphs, line breaks, `- ` bullet lists, `**bold**`. No raw HTML. Small in-house renderer or `react-markdown` with HTML disabled (only allowed new dependency).
3. Prompt (see B4/B5 block): "When a card shows values, don't repeat them as a list; one short sentence pointing to the card."

**Acceptance:** `"Line one\n- a\n- b"` renders a paragraph and a 2-item list; `<script>` in text renders as text. Manual: CR turn reply is 1–2 sentences, values only in the card.

---

## B4 — Agent assumes details

**Seen:** screenshot 01. At the CR step the agent says "A specialty coffee brand usually fits well in a kiosk or small shop" before the user mentioned coffee.

**Cause:** the prompt examples use **Bean Street / specialty coffee / Riyadh Mall A**, the same data as the mock CR (`1010123456` → "Bean Street Trading Co.") and the demo script. The model fills gaps from the examples.

**Fix (`backend/app/agent/system_prompt.md`, then copy to `docs/agent-system-prompt.md`):**
1. Replace the example brand with one not in mock data or demo scripts, e.g. **"Lumen Eyewear, an optical store at Jeddah Mall B"** (Arabic: لومن آيوير).
2. Add under "How you sound": "Never assume what the user sells, where, or anything else they haven't told you. A company name is not a brand or a product."

**Acceptance:** E2E scenario 18: no reply mentions "coffee" before the user's message containing "coffee".

---

## B5 — Required documents not stated

**Seen:** screenshot 05. "Please upload any documents you have, if available: CR, VAT, ID, address, or articles are welcome but not required." — never says Company Profile and Brand Profile **are** required.

**Fix (prompt rule 7):** "When you show the documents card, say clearly that Company Profile and Brand Profile are required to submit. Then mention once that CR, VAT, ID, address and articles documents are optional."

**Acceptance:** the reply on the documents turn contains "Company Profile" and "Brand Profile" (E2E 13, 18; live eval).

---

## B6 — Welcome chip "I have my CR number"

**Seen:** screenshot 01. Tapping the chip sends "I have my CR number" as a message; the agent replies "That looks like a message, not the CR number itself…".

**Fix:**
1. `QuickReplyOption` gains optional `action?: "send" | "focus_input"` (default `send`) and `placeholder?: string`. Update `backend/app/api/schemas.py`, `cards.py`, `frontend/src/types/contracts.ts`, `docs/spec.md` §7.
2. Welcome chip "I have my CR number" → `action: "focus_input"`, `placeholder: "Type your 10-digit CR number"`. Tapping focuses the composer and sets the placeholder; **no chat turn**; chips stay visible until the user sends.
3. Prompt: "If the user says they have their CR number but hasn't typed it, reply warmly in one short sentence inviting them to type it." (fallback when typed manually).

**Acceptance:** tapping the chip focuses the composer, placeholder changes, no network request to `/chat`. Typing "I have my CR number" manually gets a friendly one-liner.

---

## B7 — Contact rows in draft panel

**Seen:** all screenshots. "Office landline — Not yet collected" while Mobile is filled.

**Fix:** draft panel (and review card) show one **Phone** row: value from mobile or landline, small hint "Mobile" / "Landline". Hide the empty one. Backend `DraftSummary` unchanged; grouping happens in `components/draft/draftGroups.ts`.

**Acceptance:** with mobile set, panel shows "Phone · +966501234567 · Mobile" and no landline row; required count unchanged (11 of 11).

---

## Regression guard

All existing backend tests, frontend tests and the live eval must still pass. New tests listed per bug. The Playwright suite (`docs/specs/e2e-playwright.md`) covers these end to end, notably scenarios 13 and 18.
