# 05 · Feature extraction

## 1. Goal
Turn every tool call into the roadmap's fixed-order numeric feature vector, computed from the call and
the session's history **before** the call runs (Roadmap §5 Step 5).

## 2. What was built
- **`extract_features(tool, args, ctx) -> dict[str, float]`**: 17 features in `FEATURE_NAMES` order.
  - The 7 `tool_*` one-hots.
  - `sensitive_target`, `outbound`, `unknown_destination` and `destructive` (delete, or overwriting an
    existing file).
  - `payload_log_len`, `payload_entropy` (Shannon, bits per character) and `secret_pattern`.
  - `step`, scaled by 20 and capped at 1, and `sensitive_reads_so_far`, scaled by 5 and capped.
  - `outbound_after_sensitive`.

  The column order is the ML model's contract: append new features, never reorder.
- **`SessionContext`**, one per session:
  - It tracks `steps_so_far` and `sensitive_reads`, and only *successful* reads count.
  - `is_allowlisted(target)` checks the email domain or URL host against `SENTINEL_ALLOWED_DOMAINS`. Exact
    domains and real subdomains match; `ourcompany.be.evil.example` and `http://ourcompany.be@evil.example`
    don't.
  - `exists(path)` is sandboxed through the tools feature's public `file_exists_in_workspace`.
- **Gateway wiring.** The gateway keeps one context per session and passes it to the scorer in
  `ScoringInput.context` as it was *before* the call. It calls `observe()` when each call completes,
  whether it ran, was blocked or the agent disconnected. The per-session step now comes from the context.
- **Tests:** 50 new ones covering features, context and allowlist edge cases, plus a gateway test proving
  the scorer sees the pre-call context and that sessions are isolated.

## 3. File tree (new or changed)
```
.env.example                                       (+ SENTINEL_ALLOWED_DOMAINS)
README.md                                          (status line)
backend/src/sentinel/core/config.py                (+ sentinel_allowed_domains, comma-separated)
backend/src/sentinel/main.py                       (session context factory)
backend/src/sentinel/features/detection/__init__.py  patterns.py  context.py  features.py
backend/src/sentinel/features/gateway/scoring.py   (+ ScoringInput.context)
backend/src/sentinel/features/gateway/service.py   (contexts per session, observe on completion)
backend/src/sentinel/features/tools/__init__.py  sandbox.py  service.py   (file_exists_in_workspace, .workspace)
backend/tests/features/detection/conftest.py  test_context.py  test_features.py
backend/tests/features/gateway/conftest.py  test_gateway.py   (context assertions)
docs/progress/05-feature-extraction.md
```

## 4. How to run
```bash
cd backend
uv run pytest tests/features/detection
```

## 5. Verification (real output, shortened)
| Check | Result |
|---|---|
| `uv run pytest` | `169 passed, 1 skipped in 6.30s` |
| `uv run ruff check .` / `ruff format --check .` | `All checks passed!` / `67 files already formatted` |
| Features on the real sandbox, benign vs. A1 attack | see below |

```
                      sensitive   outbound   unknown   destructive  entropy  secret  sens_reads  outb_after_sens
benign    fetch_url        0.00       0.00      0.00          0.00     4.35    0.00        0.00             0.00
benign    write_file       0.00       0.00      0.00          0.00     4.17    0.00        0.00             0.00
benign    send_email       0.00       1.00      0.00          0.00     4.38    0.00        0.00             0.00
attack A1 fetch_url        0.00       0.00      0.00          0.00     4.39    0.00        0.00             0.00
attack A1 read_file        1.00       0.00      0.00          0.00     3.50    0.00        0.00             0.00
attack A1 send_email       0.00       1.00      1.00          0.00     5.69    1.00        0.20             1.00
```
The attack's final call lights up `unknown_destination`, `secret_pattern` and `outbound_after_sensitive`,
and its entropy is higher. The benign email triggers none of them.

## 6. Decisions and deviations from the roadmap
- **17 features, not 18.** I miscounted in the plan. The roadmap lists 7 one-hots plus 10 features, and
  all 17 are implemented exactly as specified.
- **`patterns.py`** wasn't in the planned tree. It holds the shared regexes and the outbound-tool set, so
  `context.py` and `features.py` don't import each other.
- **`step` uses `steps_so_far`**, the number of calls finished before this one: 0 for the first call. The
  same definition will apply in training (Step 7), so training and serving agree.
- **Only successful sensitive reads count** toward `sensitive_reads`: a failed read exposed no data.
- **`fetch_url` is not outbound.** It can only reach the fake web, matching the roadmap's `OUTBOUND` set.
- **The allowlist is configurable** via `SENTINEL_ALLOWED_DOMAINS` (default `ourcompany.be`), instead of
  being hard-coded.
- **`SessionContext` holds no tool history or tainted data yet.** The taint layer (Step 6) and the Markov
  model (Step 7) add exactly what they need, so there's no unused state now.

## 7. Known issues / TODO
- **Features aren't used for scoring yet.** `UnscoredScorer` still allows everything. Rules (Step 6) and
  the scorer (Step 8) consume `extract_features` and the context.
- `secret_pattern` misses base64-encoded keys. This is shown in a test on purpose; the taint layer
  (Step 6) decodes base64. Entropy rises for encoded payloads, which the ML can pick up.
- The step comes from completed calls, so two *concurrent* calls in the same session would get the same
  step number. The agent loop is sequential, so this doesn't happen today.

## 8. Next step
Roadmap **Step 6: taint tracking and honeytokens**, plus the **policy rules**, and a real `Scorer` that
replaces `UnscoredScorer`. That reaches the roadmap's Milestone 1: agent → Sentinel → dashboard, rules
only, with real PAUSEs.
