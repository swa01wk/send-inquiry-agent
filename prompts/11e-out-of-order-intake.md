# Step 11e: Out-of-order intake (frontend and agent prompt)

Read first: @docs/spec.md §2 ("What's left", "Space values as people write them"), §4 ("Quiet actions"), §5 rule 7, §7 `DraftSummary` · @docs/STATUS.md §6 (the five "Manual test 2 Nov" rows) · @.cursor/rules/frontend.mdc @.cursor/rules/agent.mdc · @frontend/src/components/chat/inquiryProgress.ts @frontend/src/hooks/useChatSession.ts @frontend/src/state/chatStore.tsx @backend/app/agent/system_prompt.md @docs/agent-system-prompt.md

Like 11c, this step runs **before** `12-baseline-parity.md`, so the golden transcripts record the corrected behaviour.

## Why
A manual test on 2 Nov did steps out of order, which real users do. The applicant:
1. uploaded the documents before opening the email link;
2. corrected the unit type after the verification card was shown;
3. asked "what's next" and "can you give me the submit button".

The draft panel was right throughout ("Contact not verified yet"). The guidance was wrong:
- The agent said "everything's in" and "you're at the last step".
- It pointed to a review card that `can_submit` (correctly) never showed.
- The step tabs showed **Documents** with no tick, because the tabs are strictly linear.
- A click on **Open verification link (demo)** was dropped silently while a reply was streaming.

The backend half is already merged (the PR that adds this prompt):
- `rules.remaining_steps`, and the new fields `checks.remaining` and `checks.next_step`;
- the still-needed hint and guard rule 7;
- `documents_complete still_needed=…`;
- quiet card actions;
- tolerant number and period parsing.

This step does the frontend and the agent prompt.

## Build

### Frontend
1. **Contract types.** Add the following to `DraftChecks` in `types/contracts.ts`:
   ```ts
   remaining: RemainingStep[]
   next_step: RemainingStep | null
   ```
   with this type:
   ```ts
   type RemainingStep = 'cr' | 'fields' | 'verify_email' | 'verify_mobile' | 'documents' | 'terms'
   ```
   Update the mock fixtures and scenario validation in `frontend/src/mocks/` so every `checks` object carries both fields.
2. **Independent step tabs** (`inquiryProgress.ts`, `ProgressStages`). Work out each tab's state on its own:
   - **Company:** done when the CR isn't pending and no company field is missing or unconfirmed.
   - **Brand and Space:** done when the group's required fields are filled and confirmed.
   - **Contact:** done when the contact fields are done and `checks.contact_verified` is true.
   - **Documents:** done when `required_docs_uploaded >= required_docs_total`.
   - **Review:** done when the inquiry is submitted.

   The current tab comes from `checks.next_step`:
   - `cr` → Company.
   - `fields` → the first group with a gap.
   - `verify_email` or `verify_mobile` → Contact.
   - `documents` → Documents.
   - `terms` → Review.

   Done tabs after the current one keep their tick: documents uploaded before verification show **✓ Documents** while **Contact** is current.
3. **A tab click shows its card.**
   - Contact scrolls to the verification card.
   - Documents scrolls to the documents card.
   - Review scrolls to the review card.
   - Company, Brand and Space scroll to the latest confirm card with that group's fields.

   Use `scrollIntoView({block: 'center'})` plus a short highlight, and respect `prefers-reduced-motion`. If the card hasn't been shown yet, nothing happens: the tab is not a button until then. Use `aria-disabled`, and keep the label readable.
4. **Next-step strip** above the composer. Show one short line when **both** of these are true:
   - `checks.next_step` is `verify_email`, `verify_mobile`, `documents` or `terms`;
   - that card is out of view (use an `IntersectionObserver` on the card).

   The line, by step:
   - `verify_email`: "Next: open the link we emailed you"
   - `verify_mobile`: "Next: enter the SMS code"
   - `documents`: "Next: upload the required documents"
   - `terms`: "Next: review and submit"

   Each line has a **Show** button that scrolls to the card. Hide the strip while collecting (`cr`, `fields`), after submit, in assisted mode and in form mode. It's an `aria-live="polite"` region; announce only changes.
5. **No dropped clicks.** `useChatSession.sendAction` currently returns without doing anything while `status === 'streaming'`. Queue the action instead:
   - Keep one FIFO queue in a ref, and flush it when the stream ends (`done` or `error` → idle).
   - Drop duplicate entries for the same action and payload.
   - While an action is queued, its button shows a small "Waiting…" state.
   - Upload calls are separate HTTP calls and are unaffected.
6. **Quiet actions** (spec §4) stream cards, `draft` and `done` with no `token`. After a card action, don't show the typing indicator until 400 ms have passed without `done`, so a quiet action doesn't flash the dots.

### Agent prompt
Keep `backend/app/agent/system_prompt.md` and `docs/agent-system-prompt.md` in sync.

7. **Rule 6, `documents_complete`.** Replace the last sentences with:

   > When `[ui_event] documents_complete` arrives with `still_needed=…`, thank them for the documents in one sentence and point to what's still open (the email link or the SMS code on the verification card). Without `still_needed`, thank them, mention optional documents once, and point to the review card.
8. **Flow at a glance.** Add:

   > The hint's "Still needed before submit" line is what's left. The user can do it in any order. Never call anything the last step, or point to Submit, while it lists more than the terms. When they ask what's next or for the submit button, name what's open and point to that card. If only the terms are left, call `show_review`.
9. **`[ui_event]` list.**
   - Remove the `document_number_set` line: that note no longer reaches the agent.
   - Add one line: wrong codes, manual resends and one channel verified are shown on the card and don't reach the agent. `otp_resent` now arrives only after the last wrong code, when a new code was sent automatically, so say so.
10. **Names typed by the user.** "Sara Ali" is source `user`. Split it into first and last name without a confirm step; it isn't a derived value.
11. **No self-narration.** Don't describe what you're doing ("I'm checking the summary card now"). Say what the user should do, or nothing.
12. **Arabic brand names.** Transliterate by sound and keep vowels short: "Bean" → «بين», not «بيان». The user still confirms the result.
13. **Examples.** Add a front-loaded example in which the user gives brand, space, budget, lease and contact in one message:
    - The assistant calls `update_draft`, writing area, rent, `rent_period` and `lease_period`, then calls `send_verification`.
    - The reply doesn't ask for contact details.
    - If `update_draft` rejects a space value, the reply names that value and asks for it once.

    The existing Lumen example still asks for contact correctly, because that user didn't give any.
14. **Regenerate the prompt snapshots:**
    ```
    cd backend && UPDATE_SNAPSHOTS=1 uv run pytest tests/agent/test_prompt_snapshot.py
    ```

### Scripted e2e
15. Quiet actions remove the agent turns that used to follow `email_verified` (when the mobile is still pending), `otp_failed`, manual resends and `document_number_set`. The scripted suite still passed on the backend PR (76/76, `e2e.yml` run 41442787865), because cards come from the guard and the phase. Even so, check that the step lists in `backend/tests/e2e_scripts/` still read in order (for example `s1-happy-path` and `18-demo-sequence`) whenever you touch them.
16. **New story S14: documents before verification** (`e2e/tests/s14-out-of-order.spec.ts`, scripted `s14-out-of-order.json`). The story runs in this order:
    1. CR, then the bundle message.
    2. Enter the SMS code.
    3. Upload both documents.
    4. Assert there's no review card, the latest reply mentions the email link, the Documents tab has a tick and Contact is current.
    5. Click the Contact tab: the verification card scrolls into view.
    6. Open the demo link, then assert the review card appears.

## Tests
Layers (`docs/specs/testing-strategy.md`): FE (Vitest), BE, INT, AGENT-DET. The prompt changes, so this step also runs AGENT-LIVE (`make eval-live`, including the new scenario "O out of order") and an E2E-LIVE smoke run.

Vitest:
- `inquiryProgress`: documents done while contact is pending; a correction after verification doesn't untick Documents; `next_step` decides the current tab.
- `ProgressStages`: a click on a tab scrolls to its card; a tab whose card hasn't been shown is `aria-disabled`.
- Next-step strip: shown only for the four steps and only when the card is out of view; hidden in assisted mode and form mode.
- `useChatSession`: an action sent while streaming is queued and sent after `done`; duplicate entries are dropped.
- Quiet action: no typing dots before 400 ms.

## Acceptance criteria
- Repeat the 2 Nov manual run (`docs/demo-queries.md`, Flow 1, with documents uploaded before the email link):
  - no "last step" or "everything's in" while the email is open;
  - the Documents tab is ticked;
  - the strip says "Next: open the link we emailed you";
  - the demo link click registers even if pressed while a reply is streaming.
- The same run with the ultra-dense turn 4 keeps 30 sqm, 250,000 SAR yearly and 3 years.
- `make ci` is green, and `make e2e-int` passes on desktop and mobile.

## Verify
```
make ci && make e2e-int && make eval-live
```
Update the five "Manual test 2 Nov" rows in `docs/STATUS.md` §6, and add a row for 11e in §2.
