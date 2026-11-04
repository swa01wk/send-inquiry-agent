# Re-demo Day R3 (Sat 7 Nov): type the details, or upload the profiles

Read first: @docs/specs/demo-feedback.md (§2 rows D11 and D12, §3.3, §3.7, §4 ADR-R4, R5 and R7, §6) @docs/assumptions.md (Company and brand details, no CR; Document mismatch) @docs/spec.md @backend/app/agent/system_prompt.md

## Goal
On the no-CR path, the applicant chooses how to give the company and brand details:
- **Type them.** They're checked against the company and brand profiles once those are uploaded.
- **Upload the profiles.** The agent fills the details in for the applicant to confirm.

Any difference warns the applicant and is flagged to the Lease Admin, without blocking submit.

## Backend PR (Claude): lands first; use it, don't rebuild it
- **Extracted fields.** `DocumentReviewResult.fields` is filled by the mock from `mock_world/document_review.json`, keyed by fixture file:
  - company profile: `company_name`, `company_address`;
  - brand profile: `brand_name_en`, `sales_category`, mapped to master data ids.

  New fixtures in `e2e/fixtures/files/`: `company_profile_match.pdf`, `company_profile_mismatch.pdf` and `brand_profile_match.pdf`.
- **Writing them to the draft.** `app/domain/document_fill.py`, `fill_from_review(draft, result) -> (draft, written, checks)`:
  - a field that's empty gets `source: derived`, `confirmed: false` and the evidence `"<Document label>: <file name>, uploaded <time>"`;
  - a field the applicant typed (`source: user`) is compared instead, and never overwritten.
- **Checks.** `app/domain/document_checks.py` compares values (case, whitespace and punctuation ignored, Arabic normalised, categories through master data). A difference becomes `draft.document_checks[field] = {typed, document_value, doc_type}`.
- **Re-upload.** Replacing a profile clears the values that came from the old file and sets them back to unconfirmed. They're filled again from the new result (ADR-R4).
- **Notes to the agent after an upload:**
  - `[ui_event] document_fields <doc_type> filled=<keys>`;
  - `[ui_event] document_mismatch <field>`.

  They carry field names only, never values from the document beyond what's already in the draft summary.
- **Case brief.** Each value shows its evidence, and each mismatch shows "typed X, profile says Y".
- **Tests:**
  - `tests/domain/test_document_checks.py`;
  - `tests/agent/test_document_extract.py`, covering fill, no overwrite, re-upload reset, and confirm before submit (I4 holds);
  - `tests/security/test_document_text_isolation.py`, extended to the fields.

## Your track (Cursor): agent and chat
1. **Intake prompt.**
   - After the CR question is answered No, offer once, in one sentence, a choice: type the company and brand details, or upload the two profiles and you'll fill them in for them to check.
   - Offer `suggest_replies`: "I'll type them" and "I'll upload the profiles".
   - Either answer is fine, so don't push one.
   - If they upload first, don't ask for anything a document filled. Show the confirm card for the filled values.
2. **`[ui_event] document_fields …`:** call `confirm_fields` only through the card. Say in one line what was filled and ask them to check it.
3. **`[ui_event] document_mismatch <field>`:**
   - say in one sentence that the profile shows something different for that field;
   - offer to use the document's value or keep theirs;
   - accept either: keeping theirs is allowed, and the reviewer sees the flag.
4. **Confirm card.** `ConfirmFieldsCard` shows the evidence line for document-filled values ("from: Company Profile, company_profile.pdf").
5. **Documents card.** It shows a small "Details filled from this document" note under each profile that filled something.
6. **Scripted mode and goldens:** `rd-type-or-upload`, both paths, with its golden and frontend fixture.
7. **Live eval group `document_extract`** (spec §6). Add a KPI line for `unnecessary_questions` to the eval report.

## Tests
- Vitest for the confirm-card evidence and the documents-card note; `make e2e-fe`.
- `make e2e-int`: `rd-type-or-upload` passes, along with S1, S14 and `rd-cr-question`.
- AGENT-LIVE: `document_extract` ×3 at 3/3; `intake` within tolerance.
- E2E-LIVE smoke: the self-service persona with uploads.

## End-of-day check
- [ ] No CR → "I'll upload the profiles" → upload both → confirm card with company name, address, brand and category, each with evidence → confirm → no question for those fields.
- [ ] No CR → type a company name → upload `company_profile_mismatch.pdf` → one-sentence warning → keep my value → submit works → the Lease Admin's brief shows the flag.
- [ ] Re-upload a profile after confirming → its values are unconfirmed again, and the review card blocks submit until they're confirmed.
- [ ] `docs/STATUS.md` Re-demo R3 ✅; `docs/spec.md` (spec §7, R3 row); `docs/assumptions.md` rows marked landed; tracker I12, I19 set to Done.
