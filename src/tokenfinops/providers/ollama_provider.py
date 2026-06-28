import time
from typing import AsyncIterator
import httpx
from tokenfinops.config import settings
from tokenfinops.gateway.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse
)
from tokenfinops.providers.base import ProviderHealth
from tokenfinops.providers.openai_provider import OpenAIProvider

class OllamaProvider(OpenAIProvider):
    provider_name: str = "ollama"

    def __init__(self, base_url: str):
        # Ollama has an OpenAI-compatible endpoint under /v1
        super().__init__(api_key="ollama", base_url=f"{base_url}/v1")
        self.raw_base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=5.0)
        )

    def count_tokens(self, text: str, model: str) -> int:
        # Local model token counting approximation
        # We can use tiktoken's cl100k_base which is a good heuristic
        return super().count_tokens(text, "gpt-3.5-turbo")

    async def health_check(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            # Query Ollama native health/tags endpoint
            response = await self.client.get(f"{self.raw_base_url}/api/tags", timeout=5.0)
            latency = (time.perf_counter() - start_time) * 1000
            if response.status_code == 200:
                return ProviderHealth(is_healthy=True, latency_ms=latency)
            return ProviderHealth(
                is_healthy=False,
                latency_ms=latency,
                error_message=f"Status code {response.status_code}: {response.text}"
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ProviderHealth(is_healthy=False, latency_ms=latency, error_message=str(e))

    @classmethod
    def from_env(cls) -> "OllamaProvider | None":
        if settings.OLLAMA_BASE_URL:
            return cls(base_url=settings.OLLAMA_BASE_URL)
        return None
