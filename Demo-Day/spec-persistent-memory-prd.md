# Persistent Memory Learning System

**Document:** Product requirements document (PRD) and acceptance baseline  
**Date:** 2026-10-31  
**Status:** Documentation only. Implementation and tests have not started.  
**Target:** One local parent graph and one persistent billing worker graph.

## Page 1 - PRD and architecture

### Problem and objective

A customer explains one billing problem across several messages. A worker needs earlier context to connect a duplicate charge, plan tier, and refund request.

Build the system one feature at a time. Demonstrate what each component remembers, how it receives context, and whether its memory survives a restart.

Success means that Rishi can explain each memory boundary and verify it through an observable test.

### Architecture and data flow

The parent retains the conversation and coordinates the billing worker. It supplies relevant earlier messages when the worker joins the conversation.

A returning worker restores its own conversation state. Selected information becomes long-term memory after validation and application of a structured update.

```text
Customer message + trusted identity + thread ID
                      |
                      v
          Parent retains the conversation
                      |
          Prepare billing worker context
             /                    \
    First worker call       Returning worker
    Relevant history        Unseen messages
             \                    /
                      v
         Worker restores its own state
                      |
         Retrieve relevant long-term memory
                      |
             Answer and save checkpoint
                      |
          Is a long-term update due?
               /              \
              No              Yes
              |                |
             End       Propose structured update
                               |
                        Validate and apply
                               |
                   Save profile and search copies
```

### Required behavior

| Component | Requirement |
|---|---|
| Parent | Retain messages and track which messages the billing worker has received. Parent coordination uses application code. |
| Worker | Maintain its own message history. Default to per-thread persistence. Keep per-invocation and stateless modes for comparison. |
| Context transfer | Supply relevant earlier messages on first delegation. Subsequently supply only unseen messages. Preserve original message IDs. |
| Identity | Obtain organization, user, thread, and worker identifiers from trusted application context. Model output cannot grant access. |
| Checkpoints | Save parent and worker state separately. Use `InMemorySaver` for the baseline and `PostgresSaver` for restart durability. |
| Long-term memory | Use `PostgresStore` for profiles, facts, task outcomes, and procedural instructions. Keep the structured profile authoritative. |
| Similarity search | Use the `pgvector` extension in PostgreSQL. Store embeddings for searchable memory records. No separate vector database is required. |
| Updates | Separate model proposals from validation and application. Replace conflicting facts without deleting unrelated facts. |
| Retrieval | Enforce user and organization scope. Rank relevant memories. Exclude proposed facts from ordinary retrieval. |
| Controls | Support inspection, correction, deletion, summarization, compaction, checkpoint history, branching, and checkpoint encryption. |

**Input:** Trusted identity, thread ID, message ID, text, and worker mode.

**Output:** Answer and an inspection trace. The trace identifies supplied messages, restored messages, retrieved memory IDs, and memory-update status.

### Defaults and boundaries

- Use one local PostgreSQL database with `pgvector`. Keep checkpoint records and long-term records logically separate.
- Keep database connections active while the application runs. Database setup is a prerequisite, not an assumed completed step.
- Run one application process. Additional worker instances appear only in isolation tests.
- Run structured memory extraction after five new human messages by default. Also support farewell, combined, and every-turn strategies.
- Limit structured profile injection to 2,400 tokens by default.
- Use `gpt-4o-mini` for chat and memory extraction through OpenAI directly.
- Use `text-embedding-3-small` with 1,536 embedding dimensions. Match the database index dimensions to the embedding output.
- Exclude deployment, concurrent execution, browser UI, and actual refund operations.
- Preserve the source notebooks and existing practice code.

**OpenAI API note:** Read `OPENAI_API_KEY` from the local environment or an excluded `.env` file. Use the official OpenAI endpoint without OpenRouter settings. Never save the key in code, checkpoints, logs, or test evidence.

### Source boundary and terms

Use these three Chapter 10 notebooks as references. Other chapters are outside this build.

| Reference | Notebook |
|---|---|
| N: memory baseline | [Memory versus no memory](https://github.com/Nicolepcx/ai-agents-the-definitive-guide/blob/main/ch10/ch10_memory_no_memory.ipynb) |
| T: worker topology | [Memory topologies](https://github.com/Nicolepcx/ai-agents-the-definitive-guide/blob/main/ch10/ch10_memory_topologies.ipynb) |
| M: complete memory example | [Agent memory with LangGraph](https://github.com/Nicolepcx/ai-agents-the-definitive-guide/blob/main/ch10/ch10_agent_memory_langgraph.ipynb) |

| Term | Meaning in this document |
|---|---|
| Checkpoint | Saved graph state used to restore one conversation. |
| Thread ID | Application identifier for a conversation. It does not transfer messages between graphs. |
| Long-term memory | Selected information stored outside conversation state for later use across threads. |
| Embedding | Numerical representation of text used for similarity search. |
| Search projection | Searchable copy of an authoritative profile fact. |
| Semantic, episodic, procedural | Facts, task/outcome records, and instructions, respectively. |
| Proposed fact | Stored candidate information excluded from ordinary retrieval until confirmed. |

## Page 2 - Incremental tests and pass criteria

The detailed four-demo test plan is [eval-persistent-memory-test-plan.md](eval-persistent-memory-test-plan.md). Its demo gates organize the feature stages below.

### Build rule

For each stage, write the test first. Observe the missing behavior. Add the feature. Run that test and all earlier tests.

Proceed only when the required tests pass. Use assertions rather than printed output as acceptance evidence.

| Stage | Feature added | Required pass criterion |
|---|---|---|
| 1 | No-memory baseline | Independent calls cannot recover facts absent from their current inputs. |
| 2 | Parent history | Three turns retain three ordered human messages. Repeated message IDs do not create duplicates. |
| 3 | Persistent worker | The deterministic billing example produces counts `1 -> 3 -> 5`. Turn three identifies duplicate charge, Pro plan, and refund. |
| 4 | Topology comparison | On turn three, fresh modes identify only refund. Per-thread mode identifies all three details. |
| 5 | Late worker entry | First call the worker on turn three. Earlier details remain unknown without a briefing and become available with the briefing. |
| 6 | Isolation | Separate threads, users, organizations, and worker namespaces do not expose private records to each other. |
| 7 | Restart durability | After process exit, new application objects restore saved parent state, worker state, and seeded long-term records. |
| 8 | Structured updates | A light-mode correction replaces dark mode while preserving an unrelated language preference. Exact duplicates are rejected. |
| 9 | Validation and quarantine | Reject invalid content. Discard confidence below `0.7`. Keep confidence from `0.7` to below `0.82` proposed and excluded from ordinary retrieval. |
| 10 | Vector retrieval | A billing query retrieves the relevant seeded fact within six results. Identical text under different keys remains separately addressable. |
| 11 | Episodes and procedures | Retrieve a relevant task/outcome. Partial instruction updates preserve omitted fields. Stored outcomes do not establish that an actual refund occurred. |
| 12 | Shared policy | Admin writes succeed. Non-admin writes fail at every application entry point. Shared policy remains limited to its organization. |
| 13 | Scheduling and failure | Interval mode runs extraction after turn five. Other strategies match their conditions. Failed extraction preserves memory and the success counter. |
| 14 | Context budget | Structured profile injection remains within its configured token limit. Ranking favors relevant billing facts over unrelated facts. |
| 15 | Memory controls | Inspection matches stored records. Corrections and deletions update authoritative records and search copies. Synchronization does not restore deleted facts. |
| 16 | Summary and compaction | Preserve seeded decisions and preferences. Remove duplicates without changing authoritative facts or user isolation. |
| 17 | Branch and replay | Preserve original history when branching. Demonstrate that replay does not roll back the long-term store. |
| 18 | Checkpoint encryption | Correct-key restoration succeeds. Wrong-key restoration fails. Stored checkpoint content is not readable as plaintext. |

### Source comparison and verification

Record the repository commit, notebook cell, requirement, test ID, and observed result for each stage.

Classify behavior as **reused**, **adapted**, **new**, or **source gap**. Record intentional differences from the notebooks. Convert source bugs into regression cases.

Use deterministic fixtures for state, storage, validation, and scheduling tests. Report live-model checks separately for extraction, contradictions, summarization, and relevant recall.

### Completion gate

All mandatory assertions must pass. There must be no unexplained skipped tests. Restart and isolation tests are mandatory.

Store actual test evidence separately during implementation. This document records planned criteria, not completed verification.

**Language review:** Concise technical language and meaning reviewed. Full ASD-STE100 dictionary review is incomplete.
