# Source comparison

Repository commit: `a1ff481c87cc3784c9c920c8e315b3341f57e563`.

Notebook cells use zero-based indices.
The [source manifest](../data/source/source-manifest.json) records each notebook hash and source URL.
The original notebook bytes remain unchanged.
The [case map](../evals/source-map.json) links all 55 acceptance cases to notebook cells.
This map records provenance, not test completion.

## Intentional changes

| Area | Application direction |
|---|---|
| Provider | Use OpenAI directly with native model identifiers. |
| Database | Implement active PostgreSQL connection contexts instead of commented examples. |
| Parent state | Retain messages and track delivery when the worker stage opens. |
| Identity | Reject invalid identifiers instead of converting different identifiers into the same segment. |
| Fact correction | Replace exact conflicting facts. Preserve unrelated preferences. |
| Quarantine | Exclude proposed facts from ordinary retrieval. |
| Deletion | Remove canonical facts and search copies together. |
| Organization writes | Enforce administrator access at every application write entry point. |
| Scheduling | Use durable counters that survive summary changes. |
| Encryption | Decode hexadecimal key text before supplying AES key bytes. |
| Token budget | Use the configured chat model tokenizer for profile injection. |
| Compaction | Remove redundant search projections while retaining authoritative facts. |

Some directions belong to unopened stages.
The [build status](eval-build-status.md) identifies executed checks and incomplete gates.

## Acceptance provenance

| Test ID | Notebook | Cell indices | Classification |
|---|---|---|---|
| D1-01 | ch10_agent_memory_langgraph.ipynb | 7, 29 | adapted |
| D1-02 | ch10_agent_memory_langgraph.ipynb | 29 | adapted |
| D1-03 | ch10_agent_memory_langgraph.ipynb | 26, 29 | adapted |
| D1-04 | ch10_agent_memory_langgraph.ipynb | 8, 9 | adapted |
| D1-05 | ch10_agent_memory_langgraph.ipynb | 9, 10 | adapted |
| D1-06 | ch10_agent_memory_langgraph.ipynb | 12 | adapted |
| D1-07 | ch10_agent_memory_langgraph.ipynb | 7, 29 | adapted |
| D1-08 | ch10_agent_memory_langgraph.ipynb | 7, 29 | adapted |
| D1-09 | ch10_agent_memory_langgraph.ipynb | 9, 29 | adapted |
| D1-10 | ch10_agent_memory_langgraph.ipynb | 6 | adapted |
| D1-11 | ch10_agent_memory_langgraph.ipynb | 14 | adapted |
| D1-12 | ch10_agent_memory_langgraph.ipynb | 16 | adapted |
| D2-01 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-02 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-03 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-04 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-05 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-06 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-07 | ch10_memory_no_memory.ipynb | 4, 5 | adapted |
| D2-08 | ch10_agent_memory_langgraph.ipynb | 10, 26, 29 | new |
| D2-09 | ch10_agent_memory_langgraph.ipynb | 23 | source gap |
| D3-01 | ch10_agent_memory_langgraph.ipynb | 8, 9 | adapted |
| D3-02 | ch10_agent_memory_langgraph.ipynb | 6, 9 | source gap |
| D3-03 | ch10_agent_memory_langgraph.ipynb | 9, 12 | adapted |
| D3-04 | ch10_agent_memory_langgraph.ipynb | 29, 35 | adapted |
| D3-05 | ch10_agent_memory_langgraph.ipynb | 9 | adapted |
| D3-06 | ch10_agent_memory_langgraph.ipynb | 9 | adapted |
| D3-07 | ch10_agent_memory_langgraph.ipynb | 9, 12, 29 | source gap |
| D3-08 | ch10_agent_memory_langgraph.ipynb | 6, 9, 29 | source gap |
| D3-09 | ch10_agent_memory_langgraph.ipynb | 9, 29 | adapted |
| D3-10 | ch10_agent_memory_langgraph.ipynb | 6, 29, 31 | source gap |
| D3-11 | ch10_agent_memory_langgraph.ipynb | 19, 29, 31 | source gap |
| D3-12 | ch10_agent_memory_langgraph.ipynb | 12, 19 | adapted |
| D3-13 | ch10_agent_memory_langgraph.ipynb | 7 | adapted |
| D3-14 | ch10_agent_memory_langgraph.ipynb | 9, 26 | adapted |
| D4-01 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-02 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-03 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-04 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-05 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-06 | ch10_memory_topologies.ipynb | 2 | new |
| D4-07 | ch10_memory_topologies.ipynb | 2 | new |
| D4-08 | ch10_memory_topologies.ipynb | 2 | new |
| D4-09 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-10 | ch10_memory_topologies.ipynb | 2 | adapted |
| D4-11 | ch10_memory_topologies.ipynb | 2 | new |
| D4-12 | ch10_agent_memory_langgraph.ipynb | 35 | adapted |
| OA-01 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-02 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-03 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-04 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-05 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-06 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-07 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |
| OA-08 | ch10_agent_memory_langgraph.ipynb | 5, 10, 29 | adapted |

**Adapted** means the application changes the source behavior or interface.
**New** means the requirement extends the source demonstration.
**Source gap** identifies source behavior that needs a regression case.
No classification establishes that an unopened feature works.

Technical meaning was reviewed.
Full ASD-STE100 dictionary review remains incomplete.
