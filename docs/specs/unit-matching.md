# Unit matching: malls that fit, a counter-offer, and a suggested unit for the RSM

**Status:** drafted 23 Nov 2026 (MS3) · **Delivery:** days U1–U3 (proposed Mon 7 – Wed 9 Dec), after the 18 Nov round's gate on 4 Dec · **Parent:** [`demo-18nov-feedback.md`](demo-18nov-feedback.md) (X1–X3, M32) · **Tracker:** [18 Nov demo tracker](https://claude.ai/artifact/4KmQbw2D1bwVzw7TGKTnJd) (MS18)

On 18 Nov Muzammil described where the agent goes next (17:47–21:14). Once the applicant has said how much space they need, their budget, how long a lease and when they want to open, the agent checks the inventory and suggests only malls that have a fitting unit. If nothing fits, it says what is available: "the smallest space we have at Mall X is 100 sqm; would that work?". If they say no, the inquiry is kept on file. The Regional Sales Manager also sees a suggested unit, "based on my initial scrutiny", which the tenant never sees.

This builds on the 18 Nov round: Property Details asked one at a time with `flexible` items (N10), `desired_start` (N11), `rent_basis`, the `choice` card (N3) and `match_mall` (N12).

## 1. Scope

| Item | What | Day |
| --- | --- | --- |
| X1 | `InventoryService` (mock), matching rules in code and policy, mall options limited to malls with a fitting unit | U1 (backend), U2 (agent) |
| X2 | No fit anywhere: a counter-offer stated against the applicant's own criteria; "keep my inquiry on file" submits the inquiry flagged `no_current_match` | U1, U2 |
| X3 | The RSM sees up to 3 suggested units with the reasons they fit, in the case brief and the unit-assignment action; the RSM still assigns | U1 |

**Not in scope:** alerting the applicant when a fitting unit frees up (L5, `l5-governed-proactivity.md`); showing units, unit numbers or prices to the applicant; holding or reserving a unit; real Yardi inventory (golden rule 5).

## 2. Gate

| # | Criterion | Proved by | Day |
| --- | --- | --- | --- |
| UG1 | `match_units(draft, inventory)` is pure and deterministic. A unit fits when its type matches and every non-flexible criterion is within the policy tolerances (§3.2). Flexible items don't filter. | `tests/domain/test_unit_matching.py` | U1 |
| UG2 | After the four property items, the mall options come from `match_units`: malls with at least one fitting unit, best first, plus "Show all malls". Names and the count of malls only; no units, no prices. | `tests/agent/test_mall_options_from_inventory.py`; NV12 | U1, U2 |
| UG3 | No fit: the counter-offer facts come from code (`nearest_offer`), per mall: smallest area, latest availability date that's still earlier, or the lease terms offered. The reply states only those facts, as "currently", and never promises (I7). | `tests/domain/test_nearest_offer.py`; eval `unit_matching`; NV13 | U1, U2 |
| UG4 | "Keep my inquiry on file" submits normally with `match_status: no_current_match`; the Leasing Admin sees the flag; nothing else in the flow changes. | `tests/lifecycle/test_no_current_match.py`; NV13 | U1 |
| UG5 | The case brief and the unit-assignment action show up to 3 suggested units with reasons, recomputed when the RSM opens the case. The applicant's status, emails and case chat never show them (I9 extended to case mode). | `tests/case_brief/test_suggested_units.py`; NV14 | U1 |
| UG6 | Inventory facts reach the model only through the `check_availability` tool result for that turn; no unit reference or price is in it. | `tests/security/test_inventory_not_leaked.py` | U1 |
| UG7 | Live: `unit_matching` group 3/3 in English and Arabic; the 18 Nov groups and all others within tolerance. | `make eval-live` | U2–U3 |

## 3. Design

### 3.1 Inventory

- **`InventoryService`** (`app/services/inventory.py`), protocol plus `MockInventoryService` over `data/mock_world/inventory.json`. A real adapter reads Yardi's available units once Cenomi gives access.
- **Unit:** `{unit_ref, mall_id, unit_type, area_sqm, asking_rent_sar_per_sqm_year, available_from, lease_terms_years: [int], status: available | reserved}`. Only `available` units match.
- **Seed:** about 30 units over the seed malls and the four unit types, with a few gaps on purpose: no Office in Jeddah, nothing under 60 sqm in Riyadh Mall A, and one mall whose units free up only in mid-2027.
- **Leasing Opportunities** (`OpportunityCatalogue`) stays as it is; when the real inventory arrives, its list can be derived from the same source.

### 3.2 Matching (code and policy)

`app/domain/unit_matching.py`:

```python
match_units(draft, units, policy) -> list[UnitFit]       # fitting units, scored
mall_options(fits) -> list[MallOption]                    # mall_id, count, best score
nearest_offer(draft, units, policy) -> list[MallOffer]    # per mall, what is closest
```

| Criterion | Fits when | Policy (`matching.*`) |
| --- | --- | --- |
| Unit type | Equal | — |
| Area | `area_sqm` within `[area_min × (1 − t), area_max × (1 + t)]` | `area_tolerance: 0.15` |
| Budget | Annual rent (per sqm × area, or the total) ≤ budget × (1 + t), using `rent_basis` and `rent_period` | `budget_tolerance: 0.10` |
| Lease length | The requested years are in `lease_terms_years` | — |
| Start | `available_from` ≤ desired start + grace; `asap` → ≤ today + grace | `start_grace_days: 60` |

- A flexible or missing item doesn't filter.
- **Score:** how close the area is to the middle of the range, then rent headroom, then the earliest date. Ties go to the mall the applicant named first.
- **`nearest_offer`** relaxes one criterion at a time (area, then start, then lease, then budget) and reports what would fit, per mall: "smallest 100 sqm", "from March 2027", "5-year leases". It never reports a price: I7 forbids one in a reply.

### 3.3 In the chat

- **When:** once area, budget, lease length and start are each answered or flexible, the hint (`still_needed_line`) asks for the mall with `check_availability` first.
- **Tool `check_availability()`:** no arguments; reads the draft. Returns either `{"fits": [{"mall_id", "mall": "<name>", "count"}]}` or `{"fits": [], "offers": [{"mall_id", "mall", "closest": "<fact>"}]}`. Never unit refs or prices.
- **Fits:** a `choice` card for `malls` with the fitting malls (up to 5, best first) and "Show all malls" (the existing picker). The reply says these malls have space that fits and asks which they'd like.
- **No fit:** the reply gives the closest facts, at most two malls, as "currently". Then a `choice` card for `match_choice` with:
  - "Show me <mall>" for each offer (writes the mall and sets `match_status: counter_offer_accepted`);
  - "Keep my inquiry on file" (sets `match_status: no_current_match`, then asks for their preferred mall as today).
- **Invariants:**
  - I7 gains an exception: an availability statement that matches this turn's `check_availability` result ("currently", a mall name, an area or date from the result) is allowed. Anything else stays a violation.
  - I9 covers case mode too: the case agent never names a unit.
- **Never:** a unit number, a price, "we'll hold it", or "it's yours".

### 3.4 After submit

- **`InquiryDraft.match_status`** (`matched` | `counter_offer_accepted` | `no_current_match` | `not_checked`) goes on the case. The Leasing Admin's queue and brief show "No current match: keep on file" for `no_current_match`. The lifecycle doesn't change.
- **The RSM's suggested units (X3):**
  - `build_case_brief` adds "Suggested units": up to 3 `UnitFit`s for the case's malls, with reasons ("120 sqm, in your range"; "SAR 1,050/sqm a year, within budget"; "available 1 Feb 2027");
  - recomputed when the RSM opens the case, so a unit taken since isn't suggested;
  - the unit-assignment action lists them first; the RSM can still type any unit;
  - the reviewer assistant can mention them when asked.
- **The applicant never sees them:** not in the status, the case chat or any email.

## 4. Design rules

| ADR | Decision |
| --- | --- |
| U1 | **Code matches; the model words it.** Matching and the counter-offer facts are computed in code from inventory and policy; the model only phrases the tool result. |
| U2 | **The applicant sees malls and criteria, never units or prices.** M25 still holds for units; prices stay out of replies (I7). |
| U3 | **Suggestions advise; the RSM decides.** Nothing is reserved or assigned by the agent. |
| U4 | **Never block an inquiry on inventory.** "Show all malls" and "Keep my inquiry on file" are always there; the mock or real inventory can be incomplete. |

## 5. Stories and evals

| Story | What it proves | Live |
| --- | --- | --- |
| NV12 | Store, 80–120 sqm, budget per sqm, 3 years, January → two malls offered, best first; pick one; submit; the RSM sees 2–3 suggested units with reasons | yes |
| NV13 | Office in Jeddah, 40 sqm → no fit → "the smallest space currently at X is 100 sqm"; "Keep my inquiry on file" → submitted with `no_current_match`; the Leasing Admin sees the flag | yes |
| NV14 | A suggested unit is taken (dev reseed) before the RSM opens the case → not suggested; the applicant's status and case chat never show a unit | no |

**Eval group `unit_matching`** (English and Arabic, ×3): `offers_only_fitting_malls`, `offers_show_all`, `counter_offer_from_tool_only`, `no_price_in_reply`, `no_unit_named`, `no_hold_or_promise`, `keep_on_file_offered`.

## 6. Contract changes to fold into `docs/spec.md`

`InventoryService`, `data/mock_world/inventory.json`; policy `matching.*`; `app/domain/unit_matching.py`; tool `check_availability`; `choice` card keys `malls` (from the match) and `match_choice`; `InquiryDraft.match_status`; case brief "Suggested units"; unit-assignment suggestions; I7 exception; I9 in case mode.

## 7. Days and milestones (proposed)

MS18 splits into the same two halves as the 18 Nov days.

| Day | Date | Claude (backend PR) | Swaroop (Cursor) |
| --- | --- | --- | --- |
| U1 | Mon 7 Dec | Inventory mock and service; `match_units`, `mall_options`, `nearest_offer`; `check_availability`; `match_status`; case brief and console suggestions; I7, I9; tests UG1, UG2, UG4–UG6; NV12–NV14 catalogue, scripts, specs; eval group and checks | — |
| U2 | Tue 8 Dec | Fixes from U2 runs | Prompt: when to call `check_availability`, how to word fits and the counter-offer; `choice` card for `match_choice`; reviewer assistant line; Vitest; live `unit_matching` + full regression |
| U3 | Wed 9 Dec | Docs: `POC-LIFECYCLE`, `STATUS`, demo script beat | Full scripted and live runs; rehearsal |

## 8. Assumptions and questions

U-A1–U-A4 were decided by us on 23 Nov (issue #118, closed); Muzammil can change any of them in policy or data, without code. U-A5 waits on Yardi access (issue #119).

| Id | Assumption | State |
| --- | --- | --- |
| U-A1 | Tolerances: area ±15%, budget +10%, start up to 60 days later | Decided (policy `matching.*`) |
| U-A2 | The applicant never sees prices, even in a counter-offer | Decided |
| U-A3 | "Show all malls" is always offered beside the fitting malls | Decided |
| U-A4 | A "keep on file" inquiry goes through the Leasing Admin as usual, flagged | Decided |
| U-A5 | Inventory fields as in §3.1; the real Yardi feed may differ (G8) | Open: with Yardi access (#119) |
