# IncidentOps Copilot v2 Dev Spec

## Goal

Build a portfolio-grade, offline-first incident triage platform that demonstrates full-stack engineering, evidence-grounded AI workflow design, retrieval engineering, security boundaries, observability, and testing.

## Non-Goals

- No real enterprise data.
- No claim of production authentication.
- No paid API dependency in default mode.
- No fake LLM, fake vision, or fake semantic retrieval claims.

## Architecture

- Frontend: Next.js App Router, TypeScript, Tailwind CSS.
- Backend: FastAPI, SQLModel, Alembic, SQLite by default.
- Analysis: `IncidentAnalysisPipeline` with explicit contracts, traces, and persisted audit runs.
- Retrieval: chunked KB, FAISS dense retrieval, BM25 lexical retrieval, RRF fusion, heuristic reranker.
- Security: demo RBAC, controlled attachment download, PII redaction.
- Demo Persona: frontend persists persona in a cookie and both client/server fetch paths send `X-Demo-User-Id`.

## Acceptance Criteria

- `pytest` passes without API keys or network providers.
- `ruff check .` passes.
- `python -m app.scripts.ingest_kb --check` runs.
- `python -m app.scripts.evaluate` writes JSON and Markdown reports and enforces non-zero thresholds.
- `npm run lint` and `npm run build` pass.
- `npm run test` verifies persona header/cookie helpers.
- Docker Compose can build; backend applies Alembic migration before API startup.
- Docker demo mode may run `BOOTSTRAP_DEMO_DATA=true` after migration to import synthetic data and rebuild the KB index; normal app startup must not call `create_all()`.

## Core Invariants

- High-confidence AI output must cite evidence or chunk IDs.
- Low evidence, conflict, high-risk, security, OCR failure, or critical severity requires human review.
- Trace/UI/log summaries use redacted content.
- Optional providers must degrade to offline providers when unavailable.
- Requester personas can only access their own tickets and attachments; Admin can access all admin views.
