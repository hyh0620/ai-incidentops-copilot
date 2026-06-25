import argparse
import json
from pathlib import Path

from app.evaluation.runner import run_evaluation


def _write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# IncidentOps Fixture Benchmark",
        "",
        "当前评测集为 synthetic regression benchmark，用于检查检索、引用和人工复核规则是否发生退化；结果不代表真实企业线上效果。",
        "",
        "## Summary",
        "",
        f"- Cases: {report['case_count']}",
        f"- Passed: {report['passed']}",
        f"- CategoryAccuracy: {report['triage']['CategoryAccuracy']}",
        f"- SeverityExactMatch: {report['triage']['SeverityExactMatch']}",
        f"- HitRate@3: {report['retrieval']['HitRate@3']}",
        f"- ConfiguredEmbeddingProvider: {report.get('configured_embedding_provider')}",
        f"- EffectiveEmbeddingProvider: {report.get('effective_embedding_provider')}",
        f"- EmbeddingModel: {report.get('embedding_model')}",
        f"- FallbackReason: {report.get('fallback_reason')}",
        f"- FalseAutoApprovalRate: {report['triage']['FalseAutoApprovalRate']}",
        "",
        "## Retrieval Modes",
        "",
        "| Mode | HitRate@1 | HitRate@3 | HitRate@5 | MRR | nDCG@3 | EvidencePrecision | UnsupportedCitationRate | avg_latency_ms | Configured provider | Dense provider | Model | Fallback reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for mode, metrics in report.get("retrieval_modes", {}).items():
        lines.append(
            f"| {mode} | {metrics['HitRate@1']} | {metrics['HitRate@3']} | {metrics['HitRate@5']} | "
            f"{metrics['MRR']} | {metrics['nDCG@3']} | {metrics['EvidencePrecision']} | "
            f"{metrics['UnsupportedCitationRate']} | {metrics['avg_latency_ms']} | "
            f"{metrics.get('configured_embedding_provider')} | {metrics.get('effective_dense_provider')} | "
            f"{metrics.get('embedding_model')} | {metrics.get('fallback_reason')} |"
        )
    lines.extend(
        [
            "",
            "## Thresholds",
            "",
        ]
    )
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
    parser.add_argument(
        "--embedding-provider",
        choices=["local_hash_embedding_fallback", "sentence_transformers"],
        default=None,
        help="Override EMBEDDING_PROVIDER for this evaluation run. Defaults to environment/config.",
    )
    args = parser.parse_args()

    report = run_evaluation(
        Path(args.dataset),
        Path(args.artifacts_dir),
        embedding_provider_override=args.embedding_provider,
    )
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
