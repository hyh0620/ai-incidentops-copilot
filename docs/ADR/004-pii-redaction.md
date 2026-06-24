# ADR 004: PII Redaction

## Decision

Redact common PII and secrets before content enters traces, UI evidence summaries, prompts, retrieval queries, or audit records.

## Rationale

Incident logs often contain credentials, tokens, emails, cookies, and internal addresses. Demo systems should still model safe handling.

## Consequences

- Original attachments remain in controlled storage.
- Diagnostic terms such as error codes and exception names are preserved.
- Tests verify sensitive tokens do not leak into analysis traces.
