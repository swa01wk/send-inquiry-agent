# Step 17 — Business rules as policy configuration

Read first: @docs/specs/l3-reliable-intake.md (sections 3.7, 3.8) @backend/app/domain/validation.py @backend/app/domain/rules.py @backend/app/agent/system_prompt.md

## Goal
Every Cenomi rule the agent enforces lives in one validated policy file, so a rule change is a config edit and the prompt can never contradict the code.

## Build
1. `app/policy/policy.yaml` and `app/policy/config.py`: a `PolicyConfig` (Pydantic) loaded once at start-up from `POLICY_PATH`. A bad file stops the app with a clear error. It holds:
   - product lines (Store, Media, Specialty; Office removed);
   - `existing_tenant_policy` (`sign_in` | `allow_inquiry`);
   - `max_malls_per_inquiry`;
   - allowed phone countries;
   - verification channels;
   - resend cooldown and hourly cap;
   - required and optional documents.
2. Read the policy instead of constants in:
   - `validate_malls`;
   - `classify_contact_number`;
   - `can_submit` (documents);
   - `verify_cr` (existing-tenant policy);
   - the mall picker's `max_select`;
   - the document card.
3. Remove `office` from `master_data.json` and the `OFF` unit code; keep the reference format for the remaining codes.
4. `prompts.py` renders a short "Rules in force" block from the policy into the system prompt. Delete rule statements from `system_prompt.md` that the block now covers (one mall, phone countries, verification channels).
5. `app/domain/master.py`: a `MasterDataSource` interface with `SeedMasterDataSource` (today's JSON) and a stub `CenomiMasterDataSource`, cached with a daily refresh and a last-good fallback. Add Arabic mall aliases to the seed data.

## Tests (`tests/policy/`)
For each policy value, flip it in a test policy and assert the behaviour changes without code changes:
- `max_malls_per_inquiry: 2` accepts two malls;
- `existing_tenant_policy: allow_inquiry` lets an existing CR continue;
- a phone country list rejects other countries;
- removing a required document clears its blocker.

## Acceptance criteria
- No business rule constant remains in the validators, rules or prompt that the policy covers (grep check in a test).
- The parity suite passes with the default policy, after updating goldens for the Office removal.

## Verify
```
cd backend && OPENAI_API_KEY= uv run pytest tests/policy tests/domain tests/parity -q
```
