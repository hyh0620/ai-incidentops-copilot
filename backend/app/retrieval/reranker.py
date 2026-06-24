from app.analysis.contracts import RetrievalCandidate
from app.retrieval.tokenizer import tokenize


class HeuristicReranker:
    provider = "heuristic_reranker"

    def rerank(self, query: str, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        query_tokens = set(tokenize(query))
        for candidate in candidates:
            chunk_tokens = set(tokenize(candidate.excerpt))
            exact_bonus = 0.05 * len(query_tokens & chunk_tokens)
            candidate.rerank_score = round(candidate.fusion_score + exact_bonus, 6)
            candidate.ranking_stage = "heuristic_rerank"
        return sorted(candidates, key=lambda item: item.rerank_score or item.fusion_score, reverse=True)
