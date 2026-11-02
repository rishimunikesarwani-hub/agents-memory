# Experiment log

## 2026-10-26

The user requested a policy document and a demonstrable before-and-after experiment.
The user approved skipping the blueprint for this local experiment.
Three parallel agents verified source evidence, designed evaluations, and started implementation.
At five minutes, the review added budgeted recency and separate model-outcome evidence.
The source review found unsafe update ordering and accumulating retrieval history in educational examples.
These findings became explicit test cases.

The user moved the task to the Paytm Hackathon project.
All 16 files present at that point passed SHA-256 verification after the move.

Later reviews separated grounded answers from completed tasks.
They added expiry renewal, future-write rejection, repeated compaction, and audited lesson rollback.
The final review found and fixed stale cached-model evidence and a package-import defect.

The replay ingested 1,000 synthetic workflow executions and evaluated 20 snapshots across five methods.
The policy completed all 20 sampled tasks. Budgeted recency completed 10.
Twelve actual local-model observations were retained.
The policy completed six reports. Recency produced six appropriate requests for missing information.
All 12 runtime input-token counts matched preflight counts.

The complete Python suite passed 66 tests and nine subtests.
Offline DOM checks passed 80 selector combinations and 80 comparison-row clicks.
Five successive compaction cycles preserved prior evidence and protected state.
The source diagram was rendered and visually inspected.
The browser blocked local file URLs. Browser layout remains unverified.

The default replay was rerun without inference.
It retained all 12 compatible model observations and their unchanged raw evidence.
The final evidence report and HTML passed matching SHA-256 checks.

A later independent audit found mutable record lists in early accumulated-retrieval snapshots.
The prompts and model outputs were unchanged, but later runs changed the displayed record lists.
The repair copies each snapshot and checks every reconstructed prompt and token count before report delivery.
All 100 comparison contexts passed independent prompt, token, and selected-ID checks after the repair.
The 12 model observations remained unchanged and compatible.

## 2026-10-26 OpenAI migration

The user requested replacement of the local model with the OpenAI API.
The previous configuration used Qwen3 8B, not a 0.38B model.
Slide 10 correctly described word matching and required fields without vector search.

The active adapter now uses the OpenAI Responses API and `gpt-5.4-mini-2026-03-17` by default.
OPENAI_MODEL can select a compatible model. OPENAI_API_KEY supplies the credential through the process environment.
Requests contain fixed instructions and selected memory data without server conversation history.
The adapter sets `store=False` and checks the exact input count before generation.
Offline replay uses a labeled local estimate. API trials compare server preflight counts with actual usage.

Retrieval rules and SQLite storage remain unchanged.
Required fields use direct lookup. Optional records use normalized word overlap and recency.
Semantic retrieval remains a separate future change.

Historical Qwen observations remain unchanged in `runs/model-trials.json`.
The previous report, demo, and source files have hash-verified copies in `runs/qwen-baseline/`.
New API observations use `runs/model-trials-openai.json` after a live run.
The current demo reports zero OpenAI observations.

The user requested code and offline tests first. No live API calls were made.
The complete suite passed 96 tests and 28 subtests.
All 100 current context snapshots passed prompt, token-estimate, and record-ID checks.
The independent evaluation passed 26 cases with zero failures and one expected lexical-retrieval limitation.
Offline demo checks passed 7,673 assertions across 80 selector combinations.
The missing-key check returned a failure before changing the replay report.

The README passed selected mechanical language checks and a technical meaning review.
The full ASD dictionary review remains incomplete.
Live OpenAI account access and model behavior remain unverified.
See `runs/openai-migration-check.json` for the current verification receipt.

## 2026-10-26 Approved hybrid retrieval and presentation update

The user approved hybrid retrieval after the OpenAI migration.
The selector now combines keyword rankings and embedding cosine rankings through reciprocal rank fusion.
Required fields and applicable pins remain direct lookups.
Access, validity, and scope checks run before optional records reach the embedding client.
The configured embedding model is `text-embedding-3-small` with 512 dimensions.

SQLite stores namespaced vectors keyed by provider, model, dimensions, scope, and content hash.
Python calculates similarity without a dedicated vector database.
Offline cache misses produce an explicit lexical fallback.
Authorized `--embeddings` or `--models` runs can populate the cache.
Embedding API errors stop the run without silent fallback.

The fixture demonstration retrieves the settlement-delay record for the query `late payouts`.
Keyword retrieval misses that record. Hybrid retrieval includes it with a lexical distractor.
The fixture recall changes from zero to one. Fixture precision changes from zero to one half.
These results test the implementation with hand-authored vectors. They do not measure live embedding quality.

The complete suite passed 141 tests and 28 subtests.
All 100 saved context snapshots passed integrity checks.
An additional full replay passed with API client creation blocked.
The demo passed 7,679 offline assertions across 80 selector combinations.
No live API calls were made.

Slides 5, 6, and 10 now describe hybrid retrieval and the OpenAI integration.
All other slide XML remains unchanged.
The editable PowerPoint, ten-page PDF, and slide 10 preview passed export and visual checks.
The presentation states that live API validation is pending.

The updated Mermaid diagram uses the existing white background and pastel palette.
Changed documentation passed the selected mechanical checks.
Four paragraph-length findings remain in unchanged policy sections. Full dictionary review remains incomplete.
See `runs/hybrid-completion-check.json` for current hashes and verification evidence.

## 2026-10-26 Code and folder refactor

The project keeps three working areas: the lab, presentation, and design reference.
A parent README now links the main artifacts.
The current PowerPoint path remains unchanged.

Editable demo assets now live in `src/demo/` as HTML, CSS, and JavaScript files.
The Python builder decreased from 218 lines to 42 lines.
The exported demo remained byte-identical immediately after extraction.
The experiment now shares the required-field support calculation and fixed model settings.
Its scoring behavior and cache validation remain unchanged.

Current checks now live in `runs/verification/`.
Historical Qwen observations now live in `runs/history/qwen-model-trials.json`.
The historical ZIP preserves 35 earlier files with verified SHA-256 hashes.
It includes earlier source snapshots, reports, tests, and the original Qwen tokenizer.
Paths in earlier log entries refer to those historical locations.

Old presentation drafts, browser logs, and caches moved to a recoverable temporary folder.
No files were permanently deleted.
The refactor record lists every move and the recovery location.
The runner now prevents bytecode files in child Python processes and stores current test results with other verification records.

The complete test suite passed 141 tests and 28 subtests before and after the code changes.
All 100 comparison contexts and their summary values remained unchanged after replay.
The demo passed 7,679 offline assertions across 80 selector combinations.
All design files retained their original bytes.

The open PowerPoint changed during the refactor, including text on slide 10.
The refactor did not write the PowerPoint file. The latest version remains in place.
The preserved presentation checks describe the earlier export.
No model API calls were made.

See `runs/verification/refactor-check.json` for the current evidence and file map.
