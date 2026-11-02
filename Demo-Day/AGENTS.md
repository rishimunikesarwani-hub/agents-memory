# Implementation contract

Use `spec-persistent-memory-prd.md` and `eval-persistent-memory-test-plan.md` as the acceptance baseline.
The user explicitly requested implementation against these two documents.
Preserve both filenames and the source notebooks.

Write each behavioral test before its implementation.
Save the failing result and the passing result in `runs/`.
Do not implement Demo 2 before the Demo 1 gate passes.
Apply the same rule to the remaining gates.
Report unavailable database and OpenAI checks as incomplete.

Use one parent graph and one billing worker graph.
Use PostgreSQL with pgvector for the durable application.
Use OpenAI directly for production model calls.
Keep deterministic test providers inside tests.
Do not replace required integration checks with simulated results.

Keep keys outside code, checkpoints, logs, and evidence.
Use trusted local identity arguments for this single-user learning application.
This application does not provide network authentication or perform refunds.

Use concise technical English for documentation.
Keep a glossary in the architecture document.
Record language review limits.
