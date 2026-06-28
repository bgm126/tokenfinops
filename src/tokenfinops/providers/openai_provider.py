import time
from typing import AsyncIterator
import httpx
import tiktoken
from tokenfinops.config import settings
from tokenfinops.gateway.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    Choice,
    ChoiceMessage,
    Usage,
    CostMetadata,
    StreamChoice,
    StreamChoiceDelta
)
from tokenfinops.providers.base import LLMProvider, ProviderHealth

class OpenAIProvider(LLMProvider):
    provider_name: str = "openai"

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(60.0, connect=5.0)
        )

    def _get_encoding_name(self, model: str) -> str:
        # GPT-4o uses o200k_base, older models use cl100k_base
        if "gpt-4o" in model:
            return "o200k_base"
        return "cl100k_base"

    def count_tokens(self, text: str, model: str) -> int:
        try:
            encoding_name = self._get_encoding_name(model)
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception:
            # Fallback character approximation
            return len(text) // 4

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        start_time = time.perf_counter()
        
        # Prepare OpenAI payloads (filtering custom fields)
        payload = request.model_dump(
            exclude={"budget_id", "routing_preference", "cache_policy"},
            exclude_none=True
        )

        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload
        )
        
        latency = (time.perf_counter() - start_time) * 1000
        
        if response.status_code != 200:
            raise httpx.HTTPStatusError(
                f"OpenAI error: {response.text}",
                request=response.request,
                response=response
            )

        data = response.json()
        
        # Extract inputs/outputs to construct usage
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", 0)
        
        choices = []
        for c in data.get("choices", []):
            msg = c.get("message", {})
            choices.append(
                Choice(
                    index=c.get("index", 0),
                    message=ChoiceMessage(
                        role=msg.get("role", "assistant"),
                        content=msg.get("content", "")
                    ),
                    finish_reason=c.get("finish_reason")
                )
            )

        # Estimate cost (can be updated by gateway pipeline)
        # Using simple pricing fallback, model_router updates it properly later
        cost_meta = CostMetadata(
            estimated_cost=0.0,
            actual_cost=0.0,
            model_used=request.model,
            provider_used=self.provider_name,
            latency_ms=latency
        )

        return ChatCompletionResponse(
            id=data.get("id", "unknown"),
            object="chat.completion",
            created=data.get("created", int(time.time())),
            model=request.model,
            choices=choices,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            ),
            cost_metadata=cost_meta
        )

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionStreamResponse]:
        payload = request.model_dump(
            exclude={"budget_id", "routing_preference", "cache_policy"},
            exclude_none=True
        )
        payload["stream"] = True

        req = self.client.build_request(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload
        )
        
        response = await self.client.send(req, stream=True)
        if response.status_code != 200:
            await response.aread()
            raise httpx.HTTPStatusError(
                f"OpenAI Stream error: {response.text}",
                request=req,
                response=response
            )

        # Yield stream chunks parsed from SSE
        # OpenAI stream data starts with "data: "
        async for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                
                try:
                    import json
                    chunk = json.loads(data_str)
                    
                    choices = []
                    for c in chunk.get("choices", []):
                        delta = c.get("delta", {})
                        choices.append(
                            StreamChoice(
                                index=c.get("index", 0),
                                delta=StreamChoiceDelta(
                                    role=delta.get("role"),
                                    content=delta.get("content", "")
                                ),
                                finish_reason=c.get("finish_reason")
                            )
                        )
                    
                    yield ChatCompletionStreamResponse(
                        id=chunk.get("id", "unknown"),
                        object="chat.completion.chunk",
                        created=chunk.get("created", int(time.time())),
                        model=request.model,
                        choices=choices,
                        usage=None
                    )
                except Exception:
                    continue

        await response.aclose()

    async def health_check(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            # Send a fast query to check connectivity
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
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
    def from_env(cls) -> "OpenAIProvider | None":
        if settings.OPENAI_API_KEY:
            return cls(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )
        return None
