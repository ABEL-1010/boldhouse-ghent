# 10 · Live dashboard

## 1. Goal
One live screen where judges watch the agent, see why Sentinel intervenes, and where a human approves or
denies paused actions (Roadmap §5 Step 10).

## 2. What was built
- **Event stream** (`lib/events/use-event-stream.ts`): `EventSource` on `GET /events`, listening to
  `created` / `explained` / `decided` / `completed`. It shows the connection state (Live, Reconnecting).
  It **resets on every (re)connect**, because the server replays its history, which fixes the
  restarted-server issue noted in Step 4.
- **The pure store** (`lib/events/store.ts`) replaces events by `event_id`, lists sessions, orders by step,
  finds pending decisions and works out each event's outcome. **Runtime guards** (`guards.ts`) drop
  malformed SSE payloads.
- **Timeline**: a card per call with a status colour **plus an icon and label**, the target, the risk, and
  the outcome (executed / *approved by human, executed* / blocked + the human's reason / failed / waiting).
  Clicking a card selects it.
- **Risk chart** (Recharts): a neutral 2px line, status-coloured 10px markers with a 2px surface ring,
  dashed Flag 0.5 / Pause 0.8 lines with direct labels, a crosshair and tooltip, and no animation (live
  data).
- **Signal breakdown**: neutral bars for policy rules, taint, ML anomaly and sequence, plus a plain-language
  "why", strongest evidence first.
- **Approval dialog**:
  - It opens on every PAUSE (and queues several), and **can't be dismissed without a decision**.
  - It shows the action and its args, the signal bars and the reasons. Claude's explanation appears only
    once Step 9 fills it.
  - It has a reason textarea. **Approve once stays disabled under 10 characters.**
  - Deny, server errors, and an "already decided by the fail-safe" message are all handled.
  - It closes when the `decided` event arrives, whether a human or the timeout decided.
- **The session picker** follows the newest session unless you pick one.
- **Tooling:** Vitest (19 tests for the store, guards and labels) and `npm run e2e`, a `playwright-core`
  click-through that drives your **installed Chrome**, with no browser download.

## 3. File tree (new or changed)
```
README.md                                         (dashboard + checks)
frontend/package.json  package-lock.json          (vitest, playwright-core, @types/node ^22; test/e2e scripts)
frontend/.gitignore                               (+ /e2e-shots)
frontend/vitest.config.mts
frontend/scripts/e2e-approval.mjs
frontend/src/app/page.tsx
frontend/src/components/ui/textarea.tsx           (shadcn)
frontend/src/lib/api-client.ts                    (+ apiPost with FastAPI error detail)
frontend/src/lib/events/action-badge.tsx  guards.ts  labels.ts  store.ts  use-event-stream.ts
frontend/src/lib/events/store.test.ts  guards.test.ts  fixtures.ts (doc)
frontend/src/features/live-session/  timeline/  risk-chart/  signals/  approvals/   (index.ts + components)
docs/progress/10-dashboard.md
```

## 4. How to run
```bash
cd backend && uv run uvicorn sentinel.main:app --port 8000      # terminal 1
cd backend && uv run uvicorn fakeweb.main:app --port 8001       # terminal 2
cd frontend && npm run dev                                      # terminal 3 → http://localhost:3000
cd backend && uv run sentinel-redteam A1 --delay 1.5            # terminal 4: watch and decide in the browser
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `npx tsc --noEmit` / `npm run lint` | clean / clean |
| `npm test` | `Tests 19 passed (19)` |
| `npm run build` | `✓ Compiled successfully` |
| Backend `uv run pytest` / `ruff check` | `259 passed, 1 skipped` / `All checks passed!` |

**`npm run e2e`** in real Chrome, while `sentinel-redteam A1 --delay 1` ran against the live API, fakeweb
and dashboard (run twice, both times exit 0):
```
PAUSE 1: read_file
  ok  Approve is disabled without a reason
  ok  Approve stays disabled for a 2-character reason
  ok  Approve is enabled with a real reason
  decided: APPROVE
PAUSE 2: send_email
  ok  Approve is disabled without a reason
  ok  Approve stays disabled for a 2-character reason
  decided: DENY
  ok  Timeline shows the denied action as blocked
outbox bytes: 0
```
I checked the screenshots by eye. They show the timeline (Allowed / Paused → *Approved by human,
executed: …* / Paused → *Blocked: …*), the chart with its thresholds, and the signal breakdown matching the
backend log. Two layout issues found that way were fixed: a wrapping "secret data" label, and a long
reason squeezing the risk column.

## 6. Decisions and deviations from the roadmap
- **No Audit or Results tabs yet.** Those need the hash-chain audit log and `eval.py`. Empty tabs would be
  placeholders, which you ruled out.
- **The modal can't be dismissed.** The roadmap just says "modal on PAUSE"; the agent is frozen anyway, so
  a decision (or the fail-safe) is the only way out.
- **The rules bar is 0 or 1** (any rule hit), with the rule names listed under it. Events carry rule *names*,
  not their weights, and duplicating the backend weights in the UI would drift.
- **Status colours come from the dataviz skill's reserved status palette** (`#0ca30c` / `#fab219` / `#d03b3b`),
  always with an icon and a label. Magnitude bars use one neutral hue, so status colour never doubles as
  magnitude.
- **`@types/node` was raised from 20 to 22** to match your installed Node 22. Vitest 5 requires it; I didn't
  force past the peer conflict.
- **Vitest and playwright-core** (dev only) were agreed. Playwright uses `channel: "chrome"`, so nothing is
  downloaded.

## 7. Known issues / TODO
- **A `next dev` was already running on port 3000 (PID 29044)** when I verified, either one you started or
  a leftover from my Step 0 check, so my second dev server exited. The e2e test ran against that existing
  server, which hot-reloads the same folder. I left it running.
- Plain `chrome --headless --virtual-time-budget` hangs on this page, because the open SSE stream keeps the
  page busy. Use Playwright for screenshots, as the e2e script does.
- The dashboard holds every event in memory. That's fine for a demo, but for long sessions, add pagination
  once the audit log exists.

## 8. Next step
**Step 9: Claude Haiku explanations** (paid key, now allowed). It fills the dialog's "Claude's assessment"
section, which already renders when `explanation` is set. After that: the **hash-chain audit log** with an
Audit tab, then **eval** with a Results tab.
