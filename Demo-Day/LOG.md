# Build log

## 2026-10-31

The user authorized implementation against the existing PRD and four-demo test plan.
The source commit is `a1ff481c87cc3784c9c920c8e315b3341f57e563`.
Three unchanged Chapter 10 notebooks were saved in `data/source/`.

Tests were written before the Demo 1 application modules.
The first run failed because the application package did not exist.
The CLI tests also failed before the CLI implementation existed.
The failing results remain in `runs/`.

The Demo 1 parent graph and user-memory service now pass deterministic checks.
The database adapter, command-line interface, and Docker configuration are implemented.
Database execution remains unverified.
Live OpenAI inference remains unverified.

One transport test initially mocked the wrong HTTP client class.
A synthetic request received an authentication rejection.
The test now intercepts the SDK's actual `httpx2` client.
Deterministic tests also block external socket connections.
No valid API credential was available during that failed transport test.

The session has no administrator access.
Docker and WSL were absent during prerequisite checks.
The user requested setup instructions instead of automatic installation.
The instructions are in `docs/guide-local-setup.md`.

The `.env` preparation script created a random local database password.
The OpenAI-key field remains blank.
No credentials appear in this log.

Demo 1 remains incomplete until its database and live layers pass.
Demos 2 through 4 have not started.
The complete goal remains active.

### Demo 1 retrieval review

The next review found two saved-memory paths missing from assistant context.
Profile summaries and recorded episodes were stored but not supplied to the assistant.
Two new tests failed on those omissions before the implementation changed.
The context builder now includes those records within the existing token limit.
A separate test checks profile-summary isolation between users.
Docker and OpenAI verification remain unavailable.

### Demo 1 gate passed

Docker Desktop, WSL 2, and a local OpenAI key became available during the build.
The PostgreSQL container is healthy.
Both live OpenAI checks passed.
The local database URLs now use `127.0.0.1`, matching the Docker IPv4 binding.

The first database run exposed test-fixture assumptions.
Controlled embeddings now contain nonzero vectors and tokenize the unique index suffix correctly.
Test identities now use a unique organization and user for each test.
The secret-boundary test reads checkpoint content through the common saver interface.

Demo 1 passed 34 controlled checks, 34 PostgreSQL checks, and two live checks.
The gate receipt is `runs/demo1-gate-passed-summary.json`.

Demo 2 tests were written next.
The first run failed because checkpoint encryption configuration did not exist.
The current run tests separate-process restoration and encrypted checkpoints.

### Demo 2 gate passed

The cumulative PostgreSQL suite passed 44 checks.
Both live OpenAI checks passed.
Separate-process receipts include process identifiers, checkpoint identifiers, and restored records.
The gate receipt is `runs/demo2-gate-passed-summary.json`.

Docker Desktop stopped during an earlier regression attempt.
The application reported connection failures without claiming successful persistence.
The project container now uses the `unless-stopped` restart policy.
The test runner does not make live calls after failed or unavailable database checks.

### Demo 3 implementation

Twelve tests failed before correction, deletion, command routing, and scheduling were implemented.
Corrections now remove exact fact identifiers instead of replacing an entire category.
Deletion updates the authoritative profile and searchable copies.
Compaction removes redundant profile projections while retaining authoritative facts.
Summary operations retain durable message counters and duplicate-delivery hashes.
Organization writes check the trusted administrator flag.
A live correction, summary, and recall check passed.
Cumulative verification remains required before Demo 4 opens.

### Demo 3 gate passed

The cumulative PostgreSQL suite passed 70 checks before Demo 4 implementation.
Four live OpenAI checks passed.
The gate receipt is `runs/demo3-gate-passed-summary.json`.

### Demo 4 and complete acceptance passed

The persistent billing worker now maintains a separate checkpoint namespace.
The parent tracks delivered message identifiers.
First delegation supplies history.
Later delegations supply unseen messages.

The comparison modes produced the expected message counts.
Per-thread mode produced `1, 3, 5`.
Per-invocation and stateless modes each produced `1, 1, 1`.
Separate-process tests restored both graph histories and the delivery tracking.
Late-entry, duplicate-briefing, isolation, branch, and replay tests passed.

The final controlled run passed 77 checks.
It skipped 12 database-specific checks.
The final PostgreSQL run passed all 89 checks without skips.
Five live OpenAI checks passed.
All reports match the final build fingerprint.

All four gates and all eight OpenAI criteria passed.
The final ledger covers all 55 planned cases and all 18 PRD stages.
The completion audit is `docs/eval-completion-audit.md`.
The final gate receipt is `runs/demo4-gate-passed-summary.json`.

The final source audit preserved the PRD, test plan, and three notebooks.
The credential audit found no real secrets in the checked artifacts.
The Windows setup and demonstration guides now describe the working application.
The Mermaid flowcharts were rendered and the current flow was visually checked.

Earlier setup limitations in this log describe the initial build state.
Docker, PostgreSQL, pgvector, and the local OpenAI key are now available.
The application remains within the PRD's local, single-process scope.
