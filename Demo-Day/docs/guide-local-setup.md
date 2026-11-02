# Windows setup

This guide prepares the local environment for the four memory demonstrations.
The application supports all four demonstrations.
Read [the build status](eval-build-status.md) for the latest acceptance result.
PostgreSQL and pgvector run locally without a cloud database account.
Live model calls require an OpenAI API account and local key.

## 1. Install WSL

WSL is the Windows Subsystem for Linux.
Docker uses its WSL 2 backend to run the PostgreSQL container.

Open PowerShell with **Run as administrator**.
Run this command:

```powershell
wsl --install --no-distribution
```

If Windows requests a restart, save your work first.
Restart Windows from the Start menu.
This project does not restart your computer automatically.

Open a new PowerShell window after installation.
Run these checks:

```powershell
wsl --update
wsl --version
wsl --status
```

Docker currently requires WSL version `2.1.5` or later.
Use the [Microsoft WSL instructions](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#install) if installation reports an error.

## 2. Install Docker Desktop

Download Docker Desktop from the [official Windows installation page](https://docs.docker.com/desktop/setup/install/windows-install/).
Select the WSL 2 backend.
Complete the installer prompts.
Open Docker Desktop.
Wait until its engine starts.

Open a new PowerShell window.
Run these checks:

```powershell
docker version
docker compose version
```

`docker version` must show both the client and the server.
A client-only result does not establish that the engine runs.

## 3. Prepare the project

Run these commands from a normal PowerShell window:

```powershell
Set-Location -LiteralPath 'C:\Users\Be Flith Rich\My Project Folder\Paytm Hackathon\Demo-Day'
uv sync --extra dev
powershell -NoProfile -ExecutionPolicy Bypass -File ops/prepare-local-env.ps1
```

Install `uv` from [its official installation guide](https://docs.astral.sh/uv/getting-started/installation/) if the command is unavailable.
The lock file selects the Python dependencies.

The preparation script preserves an existing `.env` file.
For a new file, it generates a local database password.
It leaves `OPENAI_API_KEY` blank.

The current workspace already contains the prepared file and a locally configured key.
Use these key-entry steps when you configure another machine.
Open `.env` in your editor.
Enter your OpenAI API key after `OPENAI_API_KEY=`.
Keep the generated database settings.
Save the file.

Never paste the key into chat or commit `.env`.
The application also accepts `OPENAI_API_KEY` from the local environment.
Environment values take priority over `.env` values.

## 4. Start PostgreSQL and pgvector

Run these commands from the project folder:

```powershell
docker compose --env-file .env -f ops/compose.yaml up -d --wait
.venv\Scripts\user-memory.exe db-init
.venv\Scripts\user-memory.exe doctor
```

The container exposes PostgreSQL on local port `54329`.
The connection URLs use `127.0.0.1` to match the IPv4 port binding.
It creates separate `memory_demo` and `memory_test` databases.
The `memory-data` volume retains database files.
The initialization command creates the LangGraph tables and vector configuration.

The application and tests both use `1536` vector dimensions.
Deterministic database tests use controlled vectors with that dimension.
Live tests verify embeddings from OpenAI separately.

## 5. Verify all four demonstrations

Run the database and live checks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops/test-demo1.ps1 -Postgres -Live
```

Read [the build status](eval-build-status.md) after the command finishes.
The runner returns a nonzero exit code if a required verification layer remains incomplete.

The runner checks every implemented demonstration.
Acceptance requires all four gates and all eight OpenAI criteria.
Tests use a separate database and unique user identifiers.

Follow [the four-demo guide](guide-four-demos.md) for the presentation commands.

## 6. Try a conversation

For the preference demonstration, temporarily select every-turn extraction:

```powershell
$env:MEMORY_LLM_SYNC_STRATEGY = 'every_turn'
.venv\Scripts\user-memory.exe chat --org demo-org --user alex --thread preferences
```

Enter `I use dark mode and prefer US English.`.
Enter `/exit` to close the chat.
Inspect the saved records:

```powershell
.venv\Scripts\user-memory.exe profile --org demo-org --user alex
.venv\Scripts\user-memory.exe search --org demo-org --user alex "appearance preference"
.venv\Scripts\user-memory.exe inspect --org demo-org --user alex --thread preferences
Remove-Item Env:MEMORY_LLM_SYNC_STRATEGY
```

The ordinary configuration uses five qualifying messages between memory updates.
A checkpoint and a long-term profile are separate records.
The trace reports whether the memory update completed.

## Common setup failures

| Result | Next action |
|---|---|
| Docker server is absent | Start Docker Desktop. Wait for its engine. |
| `docker` is unavailable after installation | Open a new PowerShell window. Confirm the Docker installation directory is on `PATH`. |
| WSL installation needs elevation | Use an administrator PowerShell window for WSL installation. |
| PostgreSQL connection fails | Check container health with `docker compose --env-file .env -f ops/compose.yaml ps`. |
| OpenAI key is missing | Enter the key locally in `.env` or the environment. |
| OpenAI rejects a model or account | Check account access for the configured model. Preserve the PRD model until a change is approved. |
| Tests report `BLOCKED` | Resolve the named prerequisite. A blocked test does not count as a pass. |

## Review limits

Commands were checked against official Microsoft, Docker, LangGraph, and OpenAI documentation.
Docker execution, PostgreSQL connections, and live OpenAI calls were verified on this machine.
An administrator performs WSL installation when the machine requires it.
Language and technical meaning were reviewed.
Full ASD-STE100 dictionary review remains incomplete.
