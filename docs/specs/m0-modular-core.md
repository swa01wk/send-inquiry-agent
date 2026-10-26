# M0 — Modular core (with B0 behaviour parity)

**Status:** proposed · **Builds on:** PR #1 (POC assumptions) and [pre-baseline fixes](pre-baseline-fixes.md) · **Cursor steps:** `prompts/12`–`16` · **Next:** [L3 reliable intake](l3-reliable-intake.md)

**Amended 26 Oct 2026:** the baseline is recorded after the pre-baseline fixes (§4); the inquiry model carries the confirm-card turn numbers (§5.1); and the post-submit rows of the state machine now follow requirements §7.1.1 b–c (§6).

## 1. Why

v1 already does extraction, slot filling, validation and consent at L3 standard. But its state lives in process memory, nothing records what happened, and submit is not idempotent. Those are the framework's L3 prerequisites (capabilities 7, 9 and 10), and every later feature depends on them:
- **The email-link journey needs durable state.** Requirements §7.1.1 has the user leave the chat and return from their inbox, so the draft must survive.
- **Post-submit work needs a case record and a state machine.** Reviewer review, re-upload requests and onboarding (§7.1.1 b–c) all act on a case after the chat ends.
- **Production needs an audit trail and exactly-once submission.**

M0 changes how the agent is built, not what the user sees. Users should notice nothing.

## 2. Gate (all Must)

| # | Criterion | Proved by |
| --- | --- | --- |
| G1 | Behaviour parity: every scenario in `tests/scenarios` and the golden transcripts pass unchanged, the Playwright `@scripted` suite is green, and live eval scores no lower than the last baseline run | `tests/parity/`, `make e2e`, `scripts/eval_live.py` |
| G2 | Restarting the backend mid-intake loses nothing: the same `session_id` continues with draft, cards and history | `tests/durability/test_restart.py` (Postgres) |
| G3 | Two concurrent `accept_and_submit` calls produce exactly one reference; a repeat returns the same reference and success card | `tests/workflow/test_idempotent_submit.py` |
| G4 | Every case has an ordered audit trail covering each user turn, tool call, card action, guard verdict, state transition and submit outcome, and no OTP code, link token or file content appears in it | `tests/audit/test_trail.py` |
| G5 | Illegal state transitions are rejected and audited | `tests/workflow/test_machine.py` |
| G6 | Every external call goes through the gateway: a forced timeout or failure in each service becomes a typed `GatewayError`, is audited, and leaves the inquiry consistent | `tests/gateway/test_gateway.py` |
| G7 | `make test` and `make lint` green with `STATE_BACKEND=memory` (default) and `STATE_BACKEND=postgres` | CI matrix |

## 3. Scope

**In:**
- Parity suite (B0).
- Durable inquiry store.
- Postgres checkpointer.
- Inquiry state machine.
- Tool gateway: timeouts, retries, error taxonomy.
- Idempotent submit with reconciliation.
- Audit event log.
- Supervisor with an agent registry.
- Bounded LLM history.

**Out (L3 or later):**
- Real external APIs.
- Email-link resume across devices.
- Status page.
- Human handoff.
- Policy file.
- Post-submit agents (L4).

## 4. B0 — behaviour parity suite (Must)

Freeze today's behaviour before restructuring it.

1. Record **golden SSE transcripts** from `main` after the pre-baseline fixes (`prompts/11c`) with `ScriptedChatModel`, so they include "confirm only what was shown" and the `documents_updated` turn:
   - CR happy path.
   - Skip CR.
   - Existing CR.
   - Landline-only.
   - Two malls named.
   - Wrong OTP three times.

   Store them in `backend/tests/parity/golden/*.jsonl`.
2. `tests/parity/test_golden.py` replays each script against the app and compares event types, card types, card payloads, draft `changed_keys`, final phase and final draft. It normalises `message_id`s and timestamps; text is compared exactly because the model is scripted.
3. Record a **live-eval baseline**: run `scripts/eval_live.py` twice and store the scores in `docs/eval-notes.md`. G1 compares against it.

## 5. Durable state (Must)

### 5.1 Model

An **inquiry** is the durable case. A **session** is a browser's handle on it. In M0 they are 1:1, and `session_id` keeps its meaning in the API. L3 adds resume, so one inquiry can have several sessions over time.

```python
class InquiryStatus(StrEnum):          # workflow state, see §6
    DRAFT = "draft"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ABANDONED = "abandoned"
    # Defined now, reachable only from L4:
    FIRST_REVIEW = "first_review"
    REUPLOAD_REQUESTED = "reupload_requested"
    SECOND_REVIEW = "second_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_TO_YARDI = "sent_to_yardi"

class Inquiry(BaseModel):
    id: UUID
    status: InquiryStatus = InquiryStatus.DRAFT
    draft: InquiryDraft                   # unchanged domain model
    cards_shown: list[str]
    confirm_card_keys: dict[str, list[str]]
    confirm_card_turns: dict[str, int]     # pre-baseline fix F1
    turn_index: int = 0                    # pre-baseline fix F1
    card_counter: int
    submit_key: str | None = None          # idempotency key, see §7
    reference: str | None = None           # mirrors draft.reference
    version: int = 0                       # optimistic concurrency
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    expires_at: datetime                   # draft retention, see §5.4
```

`cards_shown`, `confirm_card_keys`, `confirm_card_turns`, `turn_index` and `card_counter` move from `app/sessions.py:Session` onto the inquiry, so a restart keeps card state.

The post-submit case data (review queue, reviewer requests, additional contacts, onboarding, Yardi link) is added to `Inquiry` by [L4](l4-outcome-assistance.md) §3.1. M0 fixes only the statuses and events (§6), so tooling can be built against them.

### 5.2 Repository (`app/store/`)

```python
class InquiryRepository(Protocol):
    async def create(self) -> Inquiry: ...
    async def get(self, inquiry_id: UUID) -> Inquiry: ...            # raises InquiryNotFound
    async def save(self, inquiry: Inquiry) -> Inquiry: ...            # bumps version; raises VersionConflict
    async def acquire_turn(self, inquiry_id: UUID, lease_s: int) -> str: ...   # returns lease id; raises TurnInProgress
    async def release_turn(self, inquiry_id: UUID, lease_id: str) -> None: ...
    async def purge_expired(self, now: datetime) -> int: ...
```

- **`InMemoryInquiryRepository`** is the default and is used in tests. It keeps today's behaviour.
- **`PostgresInquiryRepository`** uses SQLAlchemy 2 async over psycopg 3.
- **`SessionStore` becomes a thin adapter over the repository.** Routers keep calling `store.touch(session_id)`. `SessionNotFound` and `TurnInProgress` keep their HTTP mappings (404 `session_not_found`, 409 `turn_in_progress`).
- **Turn lease.** The per-session `asyncio.Lock` becomes a lease on the row, so it works across workers and frees itself if a worker dies:

  ```sql
  UPDATE inquiries
  SET turn_lease_id = :lease, turn_lease_until = now() + make_interval(secs => :lease_s)
  WHERE id = :id
    AND (turn_lease_until IS NULL OR turn_lease_until < now())
  ```

  Zero rows updated means `TurnInProgress`. The default lease is 120 s (`TURN_LEASE_SECONDS`).
- **Uploads hold the lease too.** Document upload and delete take the same lease, which closes the v1 race where an upload could interleave with a chat turn.
- **Saves are optimistic.** `UPDATE … WHERE id = :id AND version = :expected`. A conflict raises `VersionConflict`. The chat endpoint retries once by reloading, then returns 409.

### 5.3 Tables (Alembic migration `0001_inquiries`)

| Table | Purpose | Key columns |
| --- | --- | --- |
| `inquiries` | The durable case | `id uuid pk`, `status text`, `draft jsonb`, `cards_shown jsonb`, `confirm_card_keys jsonb`, `card_counter int`, `submit_key text unique null`, `reference text unique null`, `version int`, `turn_lease_id text null`, `turn_lease_until timestamptz null`, timestamps, `expires_at` |
| `inquiry_events` | Audit trail (§8) | `id bigserial pk`, `inquiry_id uuid fk`, `seq int`, `at timestamptz`, `actor text`, `type text`, `correlation_id text`, `payload jsonb`; `unique(inquiry_id, seq)` |
| LangGraph checkpoint tables | Message history | Created by `AsyncPostgresSaver.setup()`; `thread_id = inquiry id` |

Indexes: `inquiries(status, expires_at)` and `inquiry_events(inquiry_id, seq)`.

### 5.4 Retention

- **Browser sessions** still idle out after `SESSION_TTL_MINUTES` (120). That only ends the browser session.
- **Inquiry drafts** are kept for `DRAFT_RETENTION_DAYS` (default 30) so they can be resumed in L3. `purge_expired` then marks them `abandoned`, deletes their checkpoints and uploaded files, and keeps the audit trail.
- **Submitted inquiries are never purged by this job.** Their retention follows Cenomi policy (open question Q2).

### 5.5 Checkpointer and bounded history

- `build_graph` takes a checkpointer: `MemorySaver` for memory, `AsyncPostgresSaver` for Postgres.
- `agent_node` sends the model only the last `AGENT_HISTORY_MESSAGES` messages (default 40), cut at a turn boundary so no tool call is separated from its result. This is safe because the system prompt already carries the full draft state each turn (`prompt_summary` + bundle hint).
- The full history stays in the checkpoint.

### 5.6 New dependencies

| Package | Why |
| --- | --- |
| `sqlalchemy[asyncio]` 2.x | Repository and migrations; typed and async |
| `psycopg[binary,pool]` 3.x | One driver for SQLAlchemy and the LangGraph checkpointer |
| `alembic` | Schema migrations |
| `langgraph-checkpoint-postgres` | Durable LangGraph checkpoints |

`docker-compose.yml` gains a `postgres:16` service with a named volume. `make dev` sets `STATE_BACKEND=postgres` and `DATABASE_URL`.

## 6. Inquiry state machine (Must)

The workflow state lives in `app/workflow/machine.py` as a pure function, with no library:

```python
def transition(inquiry: Inquiry, event: WorkflowEvent, *, actor: Actor) -> Inquiry
```

It raises `IllegalTransition` for anything not in the table below, and every call, legal or not, is audited. `compute_phase` stays as it is. It describes the intake sub-state inside `draft` and is not replaced.

| From | Event | To | Who can trigger | Guard |
| --- | --- | --- | --- | --- |
| `draft` | `submit_requested` | `submitting` | user (`accept_and_submit`) | `can_submit(draft) == []` |
| `submitting` | `submit_succeeded(reference)` | `submitted` | system | reference present |
| `submitting` | `submit_failed(reason)` | `draft` | system | failure is definite (gateway `rejected`) |
| `submitting` | `submit_unknown` | `submitting` | system | timeout or unavailable; reconcile before any retry (§7) |
| `draft` | `expired` | `abandoned` | system (purge job) | `now > expires_at` |
| `submitted` | `routed(queue)` | `first_review` | system (L4) | the routing table resolves a queue for the unit type and the mall's region |
| `first_review` | `reupload_requested(doc_types, remarks)` | `reupload_requested` | reviewer (L4) | `doc_types` non-empty and known; remarks non-empty |
| `reupload_requested` | `documents_resubmitted` | `first_review` | user (L4) | every requested document replaced after the request |
| `first_review` | `rejected(remarks)` | `rejected` | reviewer (L4) | remarks non-empty |
| `first_review` | `approved_first` | `second_review` | reviewer (L4) | — ; side effect: primary contact invited (Azure AD, mocked) |
| `second_review` | `contacts_requested` / `sales_data_requested` | `second_review` | reviewer (L4); `contacts_requested` also system, as an effect of `approved_first` ([L4](l4-outcome-assistance.md) §3.4) | no open request of that kind |
| `second_review` | `contact_removed(role)` | `second_review` | reviewer (L4) | the contact was prefilled from the tenant record ([intake channels](intake-channels.md) §3.7) |
| `second_review` | `contacts_provided` / `sales_data_provided` | `second_review` | user (L4) | that request is open; contacts valid (Authorized Signatory and Billing Contact present) or file present |
| `second_review` | `request_withdrawn(kind)` | `second_review` | reviewer (L4) | that request is open |
| `second_review` | `company_relinked(yardi_company_id)` / `brand_relinked(yardi_brand_id)` | `second_review` | reviewer (L4) | the id exists; a brand belongs to the linked company |
| `second_review` | `rejected(remarks)` | `rejected` | reviewer (L4) | remarks non-empty |
| `second_review` | `approved` | `approved` | reviewer (L4) | no open requests; required contacts present when the policy requires them |
| `approved` | `sent_to_yardi(yardi_ref)` | `sent_to_yardi` | system (L4) | Yardi acknowledged |
| `approved` | `yardi_failed(kind)` | `approved` | system (L4) | audited; retried through the gateway |

Every reviewer event also checks that the actor is a reviewer assigned to the case's queue (role and region). The machine enforces this, not the console. The one system-initiated request is the automatic contacts request on first-level approval (requirements §7.1.1 b: "on contact creation, a notification … to provide additional tenant contacts").

Second-level requests (contacts, sales data) are open requests on the case, not separate statuses: the case stays in `second_review` while the tenant answers, and the status page shows "Waiting for you" from the open requests. Re-upload stays a status because it pauses first-level review until the tenant acts (§7.1.1 b).

M0 implements and tests the first five rows. The L4 rows are in the table and the enum so that reviewer tooling can be built against a fixed contract, but nothing in M0 triggers them. Their data (queue, requests, contacts, remarks) arrives in [L4](l4-outcome-assistance.md).

## 7. Tool gateway and idempotent submit (Must)

### 7.1 Gateway (`app/gateway/`)

Today, tools and actions call the services directly. In M0, every external call goes through one wrapper, `Gateway.call(name, fn, *, idempotent: bool, timeout_s: float, audit_args: dict)`. It provides:
- **A timeout** per call: `GATEWAY_TIMEOUT_SECONDS`, default 10, overridable per service.
- **Retries with jittered backoff** (`GATEWAY_RETRIES`, default 2). Only calls marked idempotent are retried: reads, and writes that carry an idempotency key.
- **One error taxonomy.** Failures become `GatewayError(kind)` with kind `timeout`, `unavailable`, `rejected` or `invalid`, so tools and actions handle four outcomes instead of each service's exceptions.
- **Audit and latency.** Every call is recorded as a `tool_called` event, with arguments passed through the redactor (§8), plus its latency.

The CR, email-link, OTP, storage, submit and status services are wrapped this way. The service protocols stay as they are, so swapping a mock for a real adapter in L3 touches only the container.

### 7.2 Idempotent submit with reconciliation

This replaces today's `_accept_and_submit` in `app/agent/actions.py`, where a second call issues a second reference.

1. **Already submitted or submitting.** If `inquiry.status` is `submitted`, return the stored reference and success card again; the note is `[ui_event] submitted reference=<ref> (repeat)`. If it is `submitting`, reconcile (step 5) before doing anything else.
2. **Fresh submit.** Set `terms_accepted`. If `can_submit` reports blockers, behave as v1 does (`submit_blocked`).
3. **Record intent first.** Compute `submit_key = f"inq:{inquiry.id}:v1"` (one key per inquiry). Transition `draft → submitting` and **persist before calling out**.
4. **Call out.** `SubmitService.submit(payload, idempotency_key=submit_key)`:
   - success → `submitted` with the reference;
   - `rejected` → back to `draft`, note `submit_failed <reason>`;
   - timeout or unavailable → stay `submitting`, note `submit_pending`. The agent tells the user the inquiry is being confirmed and must not claim success; the guard already enforces that.
5. **Reconcile.** `SubmitService.lookup(submit_key) -> str | None`. A found reference completes the transition to `submitted`. Not found after `SUBMIT_RECONCILE_SECONDS` (default 120) means one retry with the same key.

The protocol changes in `app/services/submit.py`:

```python
class SubmitService(Protocol):
    def submit(self, payload: InquiryPayload, *, idempotency_key: str) -> str: ...
    def lookup(self, idempotency_key: str) -> str | None: ...
```

- The mock stores keys, so a repeat key returns the same reference.
- `InquiryPayload` is the shape Cenomi's inquiry API will receive: basic info (§7.1.1 table), document references and verification flags. It is built by `app/domain/payload.py` from the draft, not by dumping the draft as-is.

## 8. Audit trail (Must)

`app/audit/` provides `AuditLog.record(inquiry_id, type, actor, payload, correlation_id)`. It is append-only, numbered per inquiry, and backed by `inquiry_events` (or a list in memory). `correlation_id` is the turn id, so one user turn's events group together.

| Event type | Recorded by | Payload (redacted) |
| --- | --- | --- |
| `inquiry_created` | sessions router | — |
| `user_message` | chat endpoint | `chars`, `message_id`; the text itself lives in the checkpoint, not the audit trail |
| `ui_action` | `handle_ui_action` | `action`, `outcome` note token; never `code` or `token` |
| `tool_called` | tools node wrapper | `name`, redacted args, short result summary, `latency_ms` |
| `field_written` | `draft_ops.write_fields` caller | `key`, `source`, `confirmed`, `value_sha256` (contact fields) or display value (others) |
| `field_confirmed` | `confirm_fields` / `confirm_card` | `keys`, `via` (`agent` or `card`) |
| `guard_verdict` | guard node | `rule`, `retried` |
| `card_shown` | `run_turn` | `card_type`, `card_id` |
| `verification_sent` / `verification_result` | tool and actions | `channel`, `result`; never the code or token |
| `document_added` / `document_removed` | documents router | `doc_type`, `ext`, `size_bytes` |
| `state_transition` | workflow machine | `from`, `to`, `event`, `actor`, `legal` |
| `submit_attempt` / `submit_result` | submit flow | `submit_key`, `outcome`, `reference` |
| `error` | anywhere | `where`, `kind`; no stack traces with PII |

- **Redaction is enforced in one place.** `app/audit/redact.py` keeps an allowlist per event type: unknown payload keys are dropped, and `code`, `token`, `email`, `mobile`, `landline` and `file_name` are always hashed or dropped.
- **Tests assert it.** G4 checks redaction on a full happy-path trail.
- **Access in M0.** `scripts/audit_dump.py <inquiry_id>` prints the trail. An admin API comes with L4 reviewer tooling.

## 9. Supervisor and agent registry (Must)

This prepares for routing (L3) and the post-submit agents (L4) without changing intake behaviour.

```python
@dataclass(frozen=True)
class AgentSpec:
    name: str                                   # "intake", "status"
    description: str
    tools: list[BaseTool]                       # allowlist
    prompt_path: Path
    hint: Callable[[Inquiry], str]              # e.g. bundles.next_bundle_hint
    guard: Callable[[AgentState, AgentRuntime], dict[str, Any]]
```

- **`app/agents/registry.py`** registers two agents:
  - **`intake`** is today's agent moved without behaviour change: same tools, prompt, guard and bundle hints.
  - **`status`** handles a submitted inquiry. Its tools are `get_inquiry_status` and `search_faq`, it has a short prompt, and its guard keeps only the false-claim checks. L4 replaces it with the `case` agent ([L4](l4-outcome-assistance.md) §3.5).
- **`build_graph`** becomes `START → supervisor → {intake | status} → END`. Each branch is a compiled subgraph (agent ⇄ tools → guard), built from its `AgentSpec`.
- **The supervisor is deterministic in M0.** It routes to `status` when `inquiry.status != draft`, otherwise to `intake`. LLM intent routing arrives in L3 (§3.6 there), once there are intents to route between.

## 10. Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `STATE_BACKEND` | `memory` | `memory` or `postgres` |
| `DATABASE_URL` | — | Required when `STATE_BACKEND=postgres` |
| `TURN_LEASE_SECONDS` | `120` | Max length of one chat turn |
| `DRAFT_RETENTION_DAYS` | `30` | Before a draft is marked abandoned |
| `AGENT_HISTORY_MESSAGES` | `40` | Messages sent to the model per call |
| `SUBMIT_RECONCILE_SECONDS` | `120` | Wait before retrying an unknown submit |
| `GATEWAY_TIMEOUT_SECONDS` | `10` | Default timeout per external call |
| `GATEWAY_RETRIES` | `2` | Retries for idempotent calls |

## 11. Contract changes to fold into `docs/spec.md`

- **Data model.** §2 gains `Inquiry` and `InquiryStatus`.
- **Session meaning.** `session_id` keeps its API meaning; the docs note that it maps to an inquiry.
- **Idempotent submit.** `accept_and_submit` is idempotent. New `[ui_event]` notes: `submit_pending`, `submit_failed <reason>`, `submitted reference=… (repeat)`.
- **Services.** §8 `SubmitService` gains `lookup` and the `idempotency_key` argument; `InquiryPayload` is defined.
- **Configuration.** §10 adds the variables above.
- **No other changes.** SSE events, card payloads and tool names are unchanged.

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| Moving session state into Postgres changes timing and breaks streaming order | The parity suite (G1) compares event order; the memory backend stays the test default |
| Lease expiry mid-turn on a slow model call | Lease is 120 s; `run_turn` renews it every 30 s while streaming |
| Trimming history drops context the model needs | Trim only at turn boundaries; the system prompt carries the full draft; live eval in G1 |
| Audit trail leaks PII | One allowlist redactor; G4 asserts on a full trail |

## 13. Open questions for Cenomi

- **Q1** Hosting: managed Postgres available in the target environment, or another store?
- **Q2** Retention period for submitted inquiries and their audit trail.
- **Q3** The exact inquiry payload Cenomi's backend expects (field names, document references), so `InquiryPayload` matches it.
