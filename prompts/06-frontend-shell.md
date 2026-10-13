# Step 06 — Frontend shell, tokens and layout

Read first: @docs/design-spec.md (sections 1–3, 8) @design/prototype.dc.html @.cursor/rules/frontend.mdc

## Goal
The page frame from the prototype with empty panels, plus typed contracts and a mock mode.

## Build
1. `src/styles/tokens.css`: copy the tokens block from design spec section 1 exactly. `global.css`: box-sizing, body background `var(--color-page)`, font, focus-visible ring, reduced-motion rules.
2. `src/types/contracts.ts`: TypeScript types mirroring spec sections 6–7: `ChatRequest`, `SseEvent` (discriminated union), `UiCard` and each card payload, `DraftSummary`, `Phase`, `Source`.
3. Layout components (`components/layout/`): `AppHeader` (wordmark + "Tenant Central" + "العربية" pill), `Breadcrumb`, `PageShell` (container, title block with the exact intro copy, two-panel row that wraps under ~920px).
4. Placeholder `ChatPanel` and `DraftPanel` boxes at the right sizes (820px tall, radius 20, borders) so the layout can be checked.
5. `src/mocks/fixtures.ts`: a realistic `DraftSummary` at three stages (empty, mid-way, complete) and one example payload per card type, taken from the prototype's sample data (Bean Street, Ahmed Al-Harbi, Riyadh Mall A–D).
6. `src/config.ts`: reads `VITE_API_BASE` and `VITE_MOCK`.

## Acceptance criteria
- At 1440px the page matches the prototype's frame (header, breadcrumb, title, two panels side by side). At 390px the panels stack.
- No hex values outside `tokens.css` (add a test or lint check that greps for `#` colours in `src/**/*.{ts,tsx,css}` except `tokens.css`).
- `tsc --noEmit` and `vitest` pass.

## Verify
```
cd frontend && npm run test && npx tsc --noEmit && npm run dev
```
Open http://localhost:5173 at desktop and phone widths.
