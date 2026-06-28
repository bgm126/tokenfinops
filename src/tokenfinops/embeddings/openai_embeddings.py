import logging
import httpx
import numpy as np
from tokenfinops.config import settings
from tokenfinops.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class OpenAIEmbeddingsProvider(EmbeddingProvider):
    provider_name: str = "openai"

    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small", base_url: str | None = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(20.0, connect=5.0)
        )
        # Determine dimensions based on model name
        if "text-embedding-3-large" in model_name:
            self.embedding_dim = 3072
        else:
            self.embedding_dim = 1536

    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        try:
            payload = {
                "input": texts,
                "model": self.model_name
            }
            response = await self.client.post(
                f"{self.base_url}/embeddings",
                json=payload
            )
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"OpenAI Embeddings error: {response.text}",
                    request=response.request,
                    response=response
                )
            
            data = response.json()
            # Sort by index to maintain ordering
            sorted_data = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            return [np.array(item["embedding"], dtype=np.float32) for item in sorted_data]
        except Exception as e:
            logger.error(f"Error calling OpenAI embeddings: {e}")
            raise e

    async def embed_single(self, text: str) -> np.ndarray:
        res = await self.embed([text])
        return res[0]

    @classmethod
    def from_env(cls) -> "OpenAIEmbeddingsProvider | None":
        if settings.EMBEDDING_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            model_name = settings.EMBEDDING_MODEL or "text-embedding-3-small"
            return cls(
                api_key=settings.OPENAI_API_KEY,
                model_name=model_name,
                base_url=settings.OPENAI_BASE_URL
            )
        return None
