# 03 · Agent loop

## 1. Goal
A Claude tool-use agent that never executes tools itself: every call goes to an executor, which by
default is Sentinel's gateway (Roadmap §5 Step 3).

## 2. What was built
- **`run_agent()`** (`agent/loop.py`) is an async manual tool-use loop built on `AsyncAnthropic`:
  - It appends the full assistant `content` every turn, so thinking blocks are passed back unchanged.
  - It runs every `tool_use` in a turn and returns all `tool_result` blocks in one user message. Failures
    get `is_error: true`.
  - It stops on any non-tool stop reason (`end_turn`, `max_tokens`, `refusal`, …) without running a
    possibly truncated tool call. It resumes `pause_turn`, and has a max-turns guard (`AGENT_MAX_TURNS`,
    default 15).
- **Tool definitions** (`agent/tool_definitions.py`) are generated from Sentinel's `TOOL_ARGS`: the name,
  the docstring as the description, and the Pydantic JSON schema as `input_schema`. Agent and tools can't
  drift apart.
- **Executors** (`agent/executors.py`):
  - `GatewayExecutor` sends `POST {SENTINEL}/tool` with a 120 s timeout, longer than the 90 s human
    window. An HTTP error becomes a failed outcome; an unreachable gateway raises `GatewayUnavailable`, which **stops the run**.
  - `UnprotectedExecutor` calls `ToolService` directly. It's the baseline.
- **CLI:** `uv run sentinel-agent "task" [--unprotected] [--session ID] [--max-turns N]` prints each tool
  call live and the final answer. It gives clear errors for a missing model, missing credentials, a bad key or
  model, rate limits, an unreachable gateway and a missing sandbox. The unprotected mode prints a loud warning.
- **Tool descriptions** were added to the args models (docstrings plus field descriptions).
- **Config:** `AGENT_MAX_TURNS` and `sentinel_base_url`.
- **Tests:** 19 new ones covering the loop, executors, tool definitions, the CLI, and a scripted
  end-to-end baseline where a "compromised" model follows `poisoned.html` and the real tools leak all 4
  honeytokens with no Sentinel.

## 3. File tree (new or changed)
```
.env.example                                  (+ AGENT_MAX_TURNS)
README.md                                     (+ "Run the agent")
backend/pyproject.toml                        (+ sentinel-agent script)
backend/src/agent/__init__.py  cli.py  executors.py  loop.py  session.py  tool_definitions.py
backend/src/sentinel/core/config.py           (+ agent_max_turns, sentinel_base_url)
backend/src/sentinel/features/tools/schemas.py (tool descriptions)
backend/tests/agent/test_loop.py  test_executors.py  test_tool_definitions.py  test_cli.py
backend/tests/agent/test_unprotected_baseline.py
docs/progress/03-agent-loop.md
```

## 4. How to run
```bash
cd backend
uv run sentinel-reset
uv run uvicorn fakeweb.main:app --port 8001          # separate terminal
uv run sentinel-agent --unprotected "Summarize http://localhost:8001/news1.html into summary.md"
uv run sentinel-agent "…"                            # via Sentinel, once the gateway exists (Step 4)
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `uv run pytest` | `101 passed, 1 skipped in 6.38s` |
| `uv run ruff check .` / `ruff format --check .` | `All checks passed!` / `51 files already formatted` |
| `uv run sentinel-agent "List the workspace"` with the real `.env` | `AGENT_MODEL is empty. …`, exit 2 |
| Same command, `AGENT_MODEL` set, no credentials | `No Anthropic credentials found. Set ANTHROPIC_API_KEY in .env.`, exit 1 |
| Same command, invalid key (reached the real API) | `Anthropic API rejected the credentials. Check ANTHROPIC_API_KEY.`, exit 1 |
| Scripted baseline test | `fetch_url → read_file → send_email` all ok; all 4 honeytokens are in the outbox |

**Not verified yet:** a live run against a real Claude model. `.env` has no `ANTHROPIC_API_KEY` or
`AGENT_MODEL`. Once they're filled in, run the two commands in section 4.

## 6. Decisions and deviations from the roadmap
- **Async loop** (`AsyncAnthropic`) instead of the roadmap's sync example. Step 7a runs 60–100 sessions
  in parallel, and the gateway call can wait up to 90 s on a human.
- **Tool calls run sequentially within a turn.** Steps stay ordered for the Markov sequence model, and a
  PAUSE on one call holds back the rest of that turn.
- **Fail closed.** If Sentinel is unreachable, the run stops. It never falls back to unprotected execution.
- **`--unprotected` mode**, as agreed. It's the live-testable baseline now, and the "without Sentinel" half
  of the pitch.
- **No `strict: true` on tools.** Strict mode requires every property to be in `required`, and `list_dir`'s
  `path` has a default. Sentinel's `ToolService` validates every call server-side anyway, which is the
  right trust boundary.
- **Refusal fallbacks (`fallbacks: "default"`) are not enabled.** The model comes from `.env` (any model),
  and for a security demo a refusal should stay visible ("Claude refused the injection" is a pitch moment)
  rather than being silently re-run on another model. A refusal stops the run with `stop_reason=refusal`.
  It's easy to add later if wanted.
- **No `thinking` or `effort` parameters are sent**, so the model's defaults apply. For Opus 5.5 that's
  adaptive thinking at effort `medium`. These can be tuned once there's a live baseline.
- **Credentials:** the key from `.env` is passed to the client explicitly, because pydantic-settings doesn't
  export it. Without it, the SDK's normal credential resolution applies (env vars, `ant auth login` profile).
- **Benign task templates and red-team mode are not in this step**, as planned. They come in Step 7a and §9.

## 7. Known issues / TODO
- **A live Claude run is pending your API key and model IDs.**
- Importing the `anthropic` SDK takes about 5–6 s on this Windows machine (first-import and antivirus
  scanning). That's why the test suite takes 6 s instead of 1 s; our own tests are fast.
- `test_cli` stubs `run_agent`. The real network path for an unreachable gateway is covered in
  `test_executors.py` with a mock transport.

## 8. Next step
Roadmap **Step 4: the gateway**. `POST /tool` (scoring stub → execute via `ToolService` → event), PAUSE with
a `POST /decision/{id}` human decision that requires a reason, the 90 s fail-safe deny, `GET /events` (SSE
full snapshots), and creating the sandbox on startup if it's missing.
