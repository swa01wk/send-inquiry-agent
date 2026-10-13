# Step 02 — Seed data, FAQ and mock services

Read first: @docs/spec.md (sections 8 and 9) @docs/assumptions.md @.cursor/rules/backend.mdc

## Goal
Create the FAQ, the service interfaces with mock implementations, and the session store.

## Build
1. `app/data/faq.json`: 10 entries covering the topics in spec section 9. Write warm, short answers (≤ 3 sentences). Mark unknown facts `[to be confirmed]`; never invent timelines or policies. Add `app/domain/faq.py` with `search_faq(query, k=2)` (keyword + token overlap scoring, no external libs).
2. `app/services/` — a `Protocol` per service plus a `Mock*` implementation, exactly as spec section 8:
   - `cr.py`: `CrService.verify(cr_number) -> CrResult(exists, company_name?, company_address?)`;
   - `otp.py`: `OtpService.send(session_id, email, phone)`, `verify(session_id, code) -> bool`. Never log the code;
   - `storage.py`: `StorageService.save(session_id, doc_type, filename, stream, size) -> DocumentRef`, `delete(...)`. Stream to disk in chunks and stop as soon as the size exceeds the limit; never read file content for any other purpose;
   - `submit.py`: `SubmitService.submit(draft, master) -> reference` (`GEO-{code}-{6 digits}`), keeping the submitted payload in memory;
   - `status.py`: `StatusService.get(reference)`.
3. `app/services/container.py`: builds the services from `Settings`; one place to swap mocks for real adapters later.
4. `app/sessions.py`: `SessionStore` (in memory) holding `Session(id, draft, created_at, last_seen, cards_shown: set[str], card_counter)`, with `create`, `get` (raises `SessionNotFound`, honours `SESSION_TTL_MINUTES`) and `touch`. Thread-safe with an `asyncio.Lock` per session.

## Tests
- Mock CR returns the three documented behaviours.
- OTP: right code verifies; wrong code doesn't; the code never appears in captured logs.
- Storage rejects oversize streams without leaving a partial file; deletes work.
- Submit reference format matches `^GEO-(STR|MED|SPC|OFF)-\d{6}$` for each unit type.
- FAQ search returns the review-time entry for "how long does approval take".
- Session TTL expiry.

## Verify
```
cd backend && uv run pytest -q
```
