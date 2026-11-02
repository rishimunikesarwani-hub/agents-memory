# Memory policy lab

This local experiment shows how memory rules change an agent's saved state and request context.
It uses principles from two agent books and synthetic records from five workflows.

## Start here

Open [the interactive demo](runs/demo.html).
Read [the memory policy](docs/spec-memory-policy.md).
View [the architecture](docs/arch-memory-policy.svg).
Edit [the Mermaid source](docs/arch-memory-policy.mmd).

The demo compares runs 1, 10, 100, and 200.
Each view separates persistent storage, selected context, and the resulting action.

## Demonstrate the result

1. Select workflow A, run 200, and Budgeted recency.
2. Compare the missing customer code with the policy's retained run-1 record.
3. Select Full history replay to show context growth beyond the configured input allowance.
4. Inspect the run-99 rejected candidate and the run-120 accepted replacement.
5. Expand Compaction to inspect five cycles and their retained evidence.
6. Expand Learning to inspect the failed action, tested lesson, repaired action, and rollback.
7. Expand OpenAI model trials to inspect API observations when available.
8. Compare keyword and hybrid selection in the paraphrase test. Read its test-vector label before presenting the result.

Explain the distinction between storage and context before showing the token counts.
Historical Qwen trials showed correct requests for missing information. OpenAI requires a separate live evaluation.

## Run the experiment

Open PowerShell in this folder.
Install the dependencies once.

~~~powershell
py -m pip install "openai>=2.54,<3" "tiktoken>=0.13,<1" "pytest>=8"
~~~

~~~powershell
py -X utf8 -B -m pytest
py -X utf8 -B src/experiment.py
py -X utf8 -B ops/build_demo.py
~~~

The default replay and tests do not call OpenAI.
To run model trials, set OPENAI_API_KEY in your local environment first.
Do not put the key in source files, saved reports, or chat.
Then use these commands.

~~~powershell
py -X utf8 -B src/experiment.py --models
py -X utf8 -B ops/build_demo.py
~~~

The model trials call the OpenAI Responses API with synthetic records.
The default model is `gpt-5.4-mini-2026-03-17`.
Set OPENAI_MODEL to select another compatible model. Rebuild the replay after a model change.
Compatible models must support the Responses API and `reasoning.effort=none`.

Model access depends on your OpenAI account. Offline tests do not verify account access.
The adapter does not call Ollama.

The local tokenizer, tiktoken, estimates request size for offline replay.
Its first use can download public tokenizer data. It does not send records for tokenization.
Before generation, OpenAI counts the full request. Requests above the input allowance are blocked.
The report compares this server count with the usage returned after generation.

The configured 4,096-token total is an application allowance, not the model's advertised context capacity.
The input allowance remains 1,000 tokens. The output allowance is 256 tokens.
Requests use `store=False` and do not include conversation IDs or previous response IDs.
This setting does not define all provider retention behavior.

Python 3.11 or newer, openai, and tiktoken are required.
Pytest is required to run the test suite.
The experiment was developed on Windows with Python 3.14.

## What the comparison establishes

The deterministic replay covers five workflows with 200 logical executions each.
This is 1,000 simulated workflow executions, not 1,000 model calls.
The actual model trials form a separate, smaller experiment.
An ordinary replay reuses compatible recorded model evidence without running inference.
Changed prompts, selected records, or settings invalidate that evidence.

The read-policy comparison includes a budgeted recency baseline.
That baseline receives the same accepted records, access rules, pinned requirements, and input budget.
The proposed policy adds task-dependent selection.

Full replay and accumulated retrieval show how context can grow.
They are diagnostic baselines. They do not represent a production recommendation.

The policy engine uses SQLite for saved records and separate checkpoints.
Git can version saved files. It does not select which records enter a model request.

The selector combines keyword matching with vector similarity when its embedding cache is complete.
An embedding is a numerical representation of text. Vector similarity helps find related meanings with different words.
The selector combines the two ranked lists through reciprocal rank fusion.
Required fields and applicable pinned rules use direct lookup.

The OpenAI embedding client uses `text-embedding-3-small` with 512 dimensions.
SQLite stores vectors in `data/embedding-cache.sqlite`. Python calculates cosine similarity across eligible records.
Access and validity checks run before embedding or ranking.
This implementation uses no separate vector database and does not verify factual truth.

Offline replay uses cached vectors. An incomplete cache produces an explicit `lexical_fallback` result.
To populate the cache without generating answers, run this command with OPENAI_API_KEY configured.

~~~powershell
py -X utf8 -B src/experiment.py --embeddings
~~~

The `--models` command populates the cache, rebuilds selection, and runs answer generation.
The default command does not call either OpenAI endpoint.
The hybrid demonstration uses hand-authored test vectors. It does not claim measured OpenAI embedding quality.

## Inspect the evidence

- runs/experiment.json contains the replay and evaluation results.
- runs/model-trials-openai.json contains OpenAI requests and responses after API trials run.
- runs/history/qwen-model-trials.json preserves the historical Qwen requests and responses.
- runs/history/pre-refactor-evidence.zip preserves earlier reports, source snapshots, tests, and the original Qwen tokenizer.
- runs/demo-state.sqlite contains the persisted replay state.
- evals/evaluate_policy.py contains independent adversarial cases and holdout checks.
- tests/ contains executable behavior tests.
- docs/spec-experiment.md defines the experiment contract.
- runs/verification/tests.xml records the complete current Python test result.
- runs/verification/dom-check.json records offline demo controls and data-binding checks.
- runs/hybrid-evaluation.json compares keyword selection with hybrid selection using explicit test vectors.
- runs/verification/refactor-check.json records preservation checks and the current file organization.

All records are synthetic. Full record inspection is an operator view.
Do not expose its unrestricted audit data as a production tenant API.

## Code and output locations

| Location | Purpose |
|---|---|
| src/memory_policy.py | Memory admission, validity, scope, required fields, and context budgets |
| src/hybrid_retrieval.py | Vector cache, similarity calculation, and rank fusion |
| src/model_adapter.py and src/embedding_adapter.py | OpenAI request boundaries |
| src/experiment.py and src/learning_demo.py | Replay, scoring, compaction, and lesson demonstrations |
| src/demo/ | Editable HTML template, CSS styles, and JavaScript behavior |
| ops/build_demo.py | Embed the assets and report into one portable HTML file |
| runs/ | Current demo, report, evaluation, and saved state |
| runs/verification/ | Current checks and their execution records |
| runs/history/ | Preserved historical observations and compressed evidence |

The historical ZIP includes a SHA-256 manifest. Hash checks verify that each preserved file retains its original bytes.
Earlier records retain their original paths as historical metadata.

## Source books

Page numbers refer to physical PDF viewer pages in the local editions.

| Book | Relevant reading |
|---|---|
| An Illustrated Guide to AI Agents, Grootendorst and Alammar | PDF 235-255, 259-263, 275-280, 397-400, 626-628 |
| AI Agents: The Definitive Guide, Nicole Koenigstein | PDF 315-340 |

The policy document maps individual rules to specific passages.
Its implementation choices are proposals for this experiment, not universal industry standards.
The experiment adapts the principles. It does not claim to execute the books' examples unchanged.

## Limits

Passing synthetic checks does not establish production reliability.
Identity and provenance arrive as trusted runtime inputs in this experiment.
The application does not implement login, production authorization, distributed recovery, or physical memory deletion.

Policy-controlled context growth does not imply bounded disk storage.
The model trials preserve both successful and failed outputs.
The demo controls have offline DOM checks. Browser layout remains unverified because the browser blocked local file URLs.

## OpenAI integration references

- [GPT-5.4 mini model](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
- [Server token counting](https://developers.openai.com/api/docs/guides/token-counting)
- [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [Reciprocal rank fusion paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
