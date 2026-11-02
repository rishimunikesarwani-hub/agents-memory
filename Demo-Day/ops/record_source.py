"""Record immutable notebook references and acceptance-case provenance."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a1ff481c87cc3784c9c920c8e315b3341f57e563"
N = "ch10_memory_no_memory.ipynb"
T = "ch10_memory_topologies.ipynb"
M = "ch10_agent_memory_langgraph.ipynb"


def main():
    files = []
    for name in (N, T, M):
        path = ROOT / "data" / "source" / name
        raw = path.read_bytes()
        cells = json.loads(raw)["cells"]
        files.append(
            {
                "file": name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "cells": len(cells),
                "url": f"https://github.com/Nicolepcx/ai-agents-the-definitive-guide/blob/{COMMIT}/ch10/{name}",
            }
        )
    mapping = {}
    source = (ROOT / "eval-persistent-memory-test-plan.md").read_text(encoding="utf-8")
    for test_id in re.findall(r"^\| ((?:D[1-4]|OA)-\d{2}) \|", source, re.MULTILINE):
        notebook, cells, classification = M, [29], "adapted"
        if test_id.startswith("D1"):
            cells = {
                "D1-01": [7, 29],
                "D1-02": [29],
                "D1-03": [26, 29],
                "D1-04": [8, 9],
                "D1-05": [9, 10],
                "D1-06": [12],
                "D1-07": [7, 29],
                "D1-08": [7, 29],
                "D1-09": [9, 29],
                "D1-10": [6],
                "D1-11": [14],
                "D1-12": [16],
            }[test_id]
        elif test_id.startswith("D2"):
            cells = [10, 26, 29]
            classification = "new"
            if test_id == "D2-07":
                notebook, cells, classification = N, [4, 5], "adapted"
            if test_id == "D2-09":
                cells, classification = [23], "source gap"
        elif test_id.startswith("D3"):
            cells = {
                "D3-01": [8, 9],
                "D3-02": [6, 9],
                "D3-03": [9, 12],
                "D3-04": [29, 35],
                "D3-05": [9],
                "D3-06": [9],
                "D3-07": [9, 12, 29],
                "D3-08": [6, 9, 29],
                "D3-09": [9, 29],
                "D3-10": [6, 29, 31],
                "D3-11": [19, 29, 31],
                "D3-12": [12, 19],
                "D3-13": [7],
                "D3-14": [9, 26],
            }[test_id]
            if test_id in {"D3-02", "D3-07", "D3-08", "D3-10", "D3-11"}:
                classification = "source gap"
        elif test_id.startswith("D4"):
            notebook, cells = T, [2]
            if test_id in {"D4-06", "D4-07", "D4-08", "D4-11"}:
                classification = "new"
            if test_id == "D4-12":
                notebook, cells = M, [35]
        else:
            cells, classification = [5, 10, 29], "adapted"
        mapping[test_id] = {
            "notebook": notebook,
            "cell_indices": cells,
            "classification": classification,
            "commit": COMMIT,
        }
    assert len(mapping) == 55
    for reference in mapping.values():
        notebook = json.loads((ROOT / "data" / "source" / reference["notebook"]).read_text(encoding="utf-8"))
        assert all(notebook["cells"][index]["cell_type"] == "code" for index in reference["cell_indices"])
    manifest = {
        "repository": "https://github.com/Nicolepcx/ai-agents-the-definitive-guide",
        "commit": COMMIT,
        "cell_numbering": "zero-based",
        "notebooks": files,
    }
    (ROOT / "data" / "source" / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "evals" / "source-map.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(
        f"| {key} | {value['notebook']} | {', '.join(map(str, value['cell_indices']))} | {value['classification']} |"
        for key, value in mapping.items()
    )
    doc = f"""# Source comparison

Repository commit: `{COMMIT}`.

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
{rows}

**Adapted** means the application changes the source behavior or interface.
**New** means the requirement extends the source demonstration.
**Source gap** identifies source behavior that needs a regression case.
No classification establishes that an unopened feature works.

Technical meaning was reviewed.
Full ASD-STE100 dictionary review remains incomplete.
"""
    (ROOT / "docs" / "ref-source-comparison.md").write_text(doc, encoding="utf-8")
    print(f"Recorded {len(files)} notebook hashes and {len(mapping)} acceptance references.")


if __name__ == "__main__":
    main()
