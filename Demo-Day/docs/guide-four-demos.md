# Run the four memory demonstrations

Complete the [local setup](guide-local-setup.md) first.
Run these commands from the project folder.
The demonstrations call OpenAI and use API credits.

## Demo 1: Save memory

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops/run-demo.ps1 -Stage 1
```

The script creates a new user identifier.
It saves a preference for dark mode and US English.
The output shows the stored profile facts and their identifiers.
The local session identifiers are saved in `runs/demo-session.json`.
That file contains no API key.

## Demo 2: Restore after application exit

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops/run-demo.ps1 -Stage 2
```

The Stage 1 application process has already exited.
New processes inspect the saved parent state, worker state, and profile.
The separate-process tests also record process and checkpoint identifiers.
Keep the Docker data volume during this demonstration.

## Demo 3: Change memory

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops/run-demo.ps1 -Stage 3
```

The user changes the appearance preference to light mode.
The application removes the outdated fact and preserves US English.
The profile output shows the current facts.

## Demo 4: Compare worker persistence

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops/run-demo.ps1 -Stage 4 -Mode per_thread
powershell -NoProfile -ExecutionPolicy Bypass -File ops/run-demo.ps1 -Stage 4 -Mode per_invocation
powershell -NoProfile -ExecutionPolicy Bypass -File ops/run-demo.ps1 -Stage 4 -Mode stateless
```

Each comparison supplies only the latest human message.
Each mode uses a separate user scope.
The worker reports the message count before adding its current reply.

| Mode | Counts across three turns | Third-turn findings |
|---|---|---|
| `per_thread` | `1, 3, 5` | Duplicate charge, Pro plan, and refund request. |
| `per_invocation` | `1, 1, 1` | Refund request only. |
| `stateless` | `1, 1, 1` | Refund request only. |

The findings use the notebook's deterministic phrase checks.
The actual assistant answer comes from OpenAI.
No command performs a refund.

Run Stage 1 again when you need a new demonstration session.
Repeating a stage with the same message identifiers does not duplicate those messages.

## Normal conversation

```powershell
.venv\Scripts\user-memory.exe chat --org demo-org --user alex --thread billing
```

The default worker retains its own history.
The parent supplies relevant history on first delegation.
It supplies only unseen messages on later delegations.
Use a different `--thread` value to open another conversation.
The same user can still retrieve authorized long-term preferences.

The ordinary extraction strategy runs after five qualifying human messages.
The demonstration script explicitly selects `every_turn`.
The worker comparison selects interval `1000` to isolate conversation restoration from long-term updates.

## Inspect and manage records

```powershell
.venv\Scripts\user-memory.exe inspect --org demo-org --user alex --thread billing
.venv\Scripts\user-memory.exe inspect --worker --org demo-org --user alex --thread billing
.venv\Scripts\user-memory.exe profile --org demo-org --user alex
.venv\Scripts\user-memory.exe list --org demo-org --user alex
.venv\Scripts\user-memory.exe history --org demo-org --user alex --thread billing
.venv\Scripts\user-memory.exe procedure --org demo-org --user alex --style "Use short paragraphs."
```

Use `correct FACT_ID "Replacement fact"` to replace one fact.
Use `delete FACT_ID` to remove a profile fact and its search copy.
These commands preserve conversation checkpoints.
Use `delete EPISODE_KEY --kind episodic` to delete an episode without changing semantic facts.
Use `episode "Task" "Outcome" --key EPISODE_KEY` to update a recorded episode.
Use `compact` to remove redundant profile search copies.
Use `summarize` to replace the parent's active transcript with a historical summary.

Use `policy "Policy text" --admin` for an organization-wide rule.
The local administrator flag is trusted operator input.
Model output cannot grant this permission.
This local application does not provide network authentication.

Use `fork CHECKPOINT_ID "New message"` to branch from a saved parent checkpoint.
Use `replay CHECKPOINT_ID` to resume from that point.
Supply the same organization, user, and thread flags for these operations.
Original checkpoints remain available.
Replay can execute model calls and memory writes again.
It does not restore an earlier long-term profile.

Concise technical language and meaning were reviewed.
Full ASD-STE100 dictionary review remains incomplete.
