# 00 · Bootstrap

## 1. Goal
Set up a clean, feature-based monorepo (FastAPI backend + Next.js dashboard) with every dependency
installed and one working end-to-end feature: a health check.

## 2. What was built
- **Backend** (`backend/`, one uv project, Python 3.12): FastAPI app factory with CORS from settings,
  `GET /health`, pydantic-settings config that reads the root `.env`, and logging setup.
- Empty feature packages: `tools`, `gateway`, `detection`, `judge`, `audit`, `events`, plus the `agent` and `ml` packages.
- **Tests:** health response, CORS allow and deny, and `CORS_ORIGINS` comma parsing (4 tests).
- **Frontend** (`frontend/`): Next.js 16.4 with App Router, TypeScript (strict), Tailwind v4 and ESLint.
  shadcn/ui is set up with `button`, `card`, `badge` and `dialog`, and `recharts` is installed.
- **system-status feature:** polls `/health` every 5s with a 3s timeout and shows green "connected" or red
  "disconnected", plus the API version.
- `lib/env.ts` and `lib/api-client.ts` are the shared API layer.
- Empty frontend feature folders: `timeline`, `risk-chart`, `approvals`, `audit`, `results`.
- Root files: `README.md`, `.gitignore`, `.env.example`, and `sandbox/{workspace,web}/`.

## 3. File tree (new files)
```
.env.example  .gitignore  .gitattributes  README.md
docs/Sentinel_Roadmap.md (renamed)  docs/progress/00-bootstrap.md
backend/
  pyproject.toml  uv.lock  .python-version
  src/sentinel/__init__.py  main.py
  src/sentinel/core/{__init__,config,logging}.py
  src/sentinel/features/__init__.py
  src/sentinel/features/health/{__init__,router,schemas}.py
  src/sentinel/features/{tools,gateway,detection,judge,audit,events}/__init__.py
  src/agent/__init__.py  src/ml/__init__.py
  tests/conftest.py  tests/core/test_config.py  tests/features/health/test_health.py
frontend/  (create-next-app + shadcn scaffold, then:)
  next.config.ts  tsconfig.json  components.json  package.json
  src/app/{layout,page}.tsx  src/app/globals.css
  src/components/ui/{badge,button,card,dialog}.tsx
  src/features/system-status/{index,schemas,use-backend-health}.ts  system-status-card.tsx
  src/features/{timeline,risk-chart,approvals,audit,results}/.gitkeep
  src/lib/{env,api-client,utils}.ts
sandbox/workspace/.gitkeep  sandbox/web/.gitkeep
```

## 4. How to run
```bash
cp .env.example .env
cd backend && uv sync && uv run uvicorn sentinel.main:app --reload --port 8000
cd frontend && npm install && npm run dev      # second terminal
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `uv run pytest` | `4 passed in 0.03s` |
| `uv run ruff check .` / `ruff format --check .` | `All checks passed!` / `19 files already formatted` |
| `uv run uvicorn sentinel.main:app --reload --port 8000` | `Application startup complete.` |
| `curl localhost:8000/health` | `{"status":"ok","service":"sentinel","version":"0.1.0"}` |
| CORS preflight with `Origin: http://localhost:3000` | `200 OK`, `access-control-allow-origin: http://localhost:3000` |
| `npm run dev` then `curl localhost:3000` | `200` |
| Headless Chrome with the backend up | `Backend: connected` (class `text-green-600`), badge `v0.1.0` |
| Headless Chrome with the backend stopped | `Backend: disconnected` (class `text-red-600`) |
| `npm run lint` / `npx tsc --noEmit` | no output (clean) / ok |
| `npm run build` | `✓ Compiled successfully`, `/` prerendered static |

## 6. Decisions and deviations from the roadmap
- **Layout:** `frontend/` instead of `dashboard/`, and one uv project at `backend/src/{sentinel,agent,ml}`
  instead of top-level folders. This follows the feature-based structure you asked for.
  Roadmap modules map onto features: `tools.py` goes to `features/tools`, `rules/taint/markov/features/scorer` go to `features/detection`, and so on.
- **Python 3.12** is pinned through uv; the system Python is 3.14. 3.12 gives the most reliable ML wheels.
- **Roadmap renamed** from `Sentine1_Roadmap.md` to `Sentinel_Roadmap.md`.
- **No `service.py` for health.** A service that returns a constant would be a premature abstraction.
- **Single version source:** `sentinel/__init__.py` holds `__version__`, and hatch reads it dynamically.
- **One root `.env`:** `next.config.ts` calls `loadEnvConfig("..")` (added `@next/env` as a devDependency),
  so the frontend reads the same file as the backend.
- **pytest `--import-mode=importlib`**, so each feature can have test files with the same name.
- **shadcn components** stay at their default location, `src/components/ui/`, as shared primitives.
- **shadcn bug fix:** its `globals.css` had `--font-sans: var(--font-sans)`, which refers to itself and
  made the page render in a serif fallback. I pointed it at `--font-geist-sans`.
- **Stricter TypeScript:** added `noUncheckedIndexedAccess` on top of `strict`.
- Removed scaffold leftovers: the default Next.js `README.md`, unused `public/*.svg`, and the nested
  `frontend/.git` that `create-next-app` creates.
- Added `.gitattributes` (`eol=lf`) so Windows checkouts keep consistent line endings.

## 7. Known issues / TODO
- Fill in `AGENT_MODEL` and `JUDGE_MODEL` in `.env` from the Anthropic docs.
- The Geist font comes from Google Fonts, so the first `npm run dev` or `npm run build` needs internet.
  Run a build once before the demo so it's cached for offline replay mode.
- `npm install` reports audit advisories from upstream scaffold packages. I haven't run
  `npm audit fix --force`, because it can make breaking upgrades.
- `frontend/AGENTS.md` is generated by Next.js and is re-added by `next dev`, so it's committed.

## 8. Next step
Roadmap **Step 1: agree on the event contract**. Define the shared event schema in the backend
(`features/events` schemas) and the matching TypeScript type in the frontend.
