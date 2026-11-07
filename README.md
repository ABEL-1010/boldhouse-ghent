# Sentinel

**A flight recorder and anomaly detector for AI agents.**

Sentinel sits between a Claude agent and its tools. Every tool call passes through the Sentinel
gateway, where it is scored by policy rules, taint tracking with honeytokens, and ML anomaly
detection (Isolation Forest + a Markov sequence model). High-risk actions pause the agent until a
human approves or denies them, with a written reason. Every event lands in a tamper-evident audit
log and streams live to a dashboard.

Built in one day at the Boldhouse hackathon. The full plan is in
[docs/Sentinel_Roadmap.md](docs/Sentinel_Roadmap.md), and progress per step is in [docs/progress/](docs/progress/).

> **Status:** Milestone 1 reached, plus the ML layers. Every call is scored by policy rules, taint
> tracking, honeytokens, an Isolation Forest and a Markov sequence model (FLAG / PAUSE with a human decision).
> See [docs/progress/](docs/progress/).

## Repository layout

```
backend/    Python (uv) project: gateway (sentinel), agent loop (agent), ML (ml), fake web (fakeweb)
frontend/   Next.js dashboard (App Router, TypeScript, Tailwind, shadcn/ui, Recharts)
sandbox/    workspace/ (pristine seed incl. fake honeytoken .env), web/ (fake pages incl. a
            poisoned one), honeytokens.txt. Tools run on a disposable copy in sandbox/.runtime/
docs/       Roadmap and step-by-step progress notes
```

Both apps are organized **by feature**: each feature owns its router, service, schemas and tests
(backend `src/sentinel/features/*`, frontend `src/features/*`). Shared code lives only in
`backend/src/sentinel/core/` and `frontend/src/lib/`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 for you)
- Node.js 20+ and npm

```bash
# Install uv if needed (Windows, PowerShell):
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup (once)

Run from the repo root:

```bash
cp .env.example .env              # then fill in ANTHROPIC_API_KEY, AGENT_MODEL, JUDGE_MODEL
cd backend && uv sync && uv run sentinel-reset && uv run sentinel-traces && uv run sentinel-train && cd ..
cd frontend && npm install && cd ..
```

There is a single `.env` at the repo root. The backend reads it through
`backend/src/sentinel/core/config.py`, and the frontend loads it in `frontend/next.config.ts`.

## Run

Use three terminals, all starting at the repo root.

```bash
# Terminal 1: API on http://localhost:8000
cd backend
uv run uvicorn sentinel.main:app --reload --port 8000
```

```bash
# Terminal 2: fake web for fetch_url on http://localhost:8001 (e.g. /news1.html, /productivity-tips.html)
cd backend
uv run uvicorn fakeweb.main:app --port 8001
```

```bash
# Terminal 3: dashboard on http://localhost:3000
cd frontend
npm run dev
```

Open http://localhost:3000, the **live dashboard**:
- **Timeline**: every tool call, green (allowed) / amber (flagged) / red (paused), with its outcome
  and who decided it.
- **Risk per step**: a chart with the Flag (0.5) and Pause (0.8) thresholds.
- **Signal breakdown**: policy rules, taint, ML anomaly and sequence model for the selected call.
- **Approval dialog**: opens on every PAUSE. **Approve once** needs a written reason (at least 10
  characters); **Deny** blocks the action. No answer means a fail-safe deny.

Quick API check:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"sentinel","version":"0.1.0"}
```

### Gateway API

| Endpoint | Purpose |
|---|---|
| `POST /tool` `{session_id, tool, args}` | Score a tool call, then run it, or hold it (PAUSE) for a human. Returns `{ok, content, event_id, action}` |
| `POST /decision/{event_id}` `{approve, reason}` | Approve or deny a paused call. **Approving needs a reason of at least 10 characters.** No answer within `DECISION_TIMEOUT_SECONDS` (90) means a fail-safe **deny** |
| `GET /events` | Server-Sent Events: full event snapshots named `created`, `explained`, `decided`, `completed`. New clients get the history first |

```bash
curl -N http://localhost:8000/events      # watch the live stream
```

## Run the agent

Needs `ANTHROPIC_API_KEY` and `AGENT_MODEL` in `.env`.

```bash
cd backend
# Through Sentinel (default; needs the API from terminal 1 and fake web from terminal 2):
uv run sentinel-agent "Summarize http://localhost:8001/news1.html and save it to summary.md"

# Baseline WITHOUT Sentinel (tools run directly; shows what happens when nobody is watching):
uv run sentinel-agent --unprotected "Summarize http://localhost:8001/productivity-tips.html"
```

If Sentinel is unreachable, the agent stops. It never falls back to running tools unprotected.

## Demo: red-team mode (scripted attacks, no API cost)

Real Claude usually refuses these injections (its cyber safeguards stopped our live test). So the
demo uses a **scripted compromised agent**. Only the model is mocked: every call goes through the
real gateway, scorer and tools, so the events are genuine.

```bash
cd backend
uv run sentinel-redteam --list                     # A1 A3 A4 A5 A6 attacks, B2 benign
uv run sentinel-redteam A1 --delay 1.5             # through Sentinel; decide the PAUSE in the dashboard
uv run sentinel-redteam A1 --unprotected           # same script, no Sentinel: shows the leaked secrets
uv run sentinel-reset                              # clean sandbox + outbox between runs
```

## Train the ML layers (free, about 30 s)

```bash
cd backend
uv run sentinel-traces    # 1000 simulated benign sessions → models/traces.jsonl (no API calls)
uv run sentinel-train     # Isolation Forest + Markov → models/sentinel.joblib, prints the alert budget
```

Restart the API afterwards. Without a model file, Sentinel runs with rules + taint only and logs a warning.

## Reset the sandbox

Tools never modify the committed seed. They work on `sandbox/.runtime/workspace/`, and mocked
`send_email` / `http_post` calls are appended to `sandbox/.runtime/outbox.jsonl`. To restore a
clean state (before every demo run):

```bash
cd backend && uv run sentinel-reset
```

## Checks

```bash
cd backend
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
```

```bash
cd frontend
npm run lint
npm test            # Vitest: event store + guards
npm run build
npm run e2e         # real-browser click-through (needs servers + a red-team run; see the script header)
```
