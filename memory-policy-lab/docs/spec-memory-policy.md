# Memory policy for a persistent agent

Version: 1.0. Date: 2026-10-26. Scope: a local experiment with five workflows and 200 runs.

This policy combines principles from two books with explicit engineering decisions.
It does not define an industry standard.
The policy describes required behavior. Executed evaluation results establish which requirements the experiment satisfies.

## The decision this policy makes

Persistent memory stores information across runs. Context contains the information supplied to one model request.
The application selects context from persistent memory. Git can store versions, but Git does not make this selection automatically.

The policy separates five decisions:

1. Accept or reject a proposed memory record.
2. Select records for the current request.
3. Retain, supersede, or exclude old records.
4. Recover execution state after a restart.
5. Evaluate a proposed lesson before future use.

The experiment uses SQLite for persistent storage. The policy principles do not depend on that storage choice.
The application enforces access, update order, and context limits before the model runs.

**ELI10:** The agent can save many records. Each request receives only the records that pass the current rules.

## Sources and evidence labels

All page numbers identify physical PDF pages. They do not identify printed page numbers.

| ID | Local book | Relevant reading |
|---|---|---|
| I | Maarten Grootendorst and Jay Alammar, *An Illustrated Guide to AI Agents*. The local PDF has 694 pages. | Memory, PDF 224-286. Reflexion, PDF 397-400. Evaluation, PDF 442-452. Compaction, PDF 626-628. |
| D | Nicole Koenigstein, *AI Agents: The Definitive Guide*. The local PDF has 494 pages. | Recovery, PDF 319-320. Namespaces and memory types, PDF 323-328. Hygiene, PDF 332-340. Topology, PDF 341-342. |

The source passages were inspected directly. The original book implementations were not executed for this document.

| Label | Meaning |
|---|---|
| Source principle | A statement or example supported by the cited book pages. |
| Design rule | A requirement chosen for this experiment. A source principle informs the choice but does not prescribe every detail. |
| Acceptance check | An observable condition that tests the design rule. |
| Evidence state | The document specifies the check. The executed evaluation report records its result. |

The exact budgets, value limits, retrieval method, and rejection conditions are experiment configuration.
The books do not establish universally correct values for them.
The experiment must report its actual configuration with each result.

## The state that must remain visible

| State | Contents | What a policy action can change |
|---|---|---|
| Persistent store | Accepted, superseded, quarantined, and disabled records with decision metadata | Admission can add records or change their status. Selection cannot delete records. |
| Request context | Fixed instructions, current task, and selected memory data | Selection changes which records enter this request. |
| Execution checkpoint | Saved thread state, plan position, and completed local actions | Recovery restores the saved thread state. |
| Decision audit | Record IDs, policy decisions, exclusion reasons, and transaction results | Each relevant operation adds observable evidence. |

Exclusion from context does not mean deletion from storage.
A superseded record remains available for inspection, but the selector must not use it as a current fact.
A quarantined record is unavailable to normal retrieval until an authorized process resolves it.

The demo must show store state and context state separately.
It must also show the action produced from that context.
Token reduction alone does not establish successful agent behavior.

## Policy rules

### MP-01: Keep identities and workflows separate

**Source principle:** Namespaces separate user, organization, and memory type. Verified identity prevents user impersonation. D, PDF 323-325.
Shared and local memory have different coordination costs. D, PDF 341-342.

**Design rule:** Read and write operations must use the trusted runtime principal.
A principal identifies the user and their role.
The local experiment supplies this principal directly. It does not implement login.

The selector permits the current user's current workflow and explicit shared records.
The workflow value `shared` permits reuse across that user's workflows.
The user value `*` permits organization-wide records only after an administrator writes them.
Private records from another user must remain inaccessible.

Administrative inspection can list the complete synthetic store.
That inspection is an operator capability, not a tenant-facing API.

**Acceptance check:** A highly relevant record from another user remains excluded.
A private workflow-B record remains excluded from workflow A.
An authorized shared record remains available when it is applicable.

### MP-02: Keep data trust separate from instruction authority

**Source principle:** Memory poisoning changes later behavior through stored false premises. I, PDF 451.
Least privilege limits agent access and possible damage. I, PDF 612-613.
Procedural memory contains behavioral instructions. D, PDF 327-328.

**Design rule:** Runtime code assigns source and validation metadata.
A model-generated field cannot grant itself authority.
Untrusted document text cannot become an accepted fact or instruction merely because the agent saved it.

Memory data must not replace fixed system instructions or grant additional tool permissions.
Applicable user preferences remain subordinate to application constraints.
Summarization must preserve these authority boundaries.

**Acceptance check:** A saved document that requests additional privileges cannot change tool access.
A later run must still exclude its untrusted instructions after a restart.

### MP-03: Validate candidates before persistence

**Source principle:** Invalid or unvalidated memory can amplify error. D, PDF 320 and 334.
Example 10-14 checks length and known sensitive patterns before storage. D, PDF 336.

**Design rule:** Reject blank values, oversized values, invalid metadata, and known synthetic secret patterns.
Reject unsupported source claims.
Do not write rejected secret content into the decision audit.

Validation of format does not establish factual truth.
The experiment trusts its fixture validation metadata.
A production system needs a defined evidence-verification process.

**Acceptance check:** Each rejected candidate leaves accepted memory unchanged.
The decision audit records a reason without retaining rejected secret text.

### MP-04: Validate replacements before changing accepted state

**Source principle:** Example 10-15 controls contradictions, replacements, duplicates, and confidence. D, PDF 336-338.
Its code removes superseded facts before it checks each replacement's confidence. D, PDF 337.

**Design rule:** Validate the replacement before superseding an accepted record.
Commit the accepted replacement, status change, and audit evidence in one transaction.
A transaction makes these changes succeed together or fail together.

An older replacement must not override a newer accepted value.
Conflicting values with equal timestamps require quarantine.
Timestamp order alone cannot make an unauthorized source acceptable.
Runtime callers must supply trusted current time during admission.
The experiment rejects observations after that time before changing accepted state.
Without supplied admission time, the engine trusts the caller's chronology.

The experiment ranks source authority as `admin > user > verified_tool > reflection`.
A lower-authority conflicting update cannot replace a higher-authority accepted value.
This conservative order is an experiment choice. The books do not establish it as a universal rule.

**Acceptance check:** Start with an accepted currency preference.
Submit an invalid replacement that claims to supersede it.
The original preference must remain active and available.
The proposed replacement must not appear in context.

This check addresses a failure visible in the book's update order.
It does not claim that the complete book application exhibits that failure under every calling path.

### MP-05: Suppress duplicate active records

**Source principle:** Repeated facts and preferences should not accumulate without control. D, PDF 325.
Redundant retrieved content reduces useful context capacity. I, PDF 279-280 and 284.

**Design rule:** Compare normalized values within the same user, workflow, kind, and key.
Repeated matching active values must not create additional active records.
Do not merge records across access boundaries.
An authorized expiry change can create a new version with the same value.
The transaction supersedes the previous version. This permits renewal without duplicate active records.

Duplicate content is not independent corroboration.
A repeated claim must not receive greater authority solely through repetition.

**Acceptance check:** Submit the same preference repeatedly through run 200.
Only one equivalent active value must remain for its scoped key.
The request must not contain repeated copies.

### MP-06: Select only records that are valid now

**Source principle:** Outdated and noisy facts are long-term memory failure modes. D, PDF 320 and 332.
Semantic retrieval should supply relevant facts without replaying previous conversations. D, PDF 327.

**Design rule:** Exclude expired, future-dated, superseded, quarantined, and disabled records before relevance ranking.
Use the explicit request time for validity checks.
Never use similarity to bypass validity or access restrictions.

**Acceptance check:** A relevant expired fact must remain excluded.
A future-dated update must not affect an earlier request.
The exclusion trace must identify the reason for each decision.

### MP-07: Protect applicable requirements before optional retrieval

**Source principle:** Business rules can give important context additional weight. I, PDF 278.
Procedural memory uses structured records and direct reads. D, PDF 327-328.

**Design rule:** Include applicable pinned preferences and procedures before ranked optional records.
Pinned means that an applicable accepted record is required for this request.
Other memory kinds cannot become pinned through a candidate flag.

The application can also specify exact required keys.
Required keys cannot bypass access or validity checks.
If required evidence is missing, return `insufficient_evidence`.
Do not guess its value from unrelated history.

Required keys are exact application identifiers. They do not express general semantic requirements or include an explicit memory kind.
For matching keys, narrower authorized scopes take precedence.
Procedural records preserve source authority before scope specificity.
An administrator's shared procedure therefore takes precedence over a conflicting private user procedure.

**Acceptance check:** A run-1 preference remains available at run 200 when it is still applicable.
An unrelated run-199 episode must not displace it.
An inaccessible required key must cause insufficient evidence.

### MP-08: Retrieve optional context for the current task

**Source principle:** RAG retrieves relevant external information. I, PDF 244-248.
Reranking refines a candidate set for the query. I, PDF 277-278.

**Design rule:** Rank eligible optional records against the current query.
The hybrid selector combines word overlap with cosine similarity between embeddings.
An embedding is a numerical representation of text. Cosine similarity compares the direction of two embedding vectors.
Required keys and applicable pins still use direct lookup before optional ranking.

Access, status, expiry, and scope checks run before embedding requests or similarity calculations.
The embedding client uses `text-embedding-3-small` with 512 dimensions.
SQLite stores vectors in a separate cache. Python calculates similarity across eligible records.
This implementation does not require a dedicated vector database.

Reciprocal rank fusion combines positions from the keyword and semantic result lists.
The experiment uses a rank constant of 60, a cosine threshold of 0.35, and at most 20 semantic candidates.
These values are implementation choices. They require evaluation with real tasks and embeddings.
The complete context budget still limits the records that enter the model request.

Cache entries include the provider, model, dimensions, user, role, workflow, and content hash.
Changed content cannot reuse the previous content's vector.
Offline replay uses existing vectors without API calls.
If any required vector is missing, the selector reports `lexical_fallback` and uses word overlap.
API errors during an authorized cache update stop the run.

The policy does not require a vector database or an LLM reranker.
An alternative retrieval method must satisfy the same access, validity, and budget rules.
Linked-record expansion must also satisfy those rules.

**Acceptance check:** An old relevant fact remains eligible alongside new facts.
Recent irrelevant events must not enter context solely because they are recent.
Report required-fact recall independently from token usage.
Fixture tests must retrieve a paraphrase with zero keyword overlap.
They must also exclude inaccessible, expired, and quarantined records before embedding.

Hand-authored test vectors establish ranking behavior. They do not establish the quality of the OpenAI embedding model.

### MP-09: Enforce the complete serialized context budget

**Source principle:** Context capacity includes input and output requirements. I, PDF 235-236.
Trimming by message count can remove important earlier information. I, PDF 237-239.

**Design rule:** Reserve output capacity and a safety margin before selecting memory.
Count the complete serialized input with the configured tokenizer.
Include instructions, task text, separators, record metadata, and selected values in that count.

The model input must not exceed the remaining input limit.
If required content cannot fit, return `blocked_budget`.
Never silently remove required content to produce a passing size result.

The report must identify its tokenizer and any approximation.
It must distinguish measured prompt tokens from estimated tokens.

**Acceptance check:** Four oversized messages must not bypass the limit.
An oversized pinned requirement must block the request.
Do not send over-budget baseline prompts after silently truncating them.

### MP-10: Retain records separately from their eligibility

**Source principle:** Retention can use age, importance, or compression. D, PDF 332.
MemoryBank reinforces accessed memories and can forget unused items. I, PDF 251-255.

**Design rule:** This experiment uses logical expiry and supersession.
It retains excluded records for inspection and audit.
It does not implement automatic physical deletion or a storage-volume limit.

An old record can remain useful when it is valid and relevant.
A frequently accessed record can still be false, unsafe, or obsolete.
Access frequency must not determine authority.

**Acceptance check:** At run 200, expired and superseded rows remain inspectable but absent from normal context.
The report must show storage growth separately from context growth.

Production deletion periods, privacy duties, backups, and audit retention require separate decisions.
This document does not prescribe those periods.

### MP-11: Compact content without changing its meaning or authority

**Source principle:** Repeated summaries can still overflow or lose important details. I, PDF 240-243.
Thread compaction should preserve user decisions and preferences. D, PDF 333-334.
Stable task information and changing interaction state can remain separate. I, PDF 626-628.

**Design rule:** A compacted record must retain source IDs and the authority of its source material.
It must preserve applicable constraints, unresolved work, and required facts.
A summary must not invent an accepted fact or resolve an uncertain conflict without evidence.

Check both size and required-fact coverage after compaction.
Retain original evidence until the compacted representation passes its checks.
This experiment does not authorize destructive consolidation of source records.

**Acceptance check:** Compare required facts before and after repeated compaction.
Include a negative condition and an unresolved task in the test input.
Neither may disappear or reverse meaning.
Mark compaction unverified if no executed check demonstrates these properties.

The demonstration uses deterministic structured compaction.
It preserves protected goal, constraint, unresolved-work, and latest-tool fields exactly.
It replaces older messages with source references.
A candidate that changes protected fields must fail validation.
This checks state preservation. It does not evaluate unrestricted LLM summarization.
The protected-source mapping belongs to the synthetic fixture.
It does not establish a general source-attribution algorithm.

Five later cycles append 20 new messages each before compaction.
Each cycle verifies the previous archive before adding new records.
The archive file retains immutable versions, including the original 200-message version.
Context contains a version reference instead of the complete archived history.
The final cycle retains 300 source records while preserving the original protected fields.
The report records each cycle's measured state size against a configured limit.
That limit covers the structured state, not the complete model request.

### MP-12: Recover checkpoints without silently rewinding memory

**Source principle:** Checkpoint replay restores conversation state but does not automatically rewind long-term memory. D, PDF 319.
Persistent memory needs a durable storage layer. D, PDF 320.

**Design rule:** Store checkpoints separately from durable records.
Associate each checkpoint with its authorized user and thread.
Recovery restores checkpoint state and then uses current durable memory.
Reapply current access, validity, and budget rules after recovery.

The experiment must not describe this as historical reproduction of every prior input.
Exact historical reproduction would require versioned memory snapshots and the matching policy configuration.

**Acceptance check:** Save a checkpoint, update durable memory, and close the process.
Reload the checkpoint in a fresh process.
Verify restored thread state and the newer durable value.
Verify that another user cannot load the checkpoint.

### MP-13: Admit lessons through evidence and evaluation

**Source principle:** Reflexion stores reflective experiences for later trials. I, PDF 397-400.
This prompting method does not update model parameters. I, PDF 400.
Procedural memory can reinforce poor behavior without validation. D, PDF 323.

**Design rule:** A reflection begins as a lesson candidate.
Accept a lesson only with trusted validation and evidence references.
Reject unsupported, malformed, or unauthorized lessons.
A lesson cannot grant new tool permissions or override fixed instructions.

Retrieval of a lesson does not establish improvement.
Compare later task outcomes with the lesson enabled and disabled.
Use the same task conditions for both comparisons.

**Acceptance check:** A supported lesson becomes available to a later relevant request.
An unsupported lesson remains excluded.
A claimed improvement must have an observed task result.
Report deterministic and model-based results separately.

The demonstration starts with a failed simulated tool action.
A candidate lesson must pass a separate validation case before admission.
A later task tests whether the admitted lesson repairs the earlier failure.
Keep the validation case separate from the later demonstration task.
The demonstration can disable an admitted lesson while preserving its record and audit evidence.
Later requests then use the baseline action plan.
This demonstrates rollback to baseline behavior, not automatic restoration of an arbitrary earlier procedure.

### MP-14: Preserve observable decision evidence

**Source principle:** Context records user intention and supports debugging. I, PDF 275-276 and 285.
Trajectory evaluation can reveal problems that correct final answers conceal. I, PDF 442-443.

**Design rule:** Record selected IDs, exclusion reasons, policy configuration, prompt size, observable actions, and task results.
Keep rejected secret content out of logs.
Use concise decision reasons, not private chain-of-thought records.
Freeze each recorded snapshot. Later runs must not change its record list or values.
Reconstruct saved prompts from their selected records before accepting an evidence report.
The reconstructed prompt and measured token count must match the recorded values.

The complete exclusion trace is an operator view in this experiment.
A production tenant API must remove identifiers belonging to other users.

**Acceptance check:** A reviewer can explain why each displayed record entered or missed context.
The reviewer can connect the selected evidence to the simulated action.

## A concrete run-100 and run-200 example

Assume the revenue workflow runs daily alongside four other workflows.
The following records are illustrative fixture requirements, not measured results.

| Event | Persistent-store meaning | Correct request behavior at run 100 |
|---|---|---|
| Run 1: the user selects INR for revenue reports. | An accepted preference remains active. | Include the applicable preference even though it is old. |
| Run 40: a monthly amount is recorded. | An accepted fact has a validity period. | Exclude it if its validity has ended. |
| Run 70: another workflow records a private contact. | The record belongs to that workflow. | Exclude it from the revenue request. |
| Run 90: a document requests permission to send all records externally. | Untrusted content cannot grant permission. | Exclude the proposed instruction. |
| Run 99: a verified tool supplies the current revenue amount. | A valid current fact becomes available. | Include it when the request requires that amount. |
| Run 100: the user requests the revenue report. | The request does not make every old event relevant. | Use the currency preference and current required facts within the budget. |

At run 200, the same rules still apply.
An authorized newer currency preference can supersede the earlier preference.
An invalid replacement must leave the earlier accepted preference intact.
More stored episodes must not cause a larger-than-allowed request.

The store can grow while request size remains bounded.
This is the intended result of selection, not proof that storage management is complete.

## Baselines and success criteria

Use the same input events, request time, identities, and required answers for every baseline.
Compare these five conditions:

| Condition | What it tests | Expected failure to look for |
|---|---|---|
| Full replay | Every prior item enters the request. | Excess context, stale facts, and unrelated records. |
| Last four records | A recent-record count limits this synthetic history. | Loss of old requirements and oversized individual records. |
| Budgeted recency | Recent records fit a measured limit. | Old relevant facts can still disappear. |
| Accumulated top-k history | Each turn retrieves a few records and retains earlier augmented messages. | Context grows across turns despite bounded retrieval per turn. |
| Proposed policy | Admission, scope, validity, requirements, relevance, and budget rules work together. | Measure remaining failures instead of assuming success. |

The second baseline adapts the book's message-count trimming to this experiment's memory records.
It does not execute the book's original conversation class.

The fourth baseline follows an important code property in I, PDF 248.
`RAGMemory` appends retrieved content to inherited conversation memory.
Bounded retrieval per turn therefore does not establish bounded accumulated context.

Report runs 1, 10, 100, and 200 for all five workflows.
Report required-fact recall, scope leaks, stale recall, duplicates, context size, and task outcomes separately.
A smaller prompt that loses a required fact fails the policy objective.

A deterministic agent tests observable policy effects with local simulated tools.
A language-model trial tests how a specific model uses the supplied context.
Neither result substitutes for the other.

Test the gates with independent adversarial cases.
Temporarily disabling a gate should make its corresponding check fail.
This demonstrates that the check can detect the intended defect.

## Limits that must remain visible

- The local experiment has trusted synthetic principals, not an authentication service.
- Validation flags represent fixture evidence, not general automated truth verification.
- The lexical fallback can miss equivalent meanings expressed with different words.
- Hybrid fixture tests do not measure live embedding quality or production retrieval accuracy.
- Vector similarity can retrieve irrelevant records. Thresholds and ranking settings require task-specific evaluation.
- Known secret patterns do not detect every possible secret.
- Logical expiry does not physically erase saved records.
- A fresh-process reload does not prove power-loss durability or distributed concurrency safety.
- A checkpoint does not reverse external side effects.
- A successful fixture does not establish reliable behavior on every production task.
- Model behavior depends on the tested model, prompt, settings, and cases.
- A memory lesson changes supplied context. It does not demonstrate model-weight training.

## Glossary

| Term | Meaning in this experiment |
|---|---|
| Persistent memory | Information that remains available after the current process ends. |
| Context | The serialized input supplied to one model request. |
| Token | A unit used by a model to process text. |
| Tokenizer | The component that converts text into tokens. |
| Principal | The trusted runtime identity and role used for access decisions. |
| Namespace | A scope that separates records by owner, workflow, or type. |
| Semantic memory | Stored facts, including stable settings and preferences. |
| Episodic memory | Records of events, actions, and outcomes. |
| Procedural memory | Authorized instructions about how a task should proceed. |
| Provenance | The source identity and evidence references associated with a record. |
| Superseded | Replaced by a newer accepted value. |
| Quarantined | Excluded from normal use while a conflict or trust issue remains unresolved. |
| Disabled | An accepted lesson that an authorized operator excluded from future use. |
| Checkpoint | Saved execution state used to continue a thread. |
| Compaction | Reduction of context size while preserving required information. |
| Reflection | A proposed lesson derived from an earlier task and its outcome. |
| Transaction | A group of storage changes that succeeds or fails together. |
| Required-fact recall | The fraction of task-required facts present in selected context. |
| Scope leak | A record supplied outside its authorized user or workflow scope. |
| Embedding | A numerical representation of text for similarity calculations. |
| Cosine similarity | A score that compares the directions of two vectors. |
| Reciprocal rank fusion | A method that combines records' positions in separate ranked lists. |
| Vector cache | Stored embeddings that can serve later retrieval requests without another embedding call. |
| Lexical fallback | Keyword selection used when the required vector cache entries are unavailable. |

## Evidence status at policy authoring

Both books' cited passages were verified directly.
The policy rules and acceptance checks are specified.
The structured compaction and lesson demonstrations have executed unit checks.
The complete experiment report must establish the remaining implementation and model evidence.

The language review checked sentence length, consistent terms, active voice, conditions, and technical meaning.
The official ASD-STE100 dictionary was unavailable during this session because its download returned HTTP 403.
Vocabulary review remains incomplete. This is an STE-oriented document, not a full compliance claim.
