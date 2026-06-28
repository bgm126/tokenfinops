import logging
import httpx
import numpy as np
from tokenfinops.config import settings
from tokenfinops.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class OllamaEmbeddingsProvider(EmbeddingProvider):
    provider_name: str = "ollama"

    def __init__(self, base_url: str, model_name: str = "nomic-embed-text"):
        self.base_url = base_url
        self.model_name = model_name
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0)
        )
        self.embedding_dim = 768  # nomic-embed-text default. Will auto-detect on first query if different.
        self._dim_detected = False

    async def _detect_dimension_and_verify(self, sample_embedding: list[float]) -> None:
        if not self._dim_detected:
            self.embedding_dim = len(sample_embedding)
            self._dim_detected = True

    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        try:
            # Try newer /api/embed endpoint first
            payload = {
                "model": self.model_name,
                "input": texts
            }
            response = await self.client.post(
                f"{self.base_url}/api/embed",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    await self._detect_dimension_and_verify(embeddings[0])
                return [np.array(item, dtype=np.float32) for item in embeddings]

            # Fallback to older /api/embeddings endpoint (run sequentially since it only accepts one prompt)
            embeddings = []
            for text in texts:
                single_payload = {
                    "model": self.model_name,
                    "prompt": text
                }
                single_res = await self.client.post(
                    f"{self.base_url}/api/embeddings",
                    json=single_payload
                )
                if single_res.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Ollama Embeddings fallback failed: {single_res.text}",
                        request=single_res.request,
                        response=single_res
                    )
                data = single_res.json()
                emb = data.get("embedding", [])
                await self._detect_dimension_and_verify(emb)
                embeddings.append(np.array(emb, dtype=np.float32))
            
            return embeddings
        except Exception as e:
            logger.error(f"Error calling Ollama embeddings: {e}")
            raise e

    async def embed_single(self, text: str) -> np.ndarray:
        res = await self.embed([text])
        return res[0]

    @classmethod
    def from_env(cls) -> "OllamaEmbeddingsProvider | None":
        if settings.EMBEDDING_PROVIDER == "ollama" and settings.OLLAMA_BASE_URL:
            model_name = settings.EMBEDDING_MODEL or "nomic-embed-text"
            return cls(base_url=settings.OLLAMA_BASE_URL, model_name=model_name)
        return None
