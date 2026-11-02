# Memory policy experiment

The user approved a local experiment on 2026-10-26. This is not a production agent deployment.

## Outcome

Explain and test a memory policy derived from both local agent books.
Show saved state, selected context, decision reasons, and agent actions before and after the policy.
Use five independent workflows and histories through run 200.
Separate deterministic enforcement tests from observed language-model outcomes.

## Shared implementation contract

Root owns the fixture generator, experiment runner, model adapter, visual demo, and final integration.
The engine agent owns `src/memory_policy.py` and engine unit tests.
The evaluation agent owns `evals/evaluate_policy.py` and independent adversarial tests.
The source agent owns `docs/spec-memory-policy.md` and `docs/arch-memory-policy.mmd`.
Agents must not edit another owner's files without agreement.

The engine uses Python and SQLite. It must not require a model to enforce access or write decisions.

### Memory record

A candidate is a dictionary with these fields:

```json
{
  "id": "a-preference-1",
  "user_id": "user-a",
  "workflow": "workflow-a",
  "kind": "preference",
  "key": "report_currency",
  "value": "Use INR for the revenue report.",
  "source": "user",
  "observed_at": 1,
  "expires_at": null,
  "pinned": true,
  "evidence_ids": [],
  "validated": true
}
```

Kinds: `fact`, `preference`, `episode`, `procedure`, `lesson`.
Sources: `user`, `verified_tool`, `admin`, `untrusted_document`, `reflection`.
Time uses integer logical days. The request runs at an explicit `now` value.
The workflow `shared` permits records across this user's workflows.
The user `*` permits organization-wide records only when an administrator writes them.
The synthetic principal has `user_id` and `role` fields. This is a trusted runtime input in this experiment.
There is no login implementation. A production adapter must authenticate these fields.
The runtime sets source and validation metadata. A model cannot grant itself those permissions.

### Engine API

```python
store = MemoryStore(path)
decision = store.ingest(candidate, principal)
records = store.records()  # every record, including status and decision metadata
events = store.events()    # write decisions, with rejected secret content redacted
checkpoint = store.save_checkpoint(thread_id, state, principal)
state = store.load_checkpoint(thread_id, principal)
selection = store.select(
    query=query, principal=principal, workflow=workflow, now=now,
    token_limit=token_limit, render=render_prompt, count=count_tokens,
    required_keys=None,
)
store.close()
```

`render(query, selected_records)` returns the complete serialized model prompt, including fixed instructions.
`count(text)` estimates tokens with the configured local tokenizer.
Live generation uses an exact server count as an additional input-budget check.
`token_limit` is the input limit after reserving output capacity and a safety margin.
The default selector uses lexical relevance. It must disclose this limitation.
Required keys are exact application dependencies. They cannot bypass authorization or validity checks.
Required keys that are missing cause `insufficient_evidence`. Required records that exceed the budget cause `blocked_budget`.
Pinned records are applicable preferences and procedures. They must not silently disappear to fit the budget.
Other memory kinds cannot become pinned merely through a candidate flag.

The selection dictionary includes `status`, `selected`, `excluded`, `prompt`, `token_count`, and `token_limit`.
Each excluded row includes the record ID and reason. Selection must not mutate or delete saved records.
Write decisions include `status`, `reason`, and `id`.
Record statuses include `active`, `superseded`, and `quarantined`.

### Required behavior

1. Validate a candidate before it replaces an accepted record.
2. Commit replacement and audit evidence in one transaction.
3. Deduplicate matching active values within the same user, workflow, kind, and key.
4. Keep different users and workflows isolated. Permit explicit shared records.
5. Never promote untrusted documents into accepted instructions or facts.
6. Admit reflection lessons only with trusted validation and evidence references.
7. Reject blank or oversized values and known synthetic secret patterns.
8. Reject stale replacements. Quarantine conflicting updates with equal timestamps.
9. Exclude expired, future-dated, superseded, and quarantined records from context.
10. Include applicable pinned records before ranked optional records.
11. Enforce the complete serialized input budget. Block if required content cannot fit.
12. Store checkpoints separately. Reload must work in a fresh process.
13. Checkpoint recovery uses current durable memory. It does not rewind that store.
14. Preserve source IDs and authority when summarizing or consolidating records.
15. Do not grant tools new permissions through memory or reflection.

## Evaluation contract

Compare full replay, last-four messages, budgeted recency, accumulated top-k history, and the proposed policy.
Use identical event histories and task requirements for each comparison.
Record runs 1, 10, 100, and 200 across five workflows.
Report context size, required-fact recall, stale recall, scope leaks, duplicate count, and task outcomes separately.
Keep deliberately failing baselines visible. Do not report them as policy implementation failures.
Run independent adversarial tests and a fresh-process persistence test.
Check whether a disabled policy gate makes its corresponding test fail.

Use the OpenAI Responses API for the paired behavioral evaluation when an API key is configured.
Use `gpt-5.4-mini-2026-03-17` by default. OPENAI_MODEL can select another compatible model.
Keep memory selection and persistence in Python and SQLite.
Use local token estimates for offline replay.
Get the exact input count from OpenAI before generation. Block requests that exceed the input allowance.
Do not use server conversation history or automatic truncation.
Set `store=False` on generation requests.
Run two repetitions for each workflow and method. Do not send an unsupported seed parameter.
Save OpenAI observations in `runs/model-trials-openai.json`.
Keep historical Qwen observations in their original files and the preserved baseline folder.
Pin model identity and generation settings. Record prompts, responses, token counts, and elapsed time.
Do not silently truncate over-budget baseline prompts. Record those runs as blocked before inference.
The deterministic agent chooses an action from selected evidence and executes only local simulated tools.
Label deterministic and model outcomes separately in the demo.

## Hybrid retrieval contract

Filter records by access, validity, and scope before sending text for embedding.
Select required keys and applicable pins through direct lookup.
Rank the remaining records with keyword overlap and embedding cosine similarity.
Combine their positions through reciprocal rank fusion before packing the context.

Use `text-embedding-3-small` with 512 dimensions for configured OpenAI requests.
Keep vectors in a namespaced SQLite cache. Include the complete key and value in each content hash.
Use cached vectors during offline replay. Report `lexical_fallback` when the required cache entries are missing.
Stop on embedding API errors during an authorized cache update.

Use hand-authored vectors to test retrieval mechanics without API calls.
Label this evidence as fixture behavior, not live embedding quality.
Keep the lexical-only paraphrase limitation test as a baseline.

## Review checkpoints

Reconsider the workflow after approximately five minutes and report the result to the user.
Review source fidelity, test fairness, and the visible demo before completion.
The final audit must map every user requirement to current files and executed evidence.
