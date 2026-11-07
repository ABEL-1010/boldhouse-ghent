# 04 · Gateway

## 1. Goal
Put Sentinel between the agent and its tools. Every call is scored and published. High-risk calls
freeze until a human decides, with a fail-safe deny (Roadmap §5 Step 4).

## 2. What was built
- **`POST /tool`** (`GatewayService.handle`):
  1. Assigns a per-session step.
  2. Scores the call through the `Scorer` protocol.
  3. Publishes the `created` event.
  4. On PAUSE, awaits a decision.
  5. Runs the tool via `ToolService`, or returns `Blocked by Sentinel: <reason>`.
  6. Publishes `completed`, with the result capped to a 200-character preview.

  It returns `{ok, content, event_id, action}`.
- **`POST /decision/{event_id}`**:
  - Approving needs a reason of 10 or more characters (400 otherwise). A deny without a reason gets
    "Denied by human reviewer".
  - An unknown, already-decided or timed-out id returns 404.
- **Fail-safe deny in two cases.** No human answer within `DECISION_TIMEOUT_SECONDS` (default 90) gives
  `source: "timeout"`. If the agent disconnects while paused, the gateway records a deny and completes the
  event, so the dashboard is never left with a dangling PAUSE.
- **`GET /events`** (SSE via sse-starlette). It sends full `SentinelEvent` snapshots, with the event name
  `created` / `decided` / `completed` and the `event_id` as the SSE id. A new client first gets the whole
  history, then live messages. It pings every 15 s.
- **`EventBus`** fans out in memory with an ordered history. `close()` on shutdown ends open streams so
  uvicorn isn't blocked.
- **The `Scorer` protocol** is the only thing the gateway knows about detection. `UnscoredScorer` is
  the agreed explicit stand-in: ALLOW at risk 0, with a startup warning
  `Detection is NOT enabled: every tool call is ALLOWed with risk 0.`
- **App wiring:** `create_app(settings, scorer=, tools=)` builds the services once on `app.state`. On
  startup the lifespan calls `ensure_sandbox()`, which creates the runtime sandbox if it's missing and never
  wipes an existing one.
- **Tests:** 18 new ones covering the gateway (approve, deny, missing reason, 404, timeout, disconnect,
  422s, snapshot shape, per-session steps) and the bus and SSE.

## 3. File tree (new or changed)
```
.env.example                                   (+ DECISION_TIMEOUT_SECONDS)
README.md                                      (+ Gateway API table)
backend/src/sentinel/main.py                   (lifespan, service wiring, routers)
backend/src/sentinel/core/config.py            (+ decision_timeout_seconds, 0 < t < 120)
backend/src/sentinel/features/events/__init__.py  bus.py  router.py
backend/src/sentinel/features/gateway/__init__.py  schemas.py  scoring.py  decisions.py  service.py  router.py
backend/src/sentinel/features/tools/__init__.py  reset.py   (+ ensure_sandbox)
backend/tests/features/gateway/conftest.py  test_gateway.py
backend/tests/features/events/test_bus.py
docs/progress/04-gateway.md
```

## 4. How to run
```bash
cd backend
uv run uvicorn sentinel.main:app --reload --port 8000
uv run uvicorn fakeweb.main:app --port 8001                 # second terminal
curl -N http://localhost:8000/events                        # third terminal: live stream
uv run sentinel-agent "Summarize http://localhost:8001/news1.html into summary.md"   # needs API key
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `uv run pytest` | `119 passed, 1 skipped in 5.47s` |
| `uv run ruff check .` / `ruff format --check .` | `All checks passed!` / `61 files already formatted` |
| Live: agent's `GatewayExecutor` → real API on port 8000 → fakeweb on port 8001 | see below |

```
list_dir    ok=True  Contents of .: | .env | notes.md | project/ | tmp/
fetch_url   ok=True  <!doctype html> …
read_file   ok=False Access denied: '../../sandbox/honeytokens.txt' is outside the workspace
send_email  ok=True  Email sent to team@ourcompany.be.
POST /decision/evt_9999        → {"detail":"No pending action with this id."}
CORS preflight POST /decision  → 200, access-control-allow-origin: http://localhost:3000
curl -N /events                → 8 frames: evt_0001..4 × (created, completed), full JSON snapshots
late subscriber                → replayed all 8 frames
server log                     → WARNING sentinel.gateway: Detection is NOT enabled: …
```
I couldn't trigger PAUSE live, because `UnscoredScorer` never pauses. The PAUSE paths are covered by tests
that run real concurrent HTTP requests through the ASGI app.

## 6. Decisions and deviations from the roadmap
- **`UnscoredScorer`** (option a, agreed) instead of real scoring. Detection plugs in through `Scorer`.
- **Validation order:** 404 for an unknown id comes before the 400 reason check. The roadmap checks the
  reason first, but "no such action" is the more useful answer.
- **A deny doesn't need a reason.** The roadmap only requires one to *approve*, which is what prevents
  rubber-stamping.
- **Agent-disconnect handling** (not in the roadmap) prevents a PAUSE that never resolves in the dashboard.
- **`DECISION_TIMEOUT_SECONDS` is capped below 120 s**, the agent's gateway timeout, so the agent never
  times out before Sentinel's fail-safe decides.
- **Unknown tools and bad session ids are rejected with 422** before any event is created, because the
  event contract only allows the 7 known tools.
- **The Claude explanation (Step 9) and the hash-chain audit log are not in this step.**

## 7. Known issues / TODO
- Event history and step counters are in memory and reset when the API restarts, and event ids restart at
  `evt_0001`. The dashboard should clear its state when it reconnects. A persistent audit log (SQLite with
  a hash chain) is the later fix.
- Subscriber queues are unbounded. That's fine for a demo, but a slow client buffers everything.
- `tests/features/gateway/test_gateway.py` imports helpers from its `conftest.py`. It works under pytest's
  importlib mode here, but if it ever breaks, move the helpers into a fixture.

## 8. Next step
**Step 5: feature extraction.** A `SessionContext` per session and the roadmap's feature vector,
computed before each call runs.
