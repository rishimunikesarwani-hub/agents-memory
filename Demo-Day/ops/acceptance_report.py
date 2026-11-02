"""Generate gate status from current test evidence. Never infer integration from unit results."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from user_memory.evidence import build_fingerprint

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a1ff481c87cc3784c9c920c8e315b3341f57e563"


def ids_for_test(nodeid):
    ids = {value.upper().replace("_", "-") for value in re.findall(r"(?:d[1-4]|oa)_\d{2}", nodeid)}
    if "test_oa_02_03_official_clients" in nodeid:
        ids.update({"OA-02", "OA-03"})
    if "test_oa_02_03_08_http_destination" in nodeid:
        ids.update({"OA-02", "OA-03", "OA-08"})
    if "test_oa_04_and_d1_live_extraction" in nodeid:
        ids.update({"OA-04", "D1-04", "D1-05", "D1-06"})
    if "test_d3_live_correction_summary_and_recall" in nodeid:
        ids.update({"D3-01", "D3-02", "D3-03", "D3-12"})
    return ids


def read_report(name, fingerprint):
    path = ROOT / "runs" / name
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("verification", {}).get("build_fingerprint") != fingerprint:
        return None
    # Full pytest runs can contain both verification layers. Keep their evidence separate.
    prefix = "evals/" if "live" in name else "tests/"
    report["tests"] = [
        test for test in report.get("tests", []) if test["nodeid"].replace("\\", "/").startswith(prefix)
    ]
    return report


def case_status(report, test_id):
    if report is None:
        return "NOT_RUN"
    matches = [test for test in report.get("tests", []) if test_id in ids_for_test(test["nodeid"])]
    if not matches:
        return "NOT_RUN"
    outcomes = {test["outcome"] for test in matches}
    if outcomes & {"failed", "error"}:
        return "FAIL"
    if "skipped" in outcomes:
        return "BLOCKED"
    return "PASS" if outcomes == {"passed"} else "NOT_RUN"


def layer_status(report, ids):
    if report is None:
        return "BLOCKED"
    values = {case_status(report, key) for key in ids}
    if "FAIL" in values or report.get("summary", {}).get("failed", 0):
        return "FAIL"
    if values != {"PASS"}:
        return "BLOCKED"
    return "PASS"


def openai_gate(postgres, live):
    checks = {
        layer_status(postgres, {f"OA-{i:02}" for i in (1, 2, 3, 6, 7, 8)}),
        layer_status(live, {"OA-04", "OA-05"}),
    }
    return "FAIL" if "FAIL" in checks else "PASS" if checks == {"PASS"} else "BLOCKED"


def completion_status(gates, provider_gate, postgres_skips):
    checks = set(gates.values()) | {provider_gate}
    if "FAIL" in checks:
        return "FAIL"
    return "PASS" if checks == {"PASS"} and not postgres_skips else "BLOCKED"


def main():
    fingerprint = build_fingerprint()
    reports = {
        name: read_report(f"demo1-{name}.json", fingerprint) for name in ("memory", "postgres", "live")
    }
    all_d1 = {f"D1-{i:02}" for i in range(1, 13)}
    layers = {
        "deterministic": layer_status(reports["memory"], all_d1 - {"D1-03"}),
        "postgres": layer_status(reports["postgres"], all_d1),
        "live_openai": layer_status(reports["live"], {"OA-04", "OA-05"}),
    }
    gate = "PASS" if set(layers.values()) == {"PASS"} else "FAIL" if "FAIL" in layers.values() else "BLOCKED"
    gates = {1: gate}
    for number, count in ((2, 9), (3, 14), (4, 12)):
        if not (ROOT / "tests" / f"test_demo{number}.py").exists():
            gates[number] = "NOT_STARTED"
            continue
        status = layer_status(reports["postgres"], {f"D{number}-{i:02}" for i in range(1, count + 1)})
        if number == 3 and status == "PASS":
            status = layer_status(reports["live"], {"D3-01", "D3-02", "D3-03", "D3-12"})
        if number == 4 and status == "PASS":
            status = layer_status(reports["live"], {"D4-03", "D4-10"})
        gates[number] = status if gates[number - 1] == "PASS" else "BLOCKED"
    cases = []
    source_map = json.loads((ROOT / "evals" / "source-map.json").read_text(encoding="utf-8"))
    for line in (ROOT / "eval-persistent-memory-test-plan.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"\| ((?:D[1-4]|OA)-\d{2}) \| (.*?) \| (.*?) \|", line)
        if match:
            test_id, action, criterion = match.groups()
            cases.append(
                {
                    "id": test_id,
                    "action": action,
                    "pass_criterion": criterion,
                    "deterministic": case_status(reports["memory"], test_id),
                    "postgres": case_status(reports["postgres"], test_id),
                    "live_openai": case_status(reports["live"], test_id),
                    "evidence": {
                        layer: [
                            {
                                "test": test["nodeid"],
                                "outcome": test["outcome"],
                                "observed": test.get("user_properties", []),
                            }
                            for test in (report or {}).get("tests", [])
                            if test_id in ids_for_test(test["nodeid"])
                        ]
                        for layer, report in reports.items()
                    },
                    "source": source_map[test_id],
                }
            )
    assert len(cases) == 55 and len({case["id"] for case in cases}) == 55
    provider_gate = openai_gate(reports["postgres"], reports["live"])
    postgres_counts = (reports["postgres"] or {}).get("summary", {})
    complete = completion_status(gates, provider_gate, postgres_counts.get("skipped", 0))
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "build_fingerprint": fingerprint,
        "source_commit": COMMIT,
        "demo1_gate": gate,
        "demo1_layers": layers,
        "demo2_gate": gates[2],
        "demo3_gate": gates[3],
        "demo4_gate": gates[4],
        "openai_gate": provider_gate,
        "completion": complete,
        "report_counts": {name: (report or {}).get("summary", {}) for name, report in reports.items()},
        "cases": cases,
    }
    (ROOT / "runs" / "acceptance-summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    counts = reports["memory"].get("summary", {}) if reports["memory"] else {}
    text = f"""# Build verification status

Generated: `{result["generated_at"]}`.

Build fingerprint: `{fingerprint}`.

## Gate status

| Gate | Result |
|---|---|
| Demo 1 | **{gate}** |
| Demo 2 | {gates[2]} |
| Demo 3 | {gates[3]} |
| Demo 4 | {gates[4]} |
| OpenAI acceptance | {provider_gate} |
| Complete application | **{complete}** |

## Demo 1 verification layers

| Layer | Result |
|---|---|
| Deterministic state and memory tests | {layers["deterministic"]} |
| PostgreSQL integration | {layers["postgres"]} |
| Live OpenAI | {layers["live_openai"]} |

The current memory-run report contains `{counts.get("passed", 0)}` passed checks and `{counts.get("skipped", 0)}` unavailable checks.
The complete application result also requires all 55 planned cases and no skipped PostgreSQL checks.
The [acceptance ledger](../runs/acceptance-summary.json) preserves each planned case and its evidence layer.

## Next action

If a gate remains incomplete, continue at that stage.
If all gates pass, follow [the four-demo guide](guide-four-demos.md).
Run `ops/test-demo1.ps1 -Postgres -Live` for cumulative database and live verification.
The command retains its original filename and runs all implemented tests.
Do not advance until the current stage and all previous stages pass.

The runner rejects reports from a different source or test fingerprint.
Unimplemented later cases remain `NOT_RUN`.
Unavailable database or live checks remain incomplete acceptance.

Language and meaning were reviewed.
Full ASD-STE100 dictionary review remains incomplete.
"""
    (ROOT / "docs" / "eval-build-status.md").write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "gates": gates,
                "openai_gate": provider_gate,
                "completion": complete,
                "layers": layers,
                "planned_cases": len(cases),
            }
        )
    )
    return 0 if complete == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
