# Build verification status

Generated: `2026-10-31T06:41:39.952596+00:00`.

Build fingerprint: `aeaaca5f00e24886f7536d03eb54a23d57158ba57dc9e6d3048954f9056e75b8`.

## Gate status

| Gate | Result |
|---|---|
| Demo 1 | **PASS** |
| Demo 2 | PASS |
| Demo 3 | PASS |
| Demo 4 | PASS |
| OpenAI acceptance | PASS |
| Complete application | **PASS** |

## Demo 1 verification layers

| Layer | Result |
|---|---|
| Deterministic state and memory tests | PASS |
| PostgreSQL integration | PASS |
| Live OpenAI | PASS |

The current memory-run report contains `77` passed checks and `12` unavailable checks.
The complete application result also requires all 55 planned cases and no skipped PostgreSQL checks.
The [acceptance ledger](../runs/acceptance-summary.json) preserves each planned case and its evidence layer.

## Next action

If a gate remains incomplete, continue at that stage.
If all gates pass, follow [the four-demo guide](guide-four-demos.md).
Run `ops/test-demo1.ps1 -Postgres -Live` for cumulative database and live verification.
The command retains its original filename and runs all implemented tests.
Do not advance until the current stage and all previous stages pass.

The runner rejects reports from a different source or test fingerprint.
Unimplemented later cases remain `NOT_RUN`.
Unavailable database or live checks remain incomplete acceptance.

Language and meaning were reviewed.
Full ASD-STE100 dictionary review remains incomplete.
