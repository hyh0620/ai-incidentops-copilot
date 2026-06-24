# 5-Minute Demo Script

1. Open `/` and state the boundary: synthetic demo data, offline providers, no paid API required.
2. Use the Demo Persona switcher in the top bar: show Requester A, Requester B, and Admin. Explain it is cookie + `X-Demo-User-Id` demo RBAC, not production auth.
3. As Requester A, open `/requester/tickets/new`, submit a database/API error with a short log file.
4. Switch to Requester B and show that Requester A's ticket is not visible.
5. Switch to Admin and open the created admin ticket detail page.
6. Show text/log/OCR evidence, redaction marker, provider labels, knowledge chunk citations, dense/BM25/fusion/rerank scores.
7. Show AI Analysis Runs and pipeline trace with real stage latency, degraded/skipped states, provider and fallback reasons.
8. Open `/admin/ai-review`, explain why high-risk, OCR failure, conflict, or insufficient-evidence cases need human review.
9. Open `/requester/kb`, show index readiness, corpus hash, chunk count, provider and build time.
10. Run or show `python -m app.scripts.evaluate` and explain fixture metrics are regression guards, not production KPIs.
