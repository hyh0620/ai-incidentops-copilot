# Fixture Benchmark

The benchmark uses `backend/tests/fixtures/golden_incident_cases.json`.

It contains 30 synthetic cases covering VPN/network, database timeout, API 500, MFA/access, phishing, suspicious login, malware, resource pressure, insufficient evidence, Chinese, English, mixed language, logs, HTTP status codes, exceptions, ORA codes, ECONNRESET, a real small PNG OCR fixture, OCR failure, keyword-noise negative cases, and conflicting-category cases.

This is a fixture regression benchmark, not a production metric and not evidence of generalization. Cases are intentionally coupled to the demo knowledge base so the project can catch regressions in the default offline workflow. Do not present the numbers as real enterprise accuracy.

Metrics emitted by `python -m app.scripts.evaluate`:

- Retrieval: HitRate@1/3/5, MRR, nDCG@3, Evidence Coverage, Evidence Precision, Unsupported Citation Rate, Insufficient Evidence Rate.
- Triage: Category Accuracy, Severity Exact Match, High-Risk/Security Review Recall, False Auto-Approval Rate, Citation Grounding Rate.
- System: per-stage P50/P95 latency, provider usage, index version, OCR status bucket.

Default quality gates:

- CategoryAccuracy >= 0.80
- HitRate@3 >= 0.80
- SeverityExactMatch >= 0.70
- HighRiskSecurityReviewRecall >= 0.80
- CitationGroundingRate >= 0.70
- FalseAutoApprovalRate <= 0.10

Current default offline baseline after the v2 closing fixes:

- Cases: 30
- CategoryAccuracy: 1.0000
- SeverityExactMatch: 1.0000
- HitRate@3: 0.9333
- CitationGroundingRate: 0.9333
- EvidencePrecision: 0.6818
- UnsupportedCitationRate: 0.3182
- InsufficientEvidenceRate: 0.2000
- OCR bucket: success=1, failed=1, degraded=1, not_exercised=28

Interpretation:

- High category/severity scores are expected because this is a fixture regression dataset.
- EvidencePrecision below 1.0 is a documented limitation of the local hash + BM25 + heuristic reranker stack; unsupported citations are reported instead of hidden.
- `expected_source_titles=[]` cases only count as retrieval success when final sources are empty or the run is explicitly marked insufficient evidence.
