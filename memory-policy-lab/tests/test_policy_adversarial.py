"""Independent public-API contracts for the memory-policy experiment."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.evaluate_policy import CASES, run_case


class AdversarialPolicyTests(unittest.TestCase):
    """Each case owns its SQLite store and does not use replay-generator fixtures."""


def make_test(case_name):
    def test(self):
        report = run_case(case_name, ROOT)
        self.assertNotEqual(report["status"], "failed", report.get("error", report))
        if case_name == "lexical_paraphrase_limitation":
            self.assertIn(report["status"], {"limitation", "passed"})
    test.__name__ = "test_" + case_name
    return test


for name in CASES:
    setattr(AdversarialPolicyTests, "test_" + name, make_test(name))


if __name__ == "__main__":
    unittest.main()
