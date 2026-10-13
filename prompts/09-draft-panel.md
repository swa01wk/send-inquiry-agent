# Step 09 — Live draft panel

Read first: @docs/design-spec.md (section 6) @docs/spec.md (section 7 "DraftSummary") @design/prototype.dc.html @.cursor/rules/frontend.mdc

## Goal
The right-hand "Inquiry draft" panel that shows what the agent has collected, live, with provenance.

## Build (`components/draft/`)
1. `DraftPanel`: 820px tall; pinned header (title, description, "Required fields N of 11" with progress bar); scrolling body (`overflow-y: auto; position: relative`).
2. `DraftGroup` + `DraftRow`: groups in spec order; each row has an `id="draft-<key>"`, label, `SourceBadge`, and value or "Not yet collected" (muted).
3. Live update from `draft.changed_keys`:
   - add a flash class to those rows for 1.8s (background `var(--color-flash)`, 0.6s ease);
   - smooth-scroll the body so the first changed row (in panel order) sits 12px from the top. Use the row's `offsetTop` within the scroll body, not `scrollIntoView` (that would also scroll the page);
   - respect `prefers-reduced-motion` (no animation, instant scroll).
4. `ChecksList`: the four checks with filled/outline dots and the label wording from the prototype.
5. `BadgeLegend`.
6. Optional: a "Hide draft" toggle in the chat header that collapses the panel (it's a demo/debug aid; keep it on by default).

## Tests
- Rows render values and badges from a `DraftSummary` fixture.
- Changing `changed_keys` adds and then removes the flash class (fake timers).
- The scroll position is set from the first changed row (mock `offsetTop` / `scrollTo`).
- Progress label and bar width match `required_filled / required_total`.

## Verify
```
cd frontend && npm run test
VITE_MOCK=1 npm run dev
```
As each chat step fills fields, the panel should scroll to and highlight them.
