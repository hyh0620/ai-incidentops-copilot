# ADR 002: Rule Fallback Triage

## Decision

Keep rule-based triage as the default provider and label it as `rule_fallback`.

## Rationale

The system must work offline and should not pretend to call an LLM. Rules are transparent, deterministic, and suitable as a baseline for evaluation.

## Consequences

- Classification is explainable but limited.
- Optional LLM providers must return structured output with validated citations and degrade to `rule_fallback` on failure.
- Human review policy remains mandatory and cannot be bypassed by any provider.
