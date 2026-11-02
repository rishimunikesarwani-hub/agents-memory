"""Build a portable HTML viewer from recorded experiment evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_DIR = ROOT / "src" / "demo"


def load_template():
    """Inline the editable assets so the exported demo remains self-contained."""
    template = (TEMPLATE_DIR / "template.html").read_text(encoding="utf-8")
    for marker, name in (("__DEMO_CSS__", "styles.css"), ("__DEMO_JS__", "app.js")):
        template = template.replace(marker, (TEMPLATE_DIR / name).read_text(encoding="utf-8"))
    return template


def build_demo(root_dir=ROOT, report_path=None, output_path=None):
    root = Path(root_dir)
    report_file = Path(report_path) if report_path else root / "runs" / "experiment.json"
    output_file = Path(output_path) if output_path else root / "runs" / "demo.html"
    report = json.loads(report_file.read_text(encoding="utf-8-sig"))
    if not isinstance(report, dict) or not isinstance(report.get("comparisons"), list):
        raise ValueError("The experiment report must contain a comparisons list.")
    serialized = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(load_template().replace("__EXPERIMENT_JSON__", serialized), encoding="utf-8")
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(build_demo(report_path=args.report, output_path=args.output))
