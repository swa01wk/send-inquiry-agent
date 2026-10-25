# Send Inquiry Agent — design spec

Built from the approved clickable prototype (`design/prototype.dc.html`). Match it closely: tokens, sizes, radii and copy.

## 1. Tokens (`frontend/src/styles/tokens.css`)

```css
:root {
  /* Brand */
  --color-brand: #2E1A5B;          /* deep purple: logo, headings, user bubble, active stage, avatar */
  --color-accent: #C8336B;         /* magenta: primary buttons, send, chip borders, selected mall, progress fill */
  --color-accent-text: #A3214F;    /* magenta text on white (chips, links) — 4.5:1 */
  --color-accent-tint: #FCEEF3;    /* selected mall, "Required" tag */
  --color-brand-tint: #E6DEF7;     /* secondary button (Track your inquiry) */

  /* Surfaces */
  --color-page: #F5F5F7;
  --color-surface: #FFFFFF;
  --color-chat-bg: #FBFAFC;
  --color-subtle: #F3F2F7;         /* reference box */
  --color-muted-fill: #F1EFF5;     /* upcoming stage, "Optional" tag */

  /* Text */
  --color-text: #1C1530;
  --color-text-body: #4A4460;
  --color-text-secondary: #5E5873;
  --color-text-muted: #8A8499;

  /* Lines */
  --color-border: #E6E4EC;         /* panels */
  --color-border-card: #E3E0EA;    /* cards inside chat */
  --color-divider: #F0EEF4;
  --color-input-border: #CFCBDA;
  --color-control-border: #D9D6E2; /* secondary buttons */

  /* Status */
  --color-success-bg: #DDF5E8;  --color-success-fg: #17633F;  --color-success-dot: #1F8A55;
  --color-pending-bg: #FFEFD6;  --color-pending-fg: #7A4100;
  --color-derived-bg: #EDE6FA;  --color-derived-fg: #4B2A8A;
  --color-neutral-bg: #EEF0F4;  --color-neutral-fg: #3F4654;
  --color-flash: #FFF4DE;          /* draft row highlight */
  --color-disabled-bg: #E7E4EE; --color-disabled-fg: #6B6480;

  /* Type */
  --font-sans: 'Albert Sans', system-ui, sans-serif;
  --font-arabic: 'Noto Sans Arabic', sans-serif;

  /* Radius */
  --radius-panel: 20px;
  --radius-card: 14px;
  --radius-control: 10px;          /* buttons, inputs; 12px for composer + send */
  --radius-bubble: 16px;           /* tail corner 4px */
  --radius-pill: 999px;

  /* Sizes */
  --panel-height: 820px;
  --touch: 44px;
}
```

Fonts: Google Fonts `Albert Sans` 400/500/600/700 and `Noto Sans Arabic` 400/600.

## 2. Type scale

| Use | Size / weight | Colour |
| --- | --- | --- |
| Wordmark "cenomi" | 28 / 700, letter-spacing 0.5px | brand |
| Page title "Send an inquiry" | 32 / 700 | brand |
| Page intro | 16 / 400, line-height 1.5 | text-body |
| Panel title (chat name, "Inquiry draft") | 16–18 / 600–700 | text / brand |
| Card title | 14–16 / 600–700 | text |
| Message text | 15 / 400, line-height 1.5 | text (bot) / white (user) |
| Field label | 12–13 / 400 | text-secondary |
| Field value | 14–15 / 600 | text |
| Section label (draft groups) | 12 / 600, uppercase, letter-spacing 0.6px | text-secondary |
| Badge / tag | 11.5 / 600 | per badge |
| Hint / caption | 12–13 / 400 | text-secondary |

## 3. Page layout

- **Header**: white, bottom border, height ~72px. Left: "cenomi" wordmark + "Tenant Central" (15px, secondary). Right: "العربية" pill button (44px tall, Arabic font).
- **Container**: max-width 1280px, centred, padding 24px 32px 48px.
- **Breadcrumb**: "Sign In › Send Inquiry" (14px; current item brand + 600).
- **Title block**: "Send an inquiry" + intro: "Chat with our leasing assistant. It collects what we need, confirms anything it fills in for you, and sends your inquiry to our leasing team."
- **Two panels** in a wrapping flex row, gap 24px:
  - Chat panel: `flex: 999 1 560px`, height 820px.
  - Draft panel: `flex: 1 1 320px`, height 820px.
  - Below ~920px they stack, chat first.

## 4. Chat panel

White, 1px border, radius 20, `overflow: hidden`, column layout: header / messages (flex 1, scrolls) / composer.

### 4.1 Header (padding 16px 20px, bottom border)
- Avatar: 40px square, radius 12, brand background, white "C" (18/700).
- Title "Cenomi leasing assistant" (16/600) + subtitle "Leasing inquiries for new brands" (13, secondary).
- Right: "Restart" secondary button (dev/demo builds only).
- **Progress stages** below: pills `Company · Brand · Space · Contact · Documents · Review`. Pill: padding 4px 10px, 12.5/600, radius pill.
  - done: success bg/fg, prefixed "✓ "
  - current: brand bg, white text
  - upcoming: muted-fill bg, secondary text
  - Mapping from `phase`: gate → Company; collecting → derived from the first missing group; verifying → Contact; documents → Documents; review/submitted → Review (submitted marks all done).

### 4.2 Message list (padding 20px, gap 12px, chat-bg, `aria-live="polite"`, auto-scrolls to bottom)
- **User bubble**: right-aligned, max-width 78%, brand background, white text, padding 10px 14px, radius 16 16 4 16.
- **Bot bubble**: left, white, 1px border `#ECEAF1`, padding 10px 14px, radius 16 16 16 4. A 32px avatar (radius 10) shows on the first bot message of a run; later ones keep a 32px spacer.
- Cards render under the bot message they belong to, in the same column (max-width 88%).
- **Typing indicator**: avatar + bubble with three 7px dots pulsing (1.2s, staggered 0.2s).

### 4.3 Composer (padding 12px 16px 16px, top border)
- **Suggestion chips** (from `quick_replies`): wrap, gap 8. Chip: min-height 44, padding 8px 16px, 1.5px accent border, white, accent-text 14/600, radius pill. Hidden while typing.
- **Input**: min-height 48, border input-border, radius 12, 15px, placeholder "Type a message…". Enter sends.
- **Send**: 48×48, radius 12, accent, white arrow icon, `aria-label="Send message"`. Disabled while a turn streams.

## 5. Cards (inside the chat)

Common: white, 1px border-card, radius 14, padding 16 (row cards: 4px 16px).

### 5.1 ConfirmFieldsCard
Rows: label (13, secondary, 130px) · value (15/600) · SourceBadge. Row padding 12px 0, divider between. The confirmation itself happens in chat (the agent suggests "Yes, that's correct"); an optional "Looks right" text button sends `confirm_card`.

### 5.2 MallPickerCard
- Title "Malls in {city}" (14/600) + right-aligned count: "Select one" / "1 selected". Single choice (`max_select: 1`): picking another mall replaces the current one.
- 2-column grid, gap 10. Mall tile = `<button aria-pressed>`: min-height 64, padding 10px 12px, radius 12, name (15/600) on the left, 26px circle mark on the right ("+" outlined / "✓" accent fill).
  - Unselected: white, 1.5px border-card. Selected: accent-tint background, 1.5px accent border.
- "Done" button (primary, full width on mobile) sends `select_malls`. Disabled until ≥ 1 selected.

### 5.3 VerificationCard
- Email section: caption "We sent a verification link to {email.masked}. Open it to confirm your email."; in demo mode an "Open verification link (demo)" secondary button; "Resend link" text button. Verified: green check "Email verified".
- Mobile section (only when a mobile was given): label "Verification code", input (48px tall, 20px, letter-spacing 6px, numeric, max 4, `autocomplete="one-time-code"`) + "Verify" primary button; caption "Sent by SMS to {mobile.masked}"; "Resend code" text button.
- All verified: one line, "Email and mobile verified" (or "Email verified" for a landline-only applicant).
- Error: caption "That code didn't match. {n} attempts left." in pending-fg.
- Verified: check icon + "Phone and email verified" (success-fg, 15/600).

### 5.4 DocumentChecklistCard
- Header "Documents" + "{n} of 2 required uploaded".
- One row per document: label (14/600) + tag ("Required": accent-tint/accent-text; "Optional": muted-fill/secondary) · status line ("Not uploaded" or "Uploaded · {file name} · {size}" in success-fg) · button "Upload" (brand fill, white) / "Remove" (white, control border). Min 44×88.
- Upload opens a native file picker restricted to the allowed extensions; shows an inline spinner on the row while uploading; errors appear under the row in pending-fg ("That file is over 5 MB" / "That file type isn't supported").
- Footer caption: "PDF, JPG, PNG, DOC, XLSX, ZIP · up to 5 MB each · we only check that files are uploaded".

### 5.5 ReviewCard
- Title "Review your inquiry" (16/700, brand).
- Groups (Company, Brand, Space, Contact): section label + rows (label · value · SourceBadge · "Edit" text button). Edit turns the value into an inline input with Save/Cancel → `edit_field`.
- "Documents and checks": 10px dots (success-dot filled / 2px outline) + labels.
- Consent: checkbox (20px, accent) + "I agree to the terms & conditions and privacy policy." (links). Whole row is the label, min 44px.
- "Submit inquiry": full width, 48px, accent when enabled; disabled-bg/fg when not. Under it, a hint naming the first blocker ("Accept the terms to submit.", "2 required fields still missing.").

### 5.6 SuccessCard
- 44px success tile with check + "Your inquiry has been sent" (18/700).
- Reference box (subtle bg, border-card, radius 12): "Reference number" (13) + reference (24/700) + "Copy" button (→ "Copied").
- 3-step timeline: 1 "Inquiry submitted · Just now" (success circle) → 2 "Review · Our team verifies your details and documents." (outlined brand circle) → 3 "Sign in to Tenant Central · After approval, with the email you registered." (muted circle).
- "Track your inquiry" link-button (brand-tint bg, brand text, 44px).

## 6. Draft panel

White, border, radius 20, height 820, `overflow: hidden`, column:
- **Pinned header** (padding 20px 20px 16px, bottom border): "Inquiry draft" (18/700, brand) + "What the agent has collected so far, and where each value came from." (13) + progress: "Required fields" · "N of 11" and an 8px bar (muted track, accent fill).
- **Scrolling body** (padding 16px 20px 20px, `overflow-y: auto`, `position: relative`), gap 18:
  - Groups Company · Brand · Space · Contact: section label + rows. Row: label (12) + SourceBadge on one line, value below (14/600; empty: "Not yet collected", muted, 400). Row padding 8px 10px, divider, radius 8.
  - **Live update**: when a `draft` event arrives, rows in `changed_keys` get the flash background for ~1.8s (0.6s ease), and the body smooth-scrolls so the first changed row is ~12px from the top.
  - "Checks before submit": the four check rows (suggested values confirmed · phone and email verified · N of 2 required documents · terms accepted).
  - "Source badges" legend.

### SourceBadge

| Source / state | Text | Colours |
| --- | --- | --- |
| user | You said | neutral |
| verified, unconfirmed | From CR · confirm | pending |
| verified, confirmed | From your CR | success |
| derived, unconfirmed | Suggested · confirm | pending |
| derived, confirmed | Suggested · confirmed | derived |
| default | Default | white + 1px `#D5D8DE` border, `#5B6270` text |

Pill: padding 3px 8px, radius pill, 11.5/600, no wrap.

## 7. Key copy (agent wording comes from the LLM; these are the fixed strings)

- Welcome 1: "Marhaba, and welcome to Cenomi Tenant Central! I'm your leasing assistant."
- Welcome 2: "I'll help you send a leasing inquiry in a few minutes, no long form. To start, do you have your company's CR number? I'll check whether you already have an account with us."
- Welcome chips: "I have my CR number" · "I don't have it handy" · "What do I need to get started?"
- Error bubble: "Sorry, something went wrong on our side. Please try again." + "Retry" button.
- Rate limited: "You're sending messages a little fast. Give it a moment and try again."
- Session expired: "This chat has expired. Start a new inquiry to continue." + "Start again".

## 8. Accessibility and states

- Focus ring: 2px accent outline, 2px offset, on every interactive element.
- All interactive elements ≥ 44px; mall tiles and chips are `<button>`s; toggles use `aria-pressed`.
- Typing indicator has `aria-label="Assistant is typing"`.
- Icons are inline stroke SVGs with `aria-hidden="true"`; icon-only buttons have `aria-label`.
- Never use colour alone: badges carry text; checks carry labels.
- Reduced motion: disable the dot pulse, flash transition and smooth scroll under `prefers-reduced-motion`.
