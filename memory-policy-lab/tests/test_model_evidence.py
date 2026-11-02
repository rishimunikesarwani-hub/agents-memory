"""Cached model evidence must match the current request and remain auditable."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import experiment


def fixture():
    selected = [{"id": "currency-1", "key": "currency", "value": "INR"}]
    expected = {"customer_code": "ZX-A-731", "settlement_days": 3, "currency": "INR", "status": "ready"}
    prompt = experiment.render_prompt(experiment.QUERY, selected)
    request = experiment.request_payload(prompt, output_limit=256)
    trial = {"workflow": "workflow-a", "run": 200, "arm": "budgeted_recency", "repeat": 1, "expected": expected,
        "selected_ids": ["currency-1"], "prompt": prompt,
        "result": {"status": "completed", "provider": "openai", "provider_model": experiment.model_identity()["name"],
            "prompt_eval_count": 300, "preflight_tokens": 300,
            "local_estimate_tokens": len(prompt), "token_count_match": True,
            "parsed": {"customer_code": None, "settlement_days": None, "currency": "INR", "status": "needs_clarification"},
            "request": request,
            "count_request": {key: request[key] for key in ("model", "instructions", "input")}}}
    model_report = {"model": experiment.model_identity(), "settings": experiment.model_settings(), "trials": [trial]}
    report = {"comparisons": [{"workflow": "workflow-a", "run": 200, "expected": expected,
        "arms": [{"name": "budgeted_recency", "prompt": prompt, "tokens": len(prompt), "input_limit": 1000, "selected_ids": ["currency-1"], "selected": selected}]}],
        "config": {"provider": "openai", "model": experiment.model_identity()["name"], "reasoning_effort": "none",
            "model_context": 4096, "output_reserve": 256, "repeats": [1, 2]},
        "replay": {}, "limitations": [], "summary": [], "evaluation": {"passed": 1, "failed": 0, "limitations": 0}}
    return report, model_report


class ModelEvidenceTests(unittest.TestCase):
    def test_returned_provider_must_be_openai(self):
        for provider in (None, "ollama", "another-provider"):
            with self.subTest(provider=provider):
                report, saved = fixture()
                trial = saved["trials"][0]
                trial["result"]["provider"] = provider
                selected = experiment.cached_trial_context(trial, saved, report, len)
                experiment.score_model_trial(trial, selected)
                self.assertFalse(trial["trial_trusted"])
                self.assertIn("returned_provider_missing_or_changed", trial["cache_validation"]["issues"])

    def test_returned_model_matches_pin_or_exact_alias_snapshot(self):
        pinned = "gpt-5.4-mini-2026-03-17"
        alias = "gpt-5.4-mini"
        cases = (
            (pinned, pinned, True),
            (pinned, "gpt-5.4-mini-2026-03-18", False),
            (pinned, pinned + "-2026-03-18", False),
            (pinned, None, False),
            (alias, alias, True),
            (alias, pinned, True),
            (alias, "gpt-5.4-mini-plus-2026-03-17", False),
            (alias, pinned + "-extra", False),
            (alias, "another-model", False),
        )
        for configured, returned, compatible in cases:
            with self.subTest(configured=configured, returned=returned), patch.dict("os.environ", {"OPENAI_MODEL": configured}):
                report, saved = fixture()
                trial = saved["trials"][0]
                trial["result"]["provider_model"] = returned
                original_result = copy.deepcopy(trial["result"])
                selected = experiment.cached_trial_context(trial, saved, report, len)
                experiment.score_model_trial(trial, selected)
                self.assertEqual(trial["trial_trusted"], compatible)
                self.assertEqual(trial["result"], original_result)
                if not compatible:
                    self.assertIn("returned_model_missing_or_changed", trial["cache_validation"]["issues"])

    def test_different_api_model_invalidates_saved_evidence(self):
        report, saved = fixture()
        report["config"]["model"] = "another-model"
        trial = saved["trials"][0]
        experiment.cached_trial_context(trial, saved, report, len)
        self.assertFalse(trial["cache_compatible"])
        self.assertIn("model_identity_missing_or_changed", trial["cache_validation"]["issues"])

    def test_modified_count_payload_invalidates_saved_evidence(self):
        report, saved = fixture()
        trial = saved["trials"][0]
        trial["result"]["count_request"]["input"] = "a different request"
        experiment.cached_trial_context(trial, saved, report, len)
        self.assertFalse(trial["cache_compatible"])

    def test_old_qwen_trials_are_not_attached_to_openai_replay(self):
        report, saved = fixture()
        learning = {"compaction": {"status": "passed"}, "evolution": {"status": "passed"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            experiment.write_json(root / "runs" / "model-trials.json", saved)
            experiment.write_json(root / "runs" / "experiment.json", report)
            with patch("src.learning_demo.run_learning_demo", return_value=learning):
                output = experiment.refresh_report(root, len)
            self.assertNotIn("model_trials", output)
            self.assertEqual(output["model_connection"]["status"], "configured_not_live_verified")

    def test_model_failure_is_not_a_successful_experiment(self):
        for status in ("error", "incomplete", "refused", "failed", "cancelled", "queued", "in_progress"):
            with self.subTest(status=status):
                report, saved = fixture()
                report["learning"] = {"compaction": {"status": "passed"}, "evolution": {"status": "passed"}}
                report["model_trials"] = saved["trials"]
                report["model_trials"][0]["result"]["status"] = status
                self.assertTrue(experiment.report_failed(report))

    def test_live_cli_requires_key_before_changing_reports(self):
        with patch.object(experiment, "require_api_key", side_effect=RuntimeError("Set OPENAI_API_KEY")), \
                patch.object(experiment, "run_replay") as replay, \
                patch("sys.argv", ["experiment.py", "--models"]):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                experiment.main()
            replay.assert_not_called()

    def test_embedding_cli_requires_key_before_changing_reports(self):
        with patch.object(experiment, "require_api_key", side_effect=RuntimeError("Set OPENAI_API_KEY")), \
                patch.object(experiment, "run_replay") as replay, \
                patch("sys.argv", ["experiment.py", "--embeddings"]):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                experiment.main()
            replay.assert_not_called()

    def test_models_only_rejects_lexical_fallback_before_inference(self):
        report, _ = fixture()
        arm = report["comparisons"][0]["arms"][0]
        arm.update(name="policy", retrieval="lexical_fallback")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            experiment.write_json(root / "runs" / "experiment.json", report)
            with patch.object(experiment, "ROOT", root), patch.object(experiment, "require_api_key"), \
                    patch.object(experiment, "load_counter", return_value=(len, {})), \
                    patch.object(experiment, "run_models") as model, \
                    patch("sys.argv", ["experiment.py", "--models-only"]):
                with self.assertRaisesRegex(ValueError, "embedding vectors"):
                    experiment.main()
                model.assert_not_called()

    def test_runtime_integrity_guard_rejects_prompt_token_and_id_drift(self):
        for field, value in (("prompt", "mutated"), ("tokens", -1), ("selected_ids", ["wrong"])):
            with self.subTest(field=field):
                report, _ = fixture()
                self.assertEqual(experiment.validate_report_snapshots(report, len), 1)
                report["comparisons"][0]["arms"][0][field] = value
                with self.assertRaises(ValueError):
                    experiment.validate_report_snapshots(report, len)

    def test_arm_snapshot_does_not_change_when_history_grows(self):
        history = [experiment.candidate("first", "workflow-a", 1, key="currency", value="INR")]
        arm = experiment.arm_result("accumulated_top3", history, "workflow-a", 1,
            experiment.expected_for("workflow-a", 1), len)
        saved_prompt = arm["prompt"]
        saved_tokens = arm["tokens"]
        history.append(experiment.candidate("later", "workflow-a", 2, key="currency", value="USD"))
        history[0]["value"] = "EUR"
        self.assertEqual(len(arm["selected"]), 1)
        self.assertEqual(arm["selected"][0]["value"], "INR")
        self.assertEqual(arm["prompt"], saved_prompt)
        self.assertEqual(arm["tokens"], saved_tokens)
        self.assertEqual(arm["prompt"], experiment.render_prompt(experiment.QUERY, arm["selected"]))
        self.assertEqual(arm["tokens"], len(arm["prompt"]))

    def test_correct_abstention_is_grounded_but_not_complete(self):
        report, saved = fixture()
        trial = saved["trials"][0]
        selected = experiment.cached_trial_context(trial, saved, report, len)
        experiment.score_model_trial(trial, selected)
        self.assertTrue(trial["trial_trusted"])
        self.assertTrue(trial["grounded_response"])
        self.assertTrue(trial["appropriate_abstention"])
        self.assertFalse(trial["task_success"])

    def test_stale_prompt_preserves_output_but_invalidates_trust(self):
        report, saved = fixture()
        report["comparisons"][0]["arms"][0]["prompt"] = "different prompt"
        trial = saved["trials"][0]
        original = copy.deepcopy(trial["result"])
        selected = experiment.cached_trial_context(trial, saved, report, len)
        experiment.score_model_trial(trial, selected)
        self.assertFalse(trial["trial_trusted"])
        self.assertIn("prompt_changed", trial["cache_validation"]["issues"])
        self.assertEqual(trial["result"], original)

    def test_changed_selected_ids_or_settings_invalidate_cache(self):
        for change in ("ids", "settings"):
            with self.subTest(change=change):
                report, saved = fixture()
                if change == "ids":
                    report["comparisons"][0]["arms"][0]["selected_ids"] = ["different-record"]
                else:
                    saved["settings"].pop("model_context")
                trial = saved["trials"][0]
                selected = experiment.cached_trial_context(trial, saved, report, len)
                experiment.score_model_trial(trial, selected)
                self.assertFalse(trial["cache_compatible"])
                self.assertFalse(trial["trial_trusted"])

    def test_token_count_mismatch_is_a_hard_failure(self):
        report, saved = fixture()
        trial = saved["trials"][0]
        trial["result"]["token_count_match"] = False
        selected = experiment.cached_trial_context(trial, saved, report, len)
        experiment.score_model_trial(trial, selected)
        self.assertFalse(trial["trial_trusted"])
        self.assertFalse(trial["grounded_response"])

    def test_wrong_match_flag_cannot_override_actual_count_difference(self):
        report, saved = fixture()
        trial = saved["trials"][0]
        trial["result"]["prompt_eval_count"] += 1
        selected = experiment.cached_trial_context(trial, saved, report, len)
        experiment.score_model_trial(trial, selected)
        self.assertFalse(trial["trial_trusted"])

    def test_default_cli_keeps_compatible_model_observations_without_inference(self):
        report, saved = fixture()
        learning = {"compaction": {"status": "passed"}, "evolution": {"status": "passed"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            experiment.write_json(root / "runs" / experiment.MODEL_TRIALS_FILE, saved)
            with patch.object(experiment, "ROOT", root), patch.object(experiment, "load_counter", return_value=(len, {})), \
                    patch.object(experiment, "run_replay", return_value=report), \
                    patch.object(experiment, "run_evaluation", return_value=report["evaluation"]), \
                    patch("src.learning_demo.run_learning_demo", return_value=learning), \
                    patch.object(experiment, "infer") as model, patch("sys.argv", ["experiment.py"]):
                self.assertEqual(experiment.main(), 0)
                model.assert_not_called()
            output = json.loads((root / "runs" / "experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(len(output["model_trials"]), 1)
            self.assertEqual(output["model_summary"]["budgeted_recency"]["trusted_observations"], 1)

    def test_refresh_cli_fails_when_learning_fails(self):
        report, saved = fixture()
        learning = {"compaction": {"status": "failed"}, "evolution": {"status": "passed"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            experiment.write_json(root / "runs" / "experiment.json", report)
            with patch.object(experiment, "ROOT", root), patch.object(experiment, "load_counter", return_value=(len, {})), \
                    patch("src.learning_demo.run_learning_demo", return_value=learning), patch("sys.argv", ["experiment.py", "--refresh"]):
                self.assertEqual(experiment.main(), 1)

    def test_default_cli_fails_when_learning_fails(self):
        report, _ = fixture()
        learning = {"compaction": {"status": "passed"}, "evolution": {"status": "failed"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            with patch.object(experiment, "ROOT", root), patch.object(experiment, "load_counter", return_value=(len, {})), \
                    patch.object(experiment, "run_replay", return_value=report), \
                    patch.object(experiment, "run_evaluation", return_value=report["evaluation"]), \
                    patch("src.learning_demo.run_learning_demo", return_value=learning), patch("sys.argv", ["experiment.py"]):
                self.assertEqual(experiment.main(), 1)


if __name__ == "__main__":
    unittest.main()
