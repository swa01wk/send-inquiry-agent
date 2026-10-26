# Step 26 — Second-level requests: contacts and estimated sales data

Read first: @docs/specs/l4-outcome-assistance.md (sections 3.1 `TenantContact`, 3.5 "Contacts" and "Sales data") @backend/app/agents/case/ (from step 25) @backend/app/domain/validation.py @backend/app/agent/bundles.py

**Start in plan mode:** show the contacts bundle, how "that's me" reuses the primary contact, the `contacts` and `sales_data_upload` cards, and the two submit actions. Wait for approval before writing code.

## Goal
When a reviewer asks for contacts or sales data, the applicant answers in one or two messages and a card, with nothing they already gave asked again.

## Build
1. `update_contacts(contacts: list[{role, first_name?, last_name?, email?, contact_number?, same_as_primary?}])`:
   - validates with the intake validators (names, email, phone with Arabic digits normalised);
   - `same_as_primary` copies the primary contact as `verified`, unconfirmed;
   - typed values are `user`, confirmed; split names are `derived`, as in intake.
2. `show_contacts_review` emits a `contacts` card: one row per role, required roles from `policy.second_level_contacts`, source badges, edit and confirm like the confirm card.
3. UI action `submit_contacts`: all required roles present and valid, nothing unconfirmed → `contacts_provided`; note `contacts_submitted` or `contacts_blocked <reasons>`.
4. `request_sales_data_upload` emits a `sales_data_upload` card (one file, usual extension and size checks, upload via the documents endpoint with `doc_type=sales_data`). UI action `submit_sales_data` → `sales_data_provided`.
5. Case-agent prompt: one bundle question for contacts; reuse the primary contact when the applicant says it's them; mention optional roles once.
6. Update `docs/spec.md` and `docs/STATUS.md` (row 26).

## Tests
- `tests/contacts/`: required roles enforced from the policy; "that's me" copies the primary contact and needs confirmation; invalid email or phone returns a field error; Arabic digits work.
- Sales data: one file; replace; submit fires the event once; the reviewer gets `sales_data_received`.
- **Playwright:** the contacts part of T1 and story T4.
- Live eval: "Contacts" scenario — all contacts in one message, and "I'm the signatory, billing is …".

## Acceptance criteria
- Contacts fulfilled in at most two typed messages in the scripted story.
- KPI "facts re-asked after submit" stays 0 in scripted runs.

## Verify
```
make test && make lint && make e2e
```
