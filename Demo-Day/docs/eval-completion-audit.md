# Completion audit

The local memory application passed all four demonstration gates.
All 55 planned acceptance cases have passing evidence.
The complete result includes all eight OpenAI criteria.

## Executed verification

| Verification layer | Passed checks | Skipped checks | Evidence |
|---|---|---|---|
| Controlled memory backend | 77 | 12 | [Memory report](../runs/demo1-memory.json) |
| PostgreSQL and pgvector | 89 | 0 | [Database report](../runs/demo1-postgres.json) |
| Live OpenAI | 5 | 0 | [Live report](../runs/demo1-live.json) |

The controlled run omits 12 database-specific checks.
The PostgreSQL run executes those checks successfully.
The 55 acceptance cases map to multiple regression checks.
These counts describe different verification layers.

Build fingerprint: `aeaaca5f00e24886f7536d03eb54a23d57158ba57dc9e6d3048954f9056e75b8`.

The [acceptance ledger](../runs/acceptance-summary.json) records expected criteria, observed state, test identifiers, and source references.
The [final gate receipt](../runs/demo4-gate-passed-summary.json) preserves this result.

## Required behavior

| Case | Behavior checked | Result | Assertion evidence | Source cells |
|---|---|---|---|---|
| D1-01 | Start with a unique, empty test identity. | PASS | [test_d1_01_new_identity_empty](../tests/test_demo1.py) | M: 7, 29 |
| D1-02 | Submit the preference message. | PASS | [test_d1_02_message_saved_with_id](../tests/test_demo1.py) | M: 29 |
| D1-03 | Inspect the saved checkpoint through an independent database connection. | PASS | [test_d1_03_checkpoint_committed_outside_app_connection](../tests/test_postgres_demo1.py) | M: 26, 29 |
| D1-04 | Inspect the structured profile. | PASS | [test_d1_04_profile_has_provenance](../tests/test_demo1.py) | M: 8, 9 |
| D1-05 | Inspect semantic search records. | PASS | [test_d1_05_projection_references_authoritative_ids](../tests/test_demo1.py) | M: 9, 10 |
| D1-06 | Ask which appearance the user prefers. | PASS | [test_d1_06_vector_search](../tests/test_demo1.py) | M: 12 |
| D1-07 | Open a new thread for the same user. | PASS | [test_d1_07_new_thread_empty_but_long_term_available](../tests/test_demo1.py) | M: 7, 29 |
| D1-08 | Retrieve memory as another user or organization. | PASS | [test_d1_08_scope_in_search_and_prompt[user]](../tests/test_demo1.py) | M: 7, 29 |
| D1-09 | Resubmit the same message ID and fact. | PASS | [test_d1_09_message_and_fact_idempotence](../tests/test_demo1.py) | M: 9, 29 |
| D1-10 | Submit configured secret patterns and oversized memory content. | PASS | [test_d1_10_invalid_memory_never_saved[invalid0]](../tests/test_demo1.py) | M: 6 |
| D1-11 | Store and retrieve a seeded task/outcome episode. | PASS | [test_d1_11_episode_scope](../tests/test_demo1.py) | M: 14 |
| D1-12 | Save structured procedures and update one field. | PASS | [test_d1_12_procedural_partial_update](../tests/test_demo1.py) | M: 16 |
| D2-01 | Save the Demo 1 fixture and terminate its process. | PASS | [test_d2_01_original_process_exits_before_restore](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-02 | Start a new process with the same database and thread. | PASS | [test_d2_02_parent_messages_restore_exactly](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-03 | Load the user's long-term memory. | PASS | [test_d2_03_long_term_records_restore](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-04 | Repeat the similarity query. | PASS | [test_d2_04_vector_search_after_restart](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-05 | Send another message. | PASS | [test_d2_05_new_message_appends_once](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-06 | Use a new thread after restart. | PASS | [test_d2_06_new_thread_has_only_long_term_memory](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-07 | Repeat with `InMemorySaver` and `InMemoryStore`. | PASS | [test_d2_07_in_memory_negative_control](../tests/test_demo2.py) | N: 4, 5 |
| D2-08 | Make the database unavailable during a save attempt. | PASS | [test_d2_08_database_save_failure_is_not_success](../tests/test_demo2.py) | M: 10, 26, 29 |
| D2-09 | Restore an encrypted checkpoint with correct and incorrect keys. | PASS | [test_d2_09_encrypted_restart_correct_and_wrong_keys](../tests/test_demo2.py) | M: 23 |
| D3-01 | Correct dark mode to light mode. | PASS | [test_d3_01_exact_correction](../tests/test_demo3.py) | M: 8, 9 |
| D3-02 | Inspect the language preference. | PASS | [test_d3_02_unrelated_preference_keeps_its_identity](../tests/test_demo3.py) | M: 6, 9 |
| D3-03 | Search for the appearance preference. | PASS | [test_d3_03_search_reflects_current_knowledge](../tests/test_demo3.py) | M: 9, 12 |
| D3-04 | Inspect conversation history. | PASS | [test_d3_04_old_transcript_is_historical](../tests/test_demo3.py) | M: 29, 35 |
| D3-05 | Repeat the correction. | PASS | [test_d3_05_repeat_correction_does_not_duplicate](../tests/test_demo3.py) | M: 9 |
| D3-06 | Add unrelated information. | PASS | [test_d3_06_addition_preserves_unrelated_facts](../tests/test_demo3.py) | M: 9 |
| D3-07 | Delete the appearance preference and synchronize again. | PASS | [test_d3_07_delete_canonical_and_projection_then_sync](../tests/test_demo3.py) | M: 9, 12, 29 |
| D3-08 | Test confidence below `0.7`, from `0.7` to below `0.82`, and at least `0.82`. | PASS | [test_d3_08_confidence_boundaries_and_quarantine](../tests/test_demo3.py) | M: 6, 9, 29 |
| D3-09 | Return malformed extraction output or simulate extraction failure. | PASS | [test_d3_09_and_oa_07_failed_extraction_preserves_memory[exception]](../tests/test_demo3.py) | M: 9, 29 |
| D3-10 | Attempt shared-policy writes as non-admin and admin. | PASS | [test_d3_10_cli_policy_requires_admin_before_connections](../tests/test_cli.py) | M: 6, 29, 31 |
| D3-11 | Test interval, farewell, combined, and every-turn strategies. | PASS | [test_d3_11_strategies_and_success_counters[interval-expected0]](../tests/test_demo3.py) | M: 19, 29, 31 |
| D3-12 | Summarize history and compact search records. | PASS | [test_d3_12_summary_and_compaction_preserve_decisions](../tests/test_demo3.py) | M: 12, 19 |
| D3-13 | Exceed the profile context budget. | PASS | [test_d3_13_context_budget_favors_billing[200]](../tests/test_demo3.py) | M: 7 |
| D3-14 | Restart after correction and deletion. | PASS | [test_d3_14_corrected_and_deleted_facts_restore](../tests/test_demo3.py) | M: 9, 26 |
| D4-01 | Run all three parent turns. | PASS | [test_d4_01_worker_called_once_per_turn](../tests/test_demo4.py) | T: 2 |
| D4-02 | Inspect each worker input payload in the comparison fixture. | PASS | [test_d4_02_parent_supplies_latest_only_in_comparison](../tests/test_demo4.py) | T: 2 |
| D4-03 | Inspect per-thread worker state before each reply. | PASS | [test_d4_03_per_thread_restores_earlier_messages](../tests/test_demo4.py) | T: 2 |
| D4-04 | Run identical inputs in per-invocation and stateless modes. | PASS | [test_d4_04_fresh_worker_does_not_recover_missing_history[per_invocation]](../tests/test_demo4.py) | T: 2 |
| D4-05 | Compare parent and worker checkpoints. | PASS | [test_d4_05_parent_and_worker_have_separate_checkpoints](../tests/test_demo4.py) | T: 2 |
| D4-06 | First call the worker on turn three without a briefing. | PASS | [test_d4_06_late_worker_without_briefing_cannot_know_earlier_turns](../tests/test_demo4.py) | T: 2 |
| D4-07 | Repeat with explicit earlier context from the parent. | PASS | [test_d4_07_parent_explicitly_briefs_late_worker](../tests/test_demo4.py) | T: 2 |
| D4-08 | Deliver that context again with the same message IDs. | PASS | [test_d4_08_repeated_briefing_uses_message_id_deduplication](../tests/test_demo4.py) | T: 2 |
| D4-09 | Start another thread or worker namespace. | PASS | [test_d4_09_thread_and_worker_namespace_isolation](../tests/test_demo4.py) | T: 2 |
| D4-10 | Restart after turn two and then submit turn three. | PASS | [test_d4_10_and_d4_11_parent_worker_restart_and_delivery_tracking](../tests/test_demo4.py) | T: 2 |
| D4-11 | Inspect the parent's delegation tracking after restoration. | PASS | [test_d4_10_and_d4_11_parent_worker_restart_and_delivery_tracking](../tests/test_demo4.py) | T: 2 |
| D4-12 | Branch from an earlier checkpoint and continue. | PASS | [test_d4_12_fork_and_replay_preserve_history_but_not_rollback_store](../tests/test_demo4.py) | M: 35 |
| OA-01 | Start without `OPENAI_API_KEY`. | PASS | [test_oa_01_cli_checks_missing_key_before_database](../tests/test_cli.py) | M: 5, 10, 29 |
| OA-02 | Inspect client configuration and captured request destinations. | PASS | [test_oa_02_03_official_clients](../tests/test_openai_config.py) | M: 5, 10, 29 |
| OA-03 | Inspect active application configuration. | PASS | [test_oa_02_03_official_clients](../tests/test_openai_config.py) | M: 5, 10, 29 |
| OA-04 | Run structured assistant and memory-extraction calls. | PASS | [test_oa_04_and_d1_live_extraction_and_recall](../evals/test_live_demo1.py) | M: 5, 10, 29 |
| OA-05 | Request an embedding through OpenAI. | PASS | [test_oa_05_live_embedding_dimensions](../evals/test_live_demo1.py) | M: 5, 10, 29 |
| OA-06 | Compare embedding output and index configuration, including a mismatch fixture. | PASS | [test_oa_06_dimension_mismatch](../tests/test_openai_config.py) | M: 5, 10, 29 |
| OA-07 | Simulate an API failure in a memory update. | PASS | [test_d3_09_and_oa_07_failed_extraction_preserves_memory[exception]](../tests/test_demo3.py) | M: 5, 10, 29 |
| OA-08 | Inspect logs, checkpoint payloads, versioned examples, and test evidence using a synthetic key marker. | PASS | [test_oa_02_03_08_http_destination_and_secret_boundary](../tests/test_openai_transport.py) | M: 5, 10, 29 |

N, T, and M identify the notebooks in the preserved PRD.
Cell numbers start at zero.
The ledger records each adaptation classification.

## PRD stages

| PRD stage | Feature | Acceptance coverage |
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

Every listed coverage case passed in its required verification layer.

## Process and model evidence

Separate-process restart tests record distinct process identifiers and restored checkpoint identifiers.
The live worker check closes and reopens database connections.
The presentation scripts also run each turn through a separate application process.

| Evidence | Observed result |
|---|---|
| [Persistent worker](../runs/demo-billing-per_thread-summary.json) | Message counts `1, 3, 5`. All three billing details remain available. |
| [Per-invocation worker](../runs/demo-billing-per_invocation-summary.json) | Message counts `1, 1, 1`. Only the latest request remains available. |
| [Stateless worker](../runs/demo-billing-stateless-summary.json) | Message counts `1, 1, 1`. Only the latest request remains available. |
| [Live correction and summary](../runs/live-correction-summary.json) | Light mode replaces dark mode. US English remains available. |
| [Live worker](../runs/live-worker-summary.json) | The supplied third-turn payload contains only `m3`. The worker restores `m1` and `m2`. |

Exact billing findings use the deterministic phrase checks from the topology example.
OpenAI generates the actual assistant answers.
The live reports record models and supplied context.

## Test-first evidence

| Stage | Failure evidence | Passing gate |
|---|---|---|
| Demo 1 | [Initial missing behavior](../runs/demo1-red.txt) | [Demo 1 receipt](../runs/demo1-gate-passed-summary.json) |
| Demo 2 | [Encryption and restart requirements](../runs/demo2-red.txt) | [Demo 2 receipt](../runs/demo2-gate-passed-summary.json) |
| Demo 3 | [Update and control requirements](../runs/demo3-red.txt) | [Demo 3 receipt](../runs/demo3-gate-passed-summary.json) |
| Demo 4 | [Worker state requirements](../runs/demo4-red.txt) | [Demo 4 receipt](../runs/demo4-gate-passed-summary.json) |

Later regression failures also remain in `runs/`.
Failure evidence does not establish completed behavior.
Current passing evidence controls the acceptance result.

## Source and credential checks

The source commit is `a1ff481c87cc3784c9c920c8e315b3341f57e563`.
The original PRD, test plan, and three notebooks retain their recorded hashes.
The [preservation receipt](../runs/source-preservation-audit.json) records those comparisons.
The [source comparison](ref-source-comparison.md) explains the intentional changes.

The [credential audit](../runs/secret-audit.json) found no real credentials in the checked delivery files.
The example key field remains blank.
The real key stays in the excluded local environment file.
No active client uses OpenRouter configuration.

## Operating scope

The [setup guide](guide-local-setup.md) explains Windows, Docker, and local database preparation.
The [demonstration guide](guide-four-demos.md) gives the presentation commands.
The [architecture document](arch-persistent-memory.md) links the rendered Mermaid flowchart.

This build supports one local application process.
It excludes network authentication, concurrent execution, deployment, and actual refunds.
A checkpoint encryption key encrypts checkpoint payloads.
It does not encrypt the separate long-term store.
Replay does not restore an earlier long-term profile.

## Review limits

Selected language checks and technical meaning review are complete.
The architecture glossary defines the required technical terms.
The official dictionary review remains incomplete.
This audit does not claim full ASD-STE100 compliance.
