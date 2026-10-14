# Demo script — Send Inquiry Agent

Use with `make demo` (OTP code **1234**). Allow ~5 minutes for the happy path.

**Full user story & journey:** [demo-queries.md](./demo-queries.md).

## Happy path (CR **1010123456**)

1. Open **http://localhost:5173** → welcome + suggestion chips.
2. Click **I have my CR number**, then send: `My CR number is 1010123456`.
3. Confirm company details on the **confirm** card (or say “Yes, that’s correct”).
4. One natural message, e.g.  
   `Bean Street specialty coffee kiosk at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567`
5. Confirm any derived fields (Arabic name, unit type, category).
6. Enter OTP **1234** in the card.
7. Upload **Company Profile** and **Brand Profile** (any small PDF).
8. Review card → accept terms → **Submit** → note the **GEO-…** reference.

Use **Restart** in the chat header (demo builds) to reset without reloading the page.

## Wow moments

1. **Multi-field capture** — After skip CR or post-CR confirm, paste company + brand + mall + contact in **one** message; watch the draft panel populate without re-asks.
2. **Arabic name suggestion + confirm** — Agent proposes `بين ستريت` (or similar) as derived; confirm card shows source **Suggested · confirm**.
3. **Draft panel live** — Keep the draft panel visible; each tool write flashes updated rows and the checks list moves toward submit-ready.

## Quick alternates (1 minute each)

- **FAQ:** “What documents do I need to upload?”
- **Existing account:** CR `1010000000` → Sign In guidance, no submit.
- **Resilience:** Stop the backend mid-reply → **Retry**; restart backend and send a message → **Start again** when the session expires.
