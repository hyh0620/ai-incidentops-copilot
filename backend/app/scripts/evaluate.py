import argparse
import json
from pathlib import Path

from app.evaluation.runner import run_evaluation


def _write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# IncidentOps Fixture Benchmark",
        "",
        "This report is generated from synthetic fixture cases, not production incidents.",
        "",
        "## Summary",
        "",
        f"- Cases: {report['case_count']}",
        f"- Passed: {report['passed']}",
        f"- CategoryAccuracy: {report['triage']['CategoryAccuracy']}",
        f"- SeverityExactMatch: {report['triage']['SeverityExactMatch']}",
        f"- HitRate@3: {report['retrieval']['HitRate@3']}",
        f"- FalseAutoApprovalRate: {report['triage']['FalseAutoApprovalRate']}",
        "",
        "## Thresholds",
        "",
    ]
    for key, value in report["thresholds"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Cases", ""])
    for case in report["cases"]:
        lines.append(
            f"- `{case['id']}`: category {case['predicted_category']}/{case['expected_category']}, "
            f"severity {case['severity']}/{case['expected_severity']}, sources={case['source_titles']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the offline IncidentOps fixture benchmark.")
    parser.add_argument("--dataset", default="tests/fixtures/golden_incident_cases.json")
    parser.add_argument("--artifacts-dir", default="../artifacts")
    args = parser.parse_args()

    report = run_evaluation(Path(args.dataset), Path(args.artifacts_dir))
    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / "evaluation_report.json"
    md_path = artifacts_dir / "evaluation_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, md_path)
    print(json.dumps({"passed": report["passed"], "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
