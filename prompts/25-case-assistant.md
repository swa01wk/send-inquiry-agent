# Step 25 — Case assistant: links, case status, re-upload, outcome framing

Read first: @docs/specs/l4-outcome-assistance.md (sections 3.5, 3.8, 3.9) @backend/app/agents/ @backend/app/auth/tokens.py @docs/agent-system-prompt.md

**Start in plan mode:** show the `case` agent spec (tools, prompt outline, guard rules), the `case` token and resume-in-case-mode flow, and the re-upload card and action. Wait for approval before writing code.

## Goal
Every link the applicant gets after submitting opens the same case in chat, where the agent explains where it stands and what's needed, and takes re-uploads without redoing intake.

## Build
1. Token purpose `case`, scoped to one request id, valid until the request closes. `/inquiry/case?t=` resumes a session in case mode (`track` tokens open it read-only plus follow-on).
2. Replace the M0 `status` agent with `app/agents/case/` (registry entry, tool allowlist per spec §3.5, its own `system_prompt.md`):
   - outcome framing: stage, owner role, what the applicant can do now; no promises or timelines;
   - rejection: explain remarks plainly, offer `policy.after_rejection`; never reopen;
   - approvals: explain the Azure AD invitation (first level) and the proposal stage (final).
3. Tools: `get_case_status`, `request_reupload_documents` (emits `document_upload` with `mode: "reupload"` and `requested_doc_types`), plus the shared `search_faq`, `suggest_replies`, `start_follow_on`, `request_handoff`.
4. UI action `resubmit_documents`: checks every requested document was replaced after the request, then fires `documents_resubmitted`; note `[ui_event] documents_resubmitted` or `resubmit_blocked <doc_types>`. Replaced files move to `document_history`.
5. New `case_status` card: stage, owner role, last change, open requests with the reviewer's remarks. Shown at the start of a case session and after any case change (note `case_updated <event>`).
6. Guard rules for the case agent: no claim of resubmitted, approved, accepted or sent without the matching note; no reviewer names.
7. Status page: the full lifecycle and "Waiting for you" with buttons to the case link (spec §3.8).
8. Frontend: `CaseStatusCard`, re-upload mode in `DocumentChecklistCard`, the `/inquiry/case` route.
9. Update `docs/spec.md` and `docs/STATUS.md` (row 25).

## Tests
**Layers** (`docs/specs/testing-strategy.md`): BE, AGENT-DET (case agent allowlist, guard), FE (case status card, re-upload mode, case page), INT (stories T2, T3). New agent, so AGENT-LIVE (new `case` group) and E2E-LIVE (T2 live).
- Case-mode resume with each token purpose; an expired or closed-request link explains and offers the tracking page.
- The case agent can't call any intake write tool (allowlist).
- Re-upload: only requested types accepted; resubmit blocked until all are replaced; the case returns to `first_review`.
- Guard: the false-claim rules for the case agent.
- **Playwright:** stories T2 and T3 (applicant and reviewer contexts).
- Live eval: a "Case" scenario (status question, re-upload, rejection explanation).

## Acceptance criteria
- Gate X3 holds for the re-upload loop (no intake questions).
- Parity suite and L3 stories still green.

## Verify
```
make ci
```
