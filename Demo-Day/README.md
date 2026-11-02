# Persistent user memory service

This project implements the [PRD](spec-persistent-memory-prd.md) through the [four-demo test plan](eval-persistent-memory-test-plan.md).

The service uses one parent graph and one persistent billing worker.
PostgreSQL stores conversation checkpoints and long-term records.
The pgvector extension provides similarity search in the same database.
OpenAI supplies answers, structured memory proposals, summaries, and embeddings.

**Acceptance:** All four demonstration gates and all 55 planned cases passed.
The final PostgreSQL run passed 89 checks without skips.
Five live OpenAI checks passed separately.

Start with the [Windows setup guide](docs/guide-local-setup.md).
Then inspect the [build status](docs/eval-build-status.md).
Use [the four-demo guide](docs/guide-four-demos.md) for the presentation commands.

The [architecture document](docs/arch-persistent-memory.md) contains the Mermaid flowcharts and the component glossary.
The [source comparison](docs/ref-source-comparison.md) identifies the pinned notebooks and intentional changes.
The original PRD and test plan retain their planning status as preserved acceptance baselines.
The build status records executed verification.
The [completion audit](docs/eval-completion-audit.md) maps all cases to their assertions and source cells.

## Commands

Run these commands from this folder after setup:

```powershell
.venv\Scripts\user-memory.exe doctor
.venv\Scripts\user-memory.exe db-init
.venv\Scripts\user-memory.exe chat --org demo-org --user alex --thread preferences
.venv\Scripts\user-memory.exe profile --org demo-org --user alex
.venv\Scripts\user-memory.exe search --org demo-org --user alex "appearance preference"
.venv\Scripts\user-memory.exe inspect --org demo-org --user alex --thread preferences
```

`chat` uses OpenAI directly and requires a local API key.
`doctor` prints configuration status without printing credentials.
The service has a command-line interface.
The PRD excludes a browser interface.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
powershell -NoProfile -ExecutionPolicy Bypass -File ops/test-demo1.ps1 -Postgres -Live
```

The first command runs deterministic tests and skips integration checks without their required selection.
The second command requests database and live OpenAI verification.
Live calls use API credits.
An incomplete gate returns exit code `2`.

The test providers exist only in `tests/`.
The application does not silently substitute a test provider when OpenAI fails.

## Local data

The preparation script creates database credentials and leaves the OpenAI-key field blank for local entry.
This workspace already has a locally configured key.
The file is excluded from version control.
Keep the Docker volume during restart demonstrations.
No command performs a real refund.

Language and technical meaning were reviewed.
Full ASD-STE100 dictionary review remains incomplete.
