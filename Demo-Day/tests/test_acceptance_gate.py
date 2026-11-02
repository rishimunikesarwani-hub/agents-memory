import importlib.util
import json
from pathlib import Path


def load_report_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "acceptance_report.py"
    spec = importlib.util.spec_from_file_location("acceptance_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_skip_does_not_erase_a_deterministic_pass(tmp_path, monkeypatch):
    module = load_report_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "runs").mkdir()
    report = {
        "verification": {"build_fingerprint": "fixture"},
        "summary": {"passed": 1, "skipped": 1},
        "tests": [
            {"nodeid": "tests/test_demo1.py::test_d1_04_profile_has_provenance", "outcome": "passed"},
            {"nodeid": "evals/test_live_demo1.py::test_oa_04_and_d1_live_extraction", "outcome": "skipped"},
        ],
    }
    (tmp_path / "runs" / "demo1-memory.json").write_text(json.dumps(report), encoding="utf-8")
    loaded = module.read_report("demo1-memory.json", "fixture")
    assert module.layer_status(loaded, {"D1-04"}) == "PASS"


def test_unavailable_database_cannot_pass_gate():
    module = load_report_module()
    assert module.layer_status(None, {"D1-03"}) == "BLOCKED"


def test_old_build_report_does_not_establish_current_pass(tmp_path, monkeypatch):
    module = load_report_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "runs").mkdir()
    report = {"verification": {"build_fingerprint": "old"}, "summary": {"passed": 55}}
    (tmp_path / "runs" / "demo1-memory.json").write_text(json.dumps(report), encoding="utf-8")
    assert module.read_report("demo1-memory.json", "current") is None


def test_openai_gate_requires_all_eight_cases_and_real_calls():
    module = load_report_module()
    postgres = {
        "tests": [
            {"nodeid": f"tests/test_provider.py::test_oa_{i:02}_boundary", "outcome": "passed"}
            for i in (1, 2, 3, 6, 7, 8)
        ]
    }
    live = {
        "tests": [
            {"nodeid": f"evals/test_provider.py::test_oa_{i:02}_live", "outcome": "passed"} for i in (4, 5)
        ]
    }
    assert module.openai_gate(postgres, live) == "PASS"
    assert module.openai_gate(postgres, None) == "BLOCKED"
    postgres["tests"][-1]["outcome"] = "failed"
    assert module.openai_gate(postgres, live) == "FAIL"


def test_postgres_skip_cannot_establish_complete_acceptance():
    module = load_report_module()
    assert module.completion_status({1: "PASS", 2: "PASS", 3: "PASS", 4: "PASS"}, "PASS", 0) == "PASS"
    assert module.completion_status({1: "PASS", 2: "PASS", 3: "PASS", 4: "PASS"}, "PASS", 1) == "BLOCKED"
    assert (
        module.completion_status({1: "PASS", 2: "PASS", 3: "PASS", 4: "NOT_STARTED"}, "PASS", 0) == "BLOCKED"
    )
