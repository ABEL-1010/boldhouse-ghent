# 01 · Event contract

## 1. Goal
Pin down the single `SentinelEvent` shape that gateway, audit, SSE and dashboard all build against
(Roadmap §5 Step 1).

## 2. What was built
- **Backend models** (`features/events/schemas.py`): frozen, `extra="forbid"` Pydantic models
  `SentinelEvent`, `Signals`, `Explanation`, `Decision`, `ToolResult`. They're re-exported from the
  feature's public `__init__`.
- **Enums:** `ToolName` (7 tools), `RuleId` (4 rules), `Action`, `Verdict`, `DecisionSource`, `StreamEventType`.
- **Validation:** risks in [0, 1], `step >= 0`, the `evt_…` and `s_…` ID formats, timezone-aware timestamps,
  and `preview` capped at 200 characters.
- **Contract artifacts:** `docs/contract/event.schema.json` (generated), `event.example.json` (the roadmap
  example), and a `README.md` covering the lifecycle, the SSE convention and how to change the contract.
- **Frontend:** `lib/events/types.ts` (TypeScript mirror) and `lib/events/fixtures.ts`
  (typed ALLOW / FLAG / PAUSE sample events).
- **Tests:** the roadmap example parses, a JSON round-trip keeps the `Z` timestamp, a lifecycle update
  produces a new snapshot, events are immutable, 12 invalid-input cases are rejected, the preview
  is capped, and a schema drift guard checks the committed file.

## 3. File tree (new files)
```
backend/src/sentinel/features/events/__init__.py   (was empty)
backend/src/sentinel/features/events/schemas.py
backend/tests/features/events/test_schemas.py
backend/tests/features/events/test_contract_snapshot.py
docs/contract/README.md  event.schema.json  event.example.json
frontend/src/lib/events/types.ts  fixtures.ts
docs/progress/01-event-contract.md
```

## 4. How to run
```bash
cd backend && uv run pytest
cd frontend && npx tsc --noEmit
# after an intentional contract change:
cd backend && UPDATE_CONTRACT=1 uv run pytest tests/features/events
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `uv run pytest` before the schema file existed | `1 failed, 21 passed`: the drift guard fired, as expected |
| `UPDATE_CONTRACT=1 uv run pytest tests/features/events` | `18 passed`, schema written |
| `uv run pytest` | `22 passed in 0.05s` |
| `uv run ruff check .` / `ruff format --check .` | `All checks passed!` / `23 files already formatted` |
| `npx tsc --noEmit` / `npm run lint` / `npm run build` | ok / clean / `✓ Compiled successfully` |
| TypeScript negative check (temp file with `"BLOCK"` and `"made_up_rule"`) | `TS2322` on both, then the temp file was removed |

## 6. Decisions and deviations from the roadmap
All of these were agreed before implementation.
- **Added `result: {ok, preview} | null`.** The roadmap's audit stores `result_preview`, but the event shape
  had nowhere for it, and the timeline needs to show whether a call ran or was blocked.
- **Added `source` (`human` / `timeout`) and `ts` to `decision`.** This separates a human deny from the
  90-second fail-safe deny.
- **SSE sends full snapshots**, and the event name (`created` / `explained` / `decided` / `completed`)
  says what changed. Clients replace events by `event_id`, and replay mode reuses this unchanged.
- **`rules` is a closed enum.** A typo fails validation; adding a rule is a deliberate contract change.
- **Models are frozen**, so lifecycle updates use `model_copy(update=...)`.
- **Unplanned addition:** `docs/contract/README.md`, a short guide for teammates. It wasn't in the agreed
  file tree.
- **Frontend types live in `lib/events/`** rather than a feature folder, because timeline, chart, approvals
  and audit all share them.

## 7. Known issues / TODO
- The TypeScript types are hand-mirrored. The JSON Schema is guarded against drift by a test, but TS-vs-schema
  drift isn't checked automatically. The contract README makes it step 3 of "Changing the contract".
- `fixtures.ts` has no consumer yet. It's meant for the timeline and chart work against mock events.
- The approve-needs-a-10+-character-reason rule belongs to the decision *request* (gateway, Step 4) and isn't in
  this contract.

## 8. Next step
Roadmap **Step 2: sandbox and tools.** Sandboxed `read_file`, `write_file`, `delete_file`, `list_dir`,
`fetch_url`, and mocked `send_email` / `http_post` that write to an outbox. Also the sandbox seed files with
honeytokens, and the path-traversal tests.
