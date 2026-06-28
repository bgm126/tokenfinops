from tokenfinops.config import settings
from tokenfinops.providers.openai_provider import OpenAIProvider

class OpenRouterProvider(OpenAIProvider):
    provider_name: str = "openrouter"

    def __init__(self, api_key: str):
        # OpenRouter uses standard OpenAI-compatible API format
        super().__init__(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    @classmethod
    def from_env(cls) -> "OpenRouterProvider | None":
        if settings.OPENROUTER_API_KEY:
            return cls(api_key=settings.OPENROUTER_API_KEY)
        return None
