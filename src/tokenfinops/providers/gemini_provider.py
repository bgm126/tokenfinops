import time
import httpx
from tokenfinops.config import settings
from tokenfinops.providers.base import ProviderHealth
from tokenfinops.providers.openai_provider import OpenAIProvider

class GeminiProvider(OpenAIProvider):
    provider_name: str = "gemini"

    def __init__(self, api_key: str):
        # Gemini provides OpenAI compatibility endpoint
        # https://generativelanguage.googleapis.com/v1beta/openai/v1
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/v1"
        super().__init__(api_key=api_key, base_url=base_url)

    def count_tokens(self, text: str, model: str) -> int:
        # Gemini uses custom tokenizers but cl100k_base or simple len(text)/4 is a standard approximation
        return super().count_tokens(text, "gpt-3.5-turbo")

    async def health_check(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            # Check model listing or completion
            response = await self.client.get(
                f"{self.base_url}/models",
                timeout=5.0
            )
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
    def from_env(cls) -> "GeminiProvider | None":
        if settings.GEMINI_API_KEY:
            return cls(api_key=settings.GEMINI_API_KEY)
        return None
