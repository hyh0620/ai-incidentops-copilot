# ADR 003: Human Review Policy

## Decision

Route low-confidence, high/critical severity, security category, insufficient retrieval evidence, and OCR failure cases to AI review.

## Rationale

Incident triage can affect security and availability. The project should demonstrate safe decision boundaries instead of auto-executing risky actions.

## Consequences

- Review records include explicit reasons and run IDs.
- Manual overrides preserve original decisions and correction reasons.
- Overrides are future evaluation data, not automatic model training.
