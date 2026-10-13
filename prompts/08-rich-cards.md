# Step 08 — Rich cards

Read first: @docs/design-spec.md (section 5, 8) @docs/spec.md (sections 4, 6, 7 "UiCard") @design/prototype.dc.html @.cursor/rules/frontend.mdc

**Start in plan mode:** list each card's props, local state and which `sendAction`/upload call it makes, then wait for approval.

## Goal
Replace the card placeholders with the six interactive cards, plus the shared `SourceBadge`.

## Build (`components/cards/`, `components/draft/SourceBadge.tsx`)
1. `SourceBadge`: the six variants in design spec section 6.
2. `ConfirmFieldsCard`: rows with label, display value and badge; optional "Looks right" text button → `confirm_card`. Rows update in place when the card is replaced.
3. `MallPickerCard`: 2-column grid of `<button aria-pressed>` tiles, count label, "Done" → `select_malls {mall_ids}`; disabled until one is selected. Lock the tiles once `malls` is confirmed in the draft.
4. `OtpCard`: numeric 4-digit input (`autocomplete="one-time-code"`), Verify → `submit_otp {code}` (clear the input after sending), "Resend code" → `resend_otp`, error caption from `attempts_left`, verified state.
5. `DocumentChecklistCard`: a row per document; Upload opens a hidden `<input type="file" accept=…>`; client-side pre-check of extension and size (same messages as the server); per-row uploading spinner; calls `uploadDocument`, then applies the returned card and draft; Remove → `removeDocument`.
6. `ReviewCard`: groups and rows with badges; inline Edit → `edit_field {key, value}` (input with Save/Cancel; Enter saves, Escape cancels); documents and checks list; consent checkbox (local until submit); "Submit inquiry" → `accept_and_submit {terms_accepted: true}`, disabled unless the checkbox is ticked and the payload's only blocker is `terms_not_accepted`; first-blocker hint.
7. `SuccessCard`: reference box with Copy (→ "Copied" for 2s), 3-step timeline, "Track your inquiry" link to `tracking_url`.
8. Wire `CardSlot` to these components and pass the session's actions.

## Tests
- Each card renders its fixture payload and makes the right call on interaction (mock the hook).
- Mall picker: Done disabled with no selection; `aria-pressed` toggles.
- OTP: non-digits stripped; max 4; error caption shows attempts left.
- Documents: a 6 MB file and a `.exe` are rejected client-side without calling upload.
- Review: Submit disabled until consent is ticked; Edit saves via `edit_field`.

## Verify
```
cd frontend && npm run test
VITE_MOCK=1 npm run dev
```
Walk the whole flow and compare each card side by side with the prototype canvas.
