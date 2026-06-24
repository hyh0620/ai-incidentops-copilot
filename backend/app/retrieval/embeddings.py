from typing import Protocol


class EmbeddingProvider(Protocol):
    provider: str
    dimension: int

    def encode(self, texts: list[str]):
        ...
