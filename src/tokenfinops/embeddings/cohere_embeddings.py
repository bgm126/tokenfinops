import os
import logging
import httpx
import numpy as np
from tokenfinops.config import settings
from tokenfinops.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class CohereEmbeddingsProvider(EmbeddingProvider):
    provider_name: str = "cohere"

    def __init__(self, api_key: str, model_name: str = "embed-english-v3.0"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://api.cohere.com/v1"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(20.0, connect=5.0)
        )
        # Determine dimensions based on model name
        if "light" in model_name:
            self.embedding_dim = 384
        elif "multilingual" in model_name:
            self.embedding_dim = 1024
        else:
            self.embedding_dim = 1024  # embed-english-v3.0 is 1024 dim

    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        try:
            payload = {
                "texts": texts,
                "model": self.model_name,
                "input_type": "search_document"
            }
            response = await self.client.post(
                f"{self.base_url}/embed",
                json=payload
            )
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"Cohere Embeddings error: {response.text}",
                    request=response.request,
                    response=response
                )
            
            data = response.json()
            # Cohere v3 returns 'embeddings' under 'embeddings.float'
            # or directly 'embeddings' if v2
            emb_list = data.get("embeddings", [])
            if isinstance(emb_list, dict):
                emb_list = emb_list.get("float", [])
            
            return [np.array(item, dtype=np.float32) for item in emb_list]
        except Exception as e:
            logger.error(f"Error calling Cohere embeddings: {e}")
            raise e

    async def embed_single(self, text: str) -> np.ndarray:
        res = await self.embed([text])
        return res[0]

    @classmethod
    def from_env(cls) -> "CohereEmbeddingsProvider | None":
        # Cohere API key can be set in settings or directly in env COHERE_API_KEY
        cohere_key = os.environ.get("COHERE_API_KEY")
        if settings.EMBEDDING_PROVIDER == "cohere" and cohere_key:
            model_name = settings.EMBEDDING_MODEL or "embed-english-v3.0"
            return cls(api_key=cohere_key, model_name=model_name)
        return None
