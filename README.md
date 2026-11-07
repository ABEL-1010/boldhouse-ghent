# Sentinel

**A flight recorder and anomaly detector for AI agents.**

Sentinel sits between a Claude agent and its tools. Every tool call passes through the Sentinel
gateway, where it is scored by policy rules, taint tracking with honeytokens, and ML anomaly
detection (Isolation Forest + a Markov sequence model). High-risk actions pause the agent until a
human approves or denies them, with a written reason. Every event lands in a tamper-evident audit
log and streams live to a dashboard.

Built in one day at the Boldhouse hackathon. The full plan is in
[docs/Sentinel_Roadmap.md](docs/Sentinel_Roadmap.md), and progress per step is in [docs/progress/](docs/progress/).

> **Status:** event contract, sandbox and sandboxed tools are done. The gateway, detection and
> agent loop come next. See [docs/progress/](docs/progress/).

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
cd backend && uv sync && uv run sentinel-reset && cd ..
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
# Terminal 2: fake web for fetch_url on http://localhost:8001 (e.g. /news1.html, /poisoned.html)
cd backend
uv run uvicorn fakeweb.main:app --port 8001
```

```bash
# Terminal 3: dashboard on http://localhost:3000
cd frontend
npm run dev
```

Open http://localhost:3000. The **System Status** card shows "Backend: connected" in green, or
"disconnected" in red. It re-checks every 5 seconds.

Quick API check:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"sentinel","version":"0.1.0"}
```

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
npm run build
```
