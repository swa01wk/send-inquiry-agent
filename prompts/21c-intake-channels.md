# Step 21c — Intake channels: call-centre assisted intake and existing tenants

Read first: @docs/specs/intake-channels.md @docs/specs/workflows-7-1.md (§7.1.1 a2 and §7.1.2 rows) @docs/specs/l3-reliable-intake.md (sections 3.2, 3.7) @backend/app/agent/system_prompt.md @backend/app/agent/tools.py @backend/app/domain/models.py

**Start in plan mode:** show the `staff` source and where confirmation rules change, how assisted and existing-tenant modes reuse the intake agent (prompt variants, tool allowlists), the `complete` token flow, the tenant directory and prefill function, and the new pages. Wait for approval before writing code.

## Goal
Every way into an inquiry in requirements §7.1 works: a call-centre executive can raise one for a caller, who completes it from an emailed link; an existing tenant raises one from Leasing Opportunities with their details prefilled; and the public page sends existing tenants somewhere useful.

## Build
**Backend**
1. `Source.staff` (spec §3.1): unconfirmed until the applicant confirms; `can_submit` blocks on it; audit actor is the executive.
2. `Inquiry.channel`, `created_by`, `tenant_id` (spec §3.8); show the channel in the case brief and queue.
3. `TenantDirectory` and `OpportunityCatalogue` mocks from `data/mock_world/tenants.json` and `opportunities.json` (spec §3.4, §3.5). `1010000000` maps to a tenant; add a second tenant with two brands.
4. `prefill_from_tenant(draft, tenant, brand_id?)` (spec §3.4), used by every channel.
5. Assisted mode (spec §3.2): a prompt variant and tool allowlist for the intake agent; `staff` writes; `existing_cr_choice` card and action; `send_application_link` tool and action; `complete` token; `complete_application` template; handoff cases listed for executives.
6. Completing from the link (spec §3.3): `/inquiry/verify` with purpose `complete` verifies the email and resumes; `basic_info_review` card; `proceed_basic_info` action confirms `staff` and `verified` values.
7. Existing-tenant mode (spec §3.5): `/api/tenant/*`; raising from an opportunity prefills and preselects; `signed_in_skips_verification`; My inquiries.
8. Public page with an existing CR (spec §3.6): `sign_in_prompt` card for `sign_in`; prefill and `basic_info_review` for `allow_inquiry`.
9. Lifecycle differences (spec §3.7): contacts prefilled at second review; `remove_contact` console action → `contact_removed`; `IdentityService.has_account` before every invite.
10. Fold spec §5 into `docs/spec.md`; add D1–D8 to `docs/assumptions.md`; update `docs/STATUS.md` (row 21c).

**Frontend**
1. `/callcentre`: mock executive sign-in, New inquiry, the chat in assisted mode, handoff cases list, `send_link` and `existing_cr_choice` cards.
2. `/tenant`: mock tenant sign-in; `/tenant/opportunities` (filters by city and product line; Raise inquiry); `/tenant/inquiries` (My inquiries).
3. `basic_info_review` card (Edit per field, Proceed); `sign_in_prompt` card; "From the call centre" source badge.

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE, AGENT-DET (assisted and existing-tenant allowlists, `staff` confirmation rule, prompt snapshots for both modes), FE (new pages and cards), INT (stories S9–S12, T10). New prompt variants, so AGENT-LIVE (new `channels` group: executive dictating a caller's details; existing tenant with two brands) and E2E-LIVE (S9 live).
- `tests/channels/`: `staff` values block submit until Proceed; Proceed confirms only what the card listed; an edit on the card is saved as `user`; the `complete` token verifies the email once.
- Existing CR in assisted mode offers both choices; "sign in" closes the inquiry without submitting.
- Existing-tenant prefill copies exactly the policy's fields; documents on file are referenced, not copied; verification is skipped only for a signed-in tenant.
- `has_account`: an existing tenant's primary contact is never invited.
- Access: no console or portal API works without its mock identity, and a tenant can't read another tenant's inquiries.

## Acceptance criteria
- Gate rows C1–C6 pass (`docs/specs/intake-channels.md` §2), and L3 E10.
- Parity suite and stories S1–S8 still green.

## Verify
```
make ci
```
