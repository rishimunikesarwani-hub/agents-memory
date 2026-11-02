# Persistent Memory - Four-Demo Test Plan

**Date:** 2026-10-31  
**Status:** Planned. No implementation or tests have run.  
**PRD:** [Persistent Memory Learning System](spec-persistent-memory-prd.md)  
**Architecture:** One parent graph and one billing worker graph.  
**Storage:** Local PostgreSQL with `pgvector`, running in Docker with a persistent volume.  
**Provider:** OpenAI directly for chat, memory extraction, summarization, and embeddings.

## 1. Implementation gates

```text
Demo 1: Save and retrieve memory
                |
           Tests pass
                v
Demo 2: Restore memory after process restart
                |
      All earlier tests pass
                v
Demo 3: Correct, remove, and manage memory
                |
      All earlier tests pass
                v
Demo 4: Prove parent-worker state boundaries
                |
      Complete regression passes
```

For each feature, use this sequence:

1. Write the acceptance test.
2. Observe its failure before implementation.
3. Implement only that feature.
4. Run its tests and all earlier tests.
5. Save the evidence before advancing.

Do not implement the next demo until the current gate passes. Printed answers alone do not establish a pass.

Run OpenAI configuration tests before live calls. Run OpenAI failure and secret-handling tests when their application paths exist.

## 2. Setup, fixtures, and evidence

### Setup

- Start PostgreSQL with `pgvector` in Docker. Preserve database files in a persistent volume.
- Create local database credentials. No PostgreSQL or `pgvector` cloud account is required.
- Supply `OPENAI_API_KEY` through the local environment or an excluded `.env` file.
- Use `gpt-4o-mini` for chat and memory extraction.
- Use `text-embedding-3-small` with 1,536 dimensions. Match the database vector configuration to that output.
- Use a separate test namespace for each run. Keep unrelated user data outside the test scope.
- Record configuration and source versions without recording secrets.

Database installation and application setup remain prerequisites. This plan does not establish that either prerequisite is complete.

### Fixtures

| Fixture | Value or purpose |
|---|---|
| Primary user | One trusted organization/user identity for positive tests. |
| Other identities | Another user in the same organization and a user in another organization. |
| Threads | One continuing thread and one new thread. |
| Original preferences | Dark mode and US English. |
| Correction | Change appearance to light mode while retaining US English. |
| Billing sequence | `I was charged twice.` Then `I'm on the Pro plan.` Then `I want a refund.` |
| Episode | A seeded billing task and recorded outcome. This is test data, not evidence of a real refund. |
| Procedures | Structured style, workflow, safety, and task-policy fields. |

Use explicit every-turn extraction for the preference demonstrations. Display that setting. Test the normal five-message interval separately.

Use the deterministic billing worker for exact message-count assertions. Count messages before the current worker reply is added.

### Evidence contract

Record each test's ID, inputs, expected result, actual result, configuration, and final status.

Include relevant message IDs, checkpoint identifiers, worker namespaces, fact IDs, and retrieved memory IDs. Record process identifiers for restart tests.

Classify results as `PASS`, `FAIL`, `NOT_RUN`, or `BLOCKED`. An unavailable prerequisite cannot produce a pass.

Keep these verification layers distinct:

| Layer | Evidence required |
|---|---|
| Deterministic tests | Exact assertions on state, validation, scheduling, and update application. Model proposals can use controlled fixtures. |
| Database integration | Independent database reads, saved-state comparisons, vector retrieval, and restart checks. |
| Live OpenAI checks | Actual extraction, structured output, embeddings, correction, summarization, and relevant recall. Record the model and supplied context. |

Successful deterministic fixtures do not establish that a live model call succeeded. Keep model answers separate from evidence that memory was stored or restored.

## 3. Demo 1 - Does memory get saved?

**Story:** The user states a preference for dark mode and US English. The application saves and retrieves that information.

**Proof:** Conversation checkpoints and long-term memory are different records. Both must be observable.

| Test ID | Action | Pass criterion |
|---|---|---|
| D1-01 | Start with a unique, empty test identity. | No earlier conversation or profile records exist. |
| D1-02 | Submit the preference message. | Parent state contains the message with its original ID and content. |
| D1-03 | Inspect the saved checkpoint through an independent database connection. | The committed checkpoint is readable outside the application connection. |
| D1-04 | Inspect the structured profile. | Active facts contain dark mode and US English with identifiers and provenance. |
| D1-05 | Inspect semantic search records. | Searchable copies reference the corresponding authoritative fact IDs. |
| D1-06 | Ask which appearance the user prefers. | Vector search retrieves the relevant preference within six results. |
| D1-07 | Open a new thread for the same user. | Its transcript starts empty. Authorized long-term preferences remain retrievable. |
| D1-08 | Retrieve memory as another user or organization. | Private preferences are absent from retrieval and prompt context. |
| D1-09 | Resubmit the same message ID and fact. | Neither the message nor the authoritative fact is duplicated. |
| D1-10 | Submit configured secret patterns and oversized memory content. | Invalid content does not enter the profile or search records. |
| D1-11 | Store and retrieve a seeded task/outcome episode. | The expected record is retrievable only within its authorized scope. |
| D1-12 | Save structured procedures and update one field. | The changed field is saved. Omitted fields retain their earlier values. |

**On-screen evidence:** Input, committed checkpoint, authoritative profile, search copies, and similarity-search result.

**Gate:** All Demo 1 assertions pass. An assistant statement that it remembered information is insufficient evidence.

## 4. Demo 2 - Does memory survive a restart?

**Story:** Close the application completely. Start another process and continue with the same database.

**Proof:** Restored information comes from durable storage rather than surviving application objects or Python variables.

| Test ID | Action | Pass criterion |
|---|---|---|
| D2-01 | Save the Demo 1 fixture and terminate its process. | The original process exits before verification begins. |
| D2-02 | Start a new process with the same database and thread. | Parent messages restore with matching IDs and content. |
| D2-03 | Load the user's long-term memory. | Profile facts, episodes, procedures, and searchable records remain available. |
| D2-04 | Repeat the similarity query. | Persisted vector records support retrieval after restart. |
| D2-05 | Send another message. | Earlier state remains and the new message is added once. |
| D2-06 | Use a new thread after restart. | The earlier transcript is absent. Authorized long-term memory remains available. |
| D2-07 | Repeat with `InMemorySaver` and `InMemoryStore`. | Those records disappear after process exit. This is the negative control. |
| D2-08 | Make the database unavailable during a save attempt. | The application reports failure and does not claim successful persistence. |
| D2-09 | Restore an encrypted checkpoint with correct and incorrect keys. | Correct-key restoration succeeds. Wrong-key restoration fails. Stored checkpoint content is not readable as plaintext. |

**On-screen evidence:** Process A saves, Process A exits, and Process B restores matching records.

**Gate:** Restore checks run in a separate process. Recreating objects inside the original process does not satisfy the restart test.

Keep the PostgreSQL volume during restart verification. Recheck the worker's restart behavior after implementing Demo 4.

## 5. Demo 3 - Can memory change correctly?

**Story:** Change the appearance preference to light mode. Keep US English.

**Proof:** Updates correct current knowledge without deleting unrelated information or leaving stale search results.

| Test ID | Action | Pass criterion |
|---|---|---|
| D3-01 | Correct dark mode to light mode. | Light mode becomes active. The authoritative profile removes or supersedes dark mode. |
| D3-02 | Inspect the language preference. | US English remains active, although both facts belong to the preference category. |
| D3-03 | Search for the appearance preference. | Normal retrieval returns the current preference without presenting dark mode as current. |
| D3-04 | Inspect conversation history. | Historical messages remain distinguishable from current profile facts. |
| D3-05 | Repeat the correction. | No duplicate active light-mode fact appears. |
| D3-06 | Add unrelated information. | Existing preferences remain unchanged. |
| D3-07 | Delete the appearance preference and synchronize again. | It disappears from the profile and search copies. Synchronization does not restore it. |
| D3-08 | Test confidence below `0.7`, from `0.7` to below `0.82`, and at least `0.82`. | Discard, proposed, and confirmed behavior matches these boundaries. Ordinary retrieval excludes proposed facts. |
| D3-09 | Return malformed extraction output or simulate extraction failure. | Existing memory remains unchanged. The successful-sync counter does not advance. |
| D3-10 | Attempt shared-policy writes as non-admin and admin. | Non-admin writes fail at every entry point. Authorized policy remains organization-scoped. |
| D3-11 | Test interval, farewell, combined, and every-turn strategies. | Calls occur only when the selected strategy and eligibility conditions permit them. |
| D3-12 | Summarize history and compact search records. | Seeded decisions remain recoverable. Compaction does not replace or corrupt authoritative profile facts. |
| D3-13 | Exceed the profile context budget. | Injected profile text stays within 2,400 tokens and favors relevant facts. |
| D3-14 | Restart after correction and deletion. | The corrected state remains durable, including the deletion. |

For D3-11, assert that interval mode skips extraction on eligible human turns one through four and runs it on turn five.

Count only qualifying human messages for scheduling. Recheck scheduling after conversation summarization changes the active message list.

**On-screen evidence:** Before profile, proposed update, applied change, search results, and restart verification.

**Gate:** Current knowledge is correct. Unrelated facts remain. Retrieval reflects the change. Corrections and deletions survive restart.

## 6. Demo 4 - Parent-worker persistent state

**Story:** Send the billing sequence one message at a time. Inspect what the parent supplies and what the worker restores.

**Proof:** The worker receives explicit input and restores its own history. A thread ID does not automatically transfer the parent's transcript.

Use a controlled comparison fixture for latest-message-only worker calls. The late-entry tests separately verify the parent's explicit briefing behavior.

| Test ID | Action | Pass criterion |
|---|---|---|
| D4-01 | Run all three parent turns. | The worker invocation trace shows one call per turn. |
| D4-02 | Inspect each worker input payload in the comparison fixture. | Each call supplies only its new human message. |
| D4-03 | Inspect per-thread worker state before each reply. | Counts are `1 -> 3 -> 5`. Turn three identifies duplicate charge, Pro plan, and refund. |
| D4-04 | Run identical inputs in per-invocation and stateless modes. | Each call starts with one message. Turn three identifies only refund. |
| D4-05 | Compare parent and worker checkpoints. | Their state records and checkpoint namespaces are distinct. |
| D4-06 | First call the worker on turn three without a briefing. | It cannot identify the duplicate charge or Pro plan. |
| D4-07 | Repeat with explicit earlier context from the parent. | The first worker call can identify all three details. |
| D4-08 | Deliver that context again with the same message IDs. | Messages are not duplicated. |
| D4-09 | Start another thread or worker namespace. | The earlier worker transcript is absent. |
| D4-10 | Restart after turn two and then submit turn three. | Both parent and worker restore their histories and continue correctly. |
| D4-11 | Inspect the parent's delegation tracking after restoration. | Previously delivered messages are not sent again unnecessarily. |
| D4-12 | Branch from an earlier checkpoint and continue. | Original history remains accessible. Long-term memory does not silently roll back. |

Run isolation tests with additional worker instances only as test fixtures. The application still has one parent and one billing worker.

**On-screen evidence:** Parent input, worker input payload, restored worker state, and findings across all three modes.

**Gate:** Tests distinguish worker restoration from parent-supplied history. A correct final answer alone does not establish the mechanism.

## 7. OpenAI-specific acceptance checks

These checks apply across the four demos. Keep the reference notebooks unchanged. Remove OpenRouter dependencies from the adapted application.

| Test ID | Action | Pass criterion |
|---|---|---|
| OA-01 | Start without `OPENAI_API_KEY`. | A clear configuration error identifies the missing variable without exposing secrets. |
| OA-02 | Inspect client configuration and captured request destinations. | Requests target the official OpenAI endpoint. |
| OA-03 | Inspect active application configuration. | No active client requires OpenRouter keys, URLs, headers, or `openai/` model-name prefixes. |
| OA-04 | Run structured assistant and memory-extraction calls. | Outputs satisfy the required application schemas. |
| OA-05 | Request an embedding through OpenAI. | `text-embedding-3-small` returns 1,536 dimensions for the configured request. |
| OA-06 | Compare embedding output and index configuration, including a mismatch fixture. | Matching dimensions permit storage and retrieval. A mismatch produces a clear failure. |
| OA-07 | Simulate an API failure in a memory update. | Existing memory remains intact. The application does not report a successful save. |
| OA-08 | Inspect logs, checkpoint payloads, versioned examples, and test evidence using a synthetic key marker. | The marker is absent. Real keys remain outside version control and test evidence. |

Record unavailable live OpenAI checks as incomplete. Deterministic substitutes cannot establish live OpenAI compatibility.

## 8. PRD coverage and repository comparison

| Existing PRD stage | Feature | Detailed coverage |
|---|---|---|
| 1 | No-memory baseline | D2-07, D4-04, D4-06 |
| 2 | Parent history | D1-02, D1-09, D2-02 |
| 3 | Persistent worker | D4-01 through D4-03 |
| 4 | Topology comparison | D4-04 |
| 5 | Late worker entry | D4-06 through D4-08 |
| 6 | Isolation | D1-08, D3-10, D4-05, D4-09 |
| 7 | Restart durability | D2-01 through D2-07, D4-10 |
| 8 | Structured updates | D1-09, D3-01, D3-02, D3-05, D3-06 |
| 9 | Validation and quarantine | D1-10, D3-08 |
| 10 | Vector retrieval | D1-05, D1-06, D2-04, OA-05, OA-06 |
| 11 | Episodes and procedures | D1-11, D1-12, D2-03 |
| 12 | Shared policy | D3-10 |
| 13 | Scheduling and failure | D3-09, D3-11, OA-07 |
| 14 | Context budget | D3-13 |
| 15 | Memory controls | D1-04, D1-05, D3-03, D3-07, D3-14 |
| 16 | Summary and compaction | D3-11, D3-12 |
| 17 | Branch and replay | D4-12 |
| 18 | Checkpoint encryption | D2-09 |

Use the three Chapter 10 notebook references listed in the PRD. Pin the repository commit before implementation.

Map each test to its source notebook and cell. Record intentional differences as **reused**, **adapted**, **new**, or **source gap**.

Convert source bugs into regression cases. Do not treat faulty source behavior as the acceptance target.

## 9. Final acceptance

- Require all four demo gates to pass.
- Require the cumulative regression suite and all OpenAI acceptance checks to pass.
- Keep deterministic results, database evidence, and live-model results distinguishable.
- Record unavailable prerequisites and unexplained skips as incomplete acceptance.
- Preserve original reference notebooks and unrelated practice code.
- Store actual execution evidence separately during implementation.

This document contains 55 planned test cases: 12 for Demo 1, 9 for Demo 2, 14 for Demo 3, 12 for Demo 4, and 8 for OpenAI.

All cases currently have status `NOT_RUN`. No database installation, application implementation, or live API call occurred while saving this plan.

**Language review:** Concise technical language and meaning reviewed. Full ASD-STE100 dictionary review is incomplete.
