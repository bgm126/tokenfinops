from tokenfinops.config import settings
from tokenfinops.providers.openai_provider import OpenAIProvider

class VLLMProvider(OpenAIProvider):
    provider_name: str = "vllm"

    def __init__(self, base_url: str):
        # vLLM is fully OpenAI-compatible
        super().__init__(api_key="vllm-token", base_url=base_url)

    @classmethod
    def from_env(cls) -> "VLLMProvider | None":
        if settings.VLLM_BASE_URL:
            return cls(base_url=settings.VLLM_BASE_URL)
        return None
