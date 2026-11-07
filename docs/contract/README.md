# Sentinel event contract

Every part of Sentinel (gateway, audit log, SSE stream, dashboard) speaks one shape: the
**SentinelEvent**.

| File | Role |
|---|---|
| [event.schema.json](event.schema.json) | Generated JSON Schema. **Source of truth.** |
| [event.example.json](event.example.json) | The roadmap example, used by the backend tests |
| `backend/src/sentinel/features/events/schemas.py` | Pydantic models (the schema is generated from these) |
| `frontend/src/lib/events/types.ts` | TypeScript mirror |
| `frontend/src/lib/events/fixtures.ts` | Sample ALLOW / FLAG / PAUSE events for UI work |

## Lifecycle and streaming

An event is created when a tool call is scored, then filled in step by step:

| SSE event name | What changed | Always sent? |
|---|---|---|
| `created` | Event scored: `signals`, `risk` and `action` are set | yes |
| `explained` | `explanation` set by the Claude judge (advisory only) | FLAG / PAUSE only |
| `decided` | `decision` set by a human, or `source: "timeout"` for the fail-safe deny | PAUSE only |
| `completed` | `result` set: the tool ran (`ok: true`) or was blocked (`ok: false`) | yes |

Each SSE message's `data` is the **full event snapshot**, not a diff. Clients store events by
`event_id` and replace the stored event on every message. Replay mode works the same way.

## Rules
- `risk`, `ml_risk` and `markov_risk` are in `[0, 1]`. Timestamps are UTC ISO-8601 (`...Z`).
- `rules` is a closed list. Adding a rule is a contract change.
- `result.preview` is at most 200 characters.
- The judge's `explanation` never changes `risk` or `action`.

## Changing the contract
1. Edit `schemas.py`.
2. Regenerate the schema: `cd backend && UPDATE_CONTRACT=1 uv run pytest tests/features/events`
3. Update `frontend/src/lib/events/types.ts` to match, then run `npx tsc --noEmit`.
4. A plain `uv run pytest` fails if the committed schema doesn't match the models.
