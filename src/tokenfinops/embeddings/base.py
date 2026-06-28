from abc import ABC, abstractmethod
import numpy as np

class EmbeddingProvider(ABC):
    provider_name: str
    embedding_dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a list of text strings into vectors."""
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text string into a vector."""
        pass

    @classmethod
    @abstractmethod
    def from_env(cls) -> "EmbeddingProvider | None":
        """Initialize the embedding provider from settings/environment.
        Return None if the required environment variables are not set.
        """
        pass
