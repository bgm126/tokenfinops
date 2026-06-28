from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel
from tokenfinops.gateway.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionStreamResponse

class ProviderHealth(BaseModel):
    is_healthy: bool
    latency_ms: float = 0.0
    error_message: str | None = None

class LLMProvider(ABC):
    provider_name: str

    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute a non-streaming chat completion request."""
        pass

    @abstractmethod
    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionStreamResponse]:
        """Execute a streaming chat completion request."""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider health and return current status."""
        pass

    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens in a string for a given model."""
        pass

    @classmethod
    @abstractmethod
    def from_env(cls) -> "LLMProvider | None":
        """Initialize the provider from settings/environment.
        Return None if the required environment variables are not set.
        """
        pass
