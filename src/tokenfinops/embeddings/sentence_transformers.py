import logging
import numpy as np
from tokenfinops.config import settings
from tokenfinops.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class SentenceTransformersProvider(EmbeddingProvider):
    provider_name: str = "sentence-transformers"
    # all-MiniLM-L6-v2 produces 384 dimensional vectors
    embedding_dim: int = 384

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            # Detect dimensions dynamically
            self.embedding_dim = self.model.get_sentence_embedding_dimension() or 384
        except ImportError as e:
            logger.error(
                "sentence-transformers is not installed. "
                "Please run: pip install tokenfinops[local-embeddings]"
            )
            raise e

    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        # sentence-transformers encode is synchronous; run it as is or in a thread pool
        # For simplicity and speed of in-process execution, we run it directly
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [np.array(emb, dtype=np.float32) for emb in embeddings]

    async def embed_single(self, text: str) -> np.ndarray:
        embeddings = await self.embed([text])
        return embeddings[0]

    @classmethod
    def from_env(cls) -> "SentenceTransformersProvider | None":
        # Always available if installed since it runs locally and downloads automatically
        if settings.EMBEDDING_PROVIDER == "sentence-transformers":
            model_name = settings.EMBEDDING_MODEL or "all-MiniLM-L6-v2"
            try:
                import sentence_transformers  # noqa: F401
                return cls(model_name=model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers package is requested in config but not installed."
                )
                return None
        return None
