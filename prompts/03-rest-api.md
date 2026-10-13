# Step 03 — REST API

Read first: @docs/spec.md (sections 6, 7 "UiCard"/"DraftSummary", 10) @docs/design-spec.md (section 7, welcome copy) @.cursor/rules/backend.mdc

## Goal
Expose every REST endpoint in spec section 6, except the chat stream (step 05).

## Build (`app/api/`)
1. `schemas.py`: Pydantic request/response models for every endpoint, `UiCard` and each card payload type in spec section 7, `DraftSummary`, and the error envelope.
2. `cards.py`: builders that turn a draft + master data into each card payload (`confirm_fields`, `mall_picker`, `otp_input`, `document_upload`, `review`, `success`, `quick_replies`), with stable `card_id`s (`confirm-<n>`, `malls`, `otp`, `documents`, `review`, `success`, `quick-replies`). The agent tools reuse these in step 04.
3. Routers:
   - `sessions.py`: `POST /api/sessions` returns the two fixed welcome messages, a `quick_replies` card with the three welcome chips, and the initial `DraftSummary`. `GET /api/sessions/{id}/draft`.
   - `documents.py`: `POST` (multipart `doc_type` + `file`) and `DELETE`. Validate `doc_type`, extension and size; store; update the draft; return `{document, card, draft}` with `changed_keys` empty.
   - `master.py`: `GET /api/master/{kind}` (+ `?city=` for malls).
   - `inquiries.py`: `GET /api/inquiries/{reference}`.
4. Error handling: exception handlers map `SessionNotFound` → 404 `session_not_found`, validation → 400 with the spec codes, and unhandled → 500 with a friendly message.
5. Rate limiting with slowapi (`RATE_LIMIT_IP` on all routes; the per-session limit is added in step 05).

## Tests (`tests/api/`)
- Session creation returns the exact welcome copy and chips.
- Upload: success (draft shows `uploaded: true`, `required_uploaded` increments); wrong extension → 400 `invalid_extension`; 6 MB → 400 `too_large`; unknown type → 400 `unknown_doc_type`; delete works.
- Master endpoints, including malls filtered by city.
- Unknown session → 404 envelope.
- Status endpoint for a known and an unknown reference (seed a submitted inquiry through the submit service in the test).

## Verify
```
cd backend && uv run pytest -q
make dev-backend   # then open http://localhost:8000/docs
```
