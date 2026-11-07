# 07a · Benign traces (free)

## 1. Goal
Produce "normal behaviour" training data for the ML layers without spending anything (Roadmap §5 Step 7a).

## 2. What was built
- **A benign-agent simulator** (`ml/simulator.py`): 15 realistic task plans that use the real tools. They
  cover news summaries, a README to TODO list, emailing notes to colleagues, legitimate `tmp/` cleanup,
  docs Q&A, workspace overviews, article comparisons, meeting agendas, status reports, posting to the
  internal API, organizing reports, read-and-answer, and log review.
  Random variation per session:
  - optional `list_dir` exploration first
  - 1–3 pages
  - different file names and recipients
  - occasional wrong file names followed by recovery
  - partial or full email bodies
- **Recording through the real gateway** (`ml/traces.py`). `RecordingScorer` captures the exact
  production feature vector before each call and always allows it. Each session runs with its own throwaway
  sandbox, the real `GatewayService`, `ToolService` and in-process fakeweb, with no servers and no API calls.
- **`TraceRecord`**: session, task, split, step, tool, args, ok, and the 17 features, written as one JSON line
  per call.
- **Held-out split:** every 5th session (20%), assigned per *session*, so calibration never sees training sessions.
- **CLI:** `uv run sentinel-traces [--sessions 200] [--seed 7] [--out path]`. The default output is
  `models/traces.jsonl`, which is gitignored and can be regenerated in seconds.
- **Tests:** 8 new ones. Every plan runs; the records carry production features in order; there's no attack
  behaviour (no sensitive reads, unknown destinations or secret patterns; destructive calls only in `tmp/`);
  the 20% hold-out; determinism; JSONL round-trip; and the CLI.

## 3. File tree (new or changed)
```
backend/pyproject.toml                              (+ sentinel-traces script)
backend/src/ml/simulator.py  traces.py  generate_traces.py
backend/src/sentinel/core/config.py                 (+ traces_path)
backend/src/sentinel/features/gateway/__init__.py   (exports ToolRequest, ToolResponse)
backend/tests/ml/test_generate_traces.py
docs/progress/07a-benign-traces.md
```

## 4. How to run
```bash
cd backend
uv run sentinel-traces            # → models/traces.jsonl
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `uv run sentinel-traces` | `Wrote 628 calls from 200 sessions` in about 4 s; split train 510 / holdout 118; 6 failed calls (stumbles) |
| Tools | list_dir 163, write_file 132, fetch_url 130, read_file 119, send_email 36, delete_file 34, http_post 14 |
| Tasks | all 15 plans, 13–14 sessions each |
| Feature > 0 rates | sensitive_target 0, unknown_destination 0, secret_pattern 0, outbound 0.08, destructive 0.05 (tmp only) |
| Re-running with the same seed | byte-identical output (`cmp`) |
| `uv run pytest` / `ruff check` / `ruff format --check` | `227 passed, 1 skipped` / `All checks passed!` / `78 files already formatted` |

## 6. Decisions and deviations from the roadmap
- **A simulator instead of real Claude sessions.** You asked for everything to be free; the roadmap
  generates 60–100 real agent sessions with the API.
  - **Consequence:** the ML learns "normal" from my plans, not from Claude's own habits. Real Claude may take
    paths the simulator never does (more exploration, re-reads, rewriting its own files). That could raise ML
    false positives in a live demo.
  - **Mitigation:** the plans vary deliberately. Rules and taint, the decisive layers for the demo, don't
    depend on this data. And `eval.py` (Step 11) will measure the false-positive rate honestly.
- **200 sessions instead of 60–100**, because generation is free and takes seconds.
- **Traces aren't committed.** They're deterministic from the seed and regenerate in seconds, so they stay in
  the gitignored `models/` folder.
- **The plans never read `.env` or other sensitive files.** The roadmap's B1 case ("user asks to see the
  config") is benign-but-unusual and belongs to evaluation, not training.
- **Stumble file names** (`notes.txt`, `README.md` at the root, `todo.md`) were chosen so they don't exist in
  any letter case. With `NOTES.md`, Windows' case-insensitive file system made the traces differ from Linux.

## 7. Known issues / TODO
- Sessions are short: 3.1 calls on average, at most 6. Real agents tend to make more calls.
- If you later want Claude-generated traces (paid), the recorder works the same way. Only the call source
  changes.

## 8. Next step
**7b:** the Isolation Forest and Markov sequence model, trained on these traces and calibrated on the
hold-out, then plugged into `combine()`.
