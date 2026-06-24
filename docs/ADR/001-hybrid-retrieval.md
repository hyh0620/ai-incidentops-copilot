# ADR 001: Local Hybrid Retrieval

## Decision

Use local FAISS dense retrieval with deterministic hash embeddings, BM25 lexical retrieval, RRF fusion, and a heuristic reranker by default.

## Rationale

The project must run offline without paid API keys or model downloads. Hash embeddings are not semantic embeddings, so the UI and trace label them as `local_hash_embedding_fallback`. BM25 preserves exact error codes and exception identifiers. RRF makes dense and lexical signals comparable without calibration.

## Consequences

- Default retrieval is reproducible and testable.
- Semantic quality is limited until `sentence_transformers` is explicitly enabled.
- All outputs must expose dense, lexical, fusion, rerank, and final scores.
