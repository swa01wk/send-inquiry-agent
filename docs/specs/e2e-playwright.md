# Spec: End-to-end tests with Playwright (frontend + backend + agent)

Goal: prove that **non-technical users** (shop owners, brand managers, people typing on a phone, people who don't know what a CR number is) can finish an inquiry easily, and that the bugs in `docs/specs/ui-bugs.md` stay fixed.

Two suites run the **real browser, frontend and backend**:

| Suite | Agent | When | Asserts on |
| --- | --- | --- | --- |
| `@scripted` | `ScriptedChatModel` per scenario (deterministic) | Every PR (CI) | Exact cards, draft state, UI |
| `@live` | Real OpenAI model | Manually before demos | Draft state, cards, plain-language rules (not exact wording) |

Both run on two projects: **desktop-chrome** (1440×900) and **mobile** (iPhone 13).

---

## 1. Setup

```text
e2e/
  package.json            # @playwright/test, @axe-core/playwright, typescript
  playwright.config.ts
  global-setup.ts         # generates too_big.pdf (6 MB), checks servers
  fixtures/files/         # company_profile.pdf, brand_profile.pdf, notes.txt
  pages/inquiry.ts        # page object
  support/plainLanguage.ts
  support/events.ts       # SSE event capture (message_remove count, card ids)
  tests/*.spec.ts         # one file per persona group
  results/                # live run summaries (gitignored except .gitkeep)
```

- `playwright.config.ts`
  - `webServer`: backend `uvicorn app.main:app --port 8000` (cwd `backend`, env from the suite) and frontend `npm run dev -- --port 5173` (cwd `frontend`). `reuseExistingServer: !process.env.CI`.
  - `projects`: `desktop-chrome`, `mobile` (`devices['iPhone 13']`).
  - `use`: `trace: 'retain-on-failure'`, `video: 'retain-on-failure'`, `screenshot: 'only-on-failure'`.
  - `grep` by tag: `@scripted` default; `@live` via `make e2e-live`.
- Makefile:
  - `make e2e` → backend with `AGENT_MODE=scripted`, run `@scripted`.
  - `make e2e-live` → backend with real `OPENAI_API_KEY`, run `@live` (retries: 1).
  - `make e2e-report` → `npx playwright show-report`.
- PDF fixtures are tiny valid PDFs (a few hundred bytes, real `%PDF-1.4` header). `too_big.pdf` is generated in global setup, not committed.

## 2. Scripted agent mode (backend)

- `Settings.agent_mode: Literal["openai", "scripted"] = "openai"` (env `AGENT_MODE`).
- In scripted mode only, `POST /api/sessions` accepts header `X-Test-Scenario: <name>`; the session stores it. In `openai` mode the header is ignored.
- The agent node resolves its model per session: `config["configurable"]["model"]` when present (scripted), else the shared OpenAI model. `run_turn` passes a `ScriptedChatModel` built from `backend/tests/e2e_scripts/<name>.json` (same step format as `ScriptedChatModel.steps`), keeping its step index on the session across turns.
- Scripts must call the **real tools** (`verify_cr`, `update_draft`, `confirm_fields`, `show_mall_picker`, `send_otp`, `request_documents`, `show_review`, `suggest_replies`, `search_faq`, `get_inquiry_status`) so the guard, cards and draft run for real.
- Scripts are validated by a backend unit test (JSON parses, tool names exist).

## 3. Page object (`e2e/pages/inquiry.ts`)

Methods read like what a user does:

| Method | Behaviour |
| --- | --- |
| `open(scenario?)` | Load page; in scripted mode set `X-Test-Scenario` via route interception on `POST /api/sessions` |
| `say(text)` | Type in composer, Enter, wait until the turn's `done` (typing dots gone, composer enabled) |
| `tapChip(label)` | Click a suggestion chip |
| `confirmCard()` | Click "Looks right" on the latest unconfirmed confirm card |
| `pickMalls(names)` | Toggle mall tiles, click Done |
| `enterCode(code)` | OTP input + Verify |
| `upload(docLabel, file)` | `setInputFiles` on that document row |
| `acceptAndSubmit()` | Tick consent, click Submit inquiry |
| `lastReply()` / `allReplies()` | Assistant bubble texts in order |
| `cards(type)` | Visible cards of a type |
| `draft()` | `GET /api/sessions/{id}/draft` |
| `events()` | Captured SSE events for the session (`message_remove`, `ui_card` ids) |

SSE capture: test builds (`VITE_E2E=1`) push each parsed event to `window.__e2eEvents`; nothing is exposed otherwise.

## 4. Checks after every turn (`support/plainLanguage.ts`)

Non-technical users must never see system language or walls of text:

1. No reply contains: `update_draft`, `verify_cr`, `confirm_fields`, `send_otp`, `tool`, `field`, `ui_event`, `derived`, `payload`, `guard`, `schema`, any `snake_case` word, or a master id like `riyadh-mall-a`.
2. Each reply ≤ 4 sentences and ≤ 2 question marks.
3. No duplicate confirm cards: for each set of field keys, at most one visible `confirm_fields` card.
4. Retractions (`message_remove`) ≤ 1 per conversation.
5. No reply mentions a detail (coffee, kiosk, a mall) before the user has.

At the end of each test: axe scan on the final screen, no serious/critical violations; on mobile, no horizontal scroll (`document.documentElement.scrollWidth <= innerWidth`).

## 5. Scenarios

Tags: all scenarios are `@scripted` (with a script). Those marked **L** also run `@live`.

| # | Persona | Steps | Expect |
| --- | --- | --- | --- |
| 1 **L** | Shop owner, brief answers | "hi" → "1010123456" → "coffee kiosk riyadh mall a" → "sara ali sara@beanstreet.example 0501234567" | OTP card within 4 typed turns. Draft: malls `[riyadh-mall-a]`, unit `specialty`, category `fnb_cafe`, Sara / Ali, mobile `+966501234567` |
| 2 **L** | Front-loader | CR, then one message with brand, mall, size, budget, lease, name, email, phone | Next reply asks nothing already given; OTP card shown |
| 3 **L** | Doesn't know CR | "what is CR?" → "i dont have it" → "Acme Trading LLC, King Abdullah Road Riyadh" | Plain CR explanation (≤ 2 sentences); `cr_status` skipped; company saved |
| 4 | Typos, lowercase | after CR: "beanstreet cofee kiosk in riyad mall a" | Either malls `[riyadh-mall-a]` or a mall picker; never an invalid mall id; no error wording |
| 5 **L** | Arabic only | "السلام عليكم" → "رقم السجل 1010123456" → "كشك قهوة في Riyadh Mall A اسم العلامة بين ستريت" → "سارة علي sara@beanstreet.example 0501234567" | Replies contain Arabic; 0 retractions; required fields filled |
| 6 **L** | WhatsApp style | "hiii 👋 pls help" → "cr 1010123456 🙏" → "we sell coffee ☕ small kiosk riyadh mall a" | Data saved; warm replies; no jargon |
| 7 | Phone in any format | contact turn with "05 0123 4567", "+966-50-123-4567", "966501234567" (three runs) | Mobile `+966501234567` each time |
| 8 | City only | "sneakers shop somewhere in jeddah" | Mall picker for Jeddah; malls empty until picked; `pickMalls(["Jeddah Mall A"])` saves it |
| 9 **L** | Changes mind | after brand summary: "actually make it a full shop not kiosk" | unit `store`, source user; brand confirm card count still 1 |
| 10 **L** | Unsure | "not sure about the category" | category unconfirmed; reply offers options |
| 11 **L** | Impatient | "just submit it" before OTP | No review/success card; reply says what's left in plain words |
| 12 | Wrong code | `enterCode("0000")` ×2 then `"1234"` | Friendly retry messages; verified; the code never appears in chat |
| 13 | Wrong files | Company Profile: notes.txt → too_big.pdf → company_profile.pdf; Brand Profile: brand_profile.pdf | "That file type isn't supported." → "That file is over 5 MB." → uploaded with name; review card appears; documents reply names Company Profile and Brand Profile |
| 14 **L** | Wants a person | "can i talk to someone?" | Polite answer, offers to continue, no promises |
| 15 **L** | Asks price | "how much is rent at riyadh mall a?" | No SAR amount invented; flow continues |
| 16 | Existing tenant | "1010000000" | Reply mentions Sign In; no further collection; submit impossible |
| 17 **L** | Rambler (voice-to-text) | one long paragraph mixing greeting, brand, mall, budget, name, email, phone and an unrelated story | Fields saved; summary ≤ 4 sentences |
| 18 **L** | Demo sequence | the 8 demo queries from `ui-bugs.md`, `enterCode("1234")`, upload both PDFs, `acceptAndSubmit()` | One company card ending "From your CR"; one brand card; unit `store`; documents reply names both required docs; success reference matches `^GEO-(STR|MED|SPC|OFF)-\d{6}$` |
| 19 | CR chip | tap "I have my CR number" | Composer focused, placeholder "Type your 10-digit CR number", no `/chat` request |
| 20 | Formatting | scripted reply with a bullet list | Rendered as a list, line breaks kept |

## 6. Live suite rules

- `retries: 1`; a scenario passes if either attempt passes.
- Writes `e2e/results/live-<date>.json`: per scenario pass/fail, turns, retractions, duration.
- Adds a row to `docs/eval-notes.md` (date, pass count, total retractions).
- Target: ≥ 11/12 live scenarios on two consecutive runs.

## 7. CI

`.github/workflows/e2e.yml`:
- `pull_request`: set up Python (uv) and Node, install Playwright browsers, run backend with `AGENT_MODE=scripted`, run `make e2e` on both projects; upload `playwright-report/` as an artifact.
- `workflow_dispatch`: live suite with secret `OPENAI_API_KEY`.

## 8. Done when

- `make e2e` green on desktop and mobile.
- `make e2e-live` ≥ 11/12 twice; results logged.
- Every bug in `ui-bugs.md` has at least one failing-before / passing-after e2e or unit test.
