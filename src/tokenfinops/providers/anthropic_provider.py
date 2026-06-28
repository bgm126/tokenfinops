import json
import time
from typing import Any, AsyncIterator
import httpx
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

class AnthropicProvider(LLMProvider):
    provider_name: str = "anthropic"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.client = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            timeout=httpx.Timeout(60.0, connect=5.0)
        )

    def count_tokens(self, text: str, model: str) -> int:
        # Approximate: Anthropic tokens are ~4 characters or slightly more
        return len(text) // 4

    def _convert_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        messages = []
        system_prompt = None
        
        for msg in request.messages:
            if msg.role == "system":
                # System prompt must go to the top level 'system' param in Anthropic API
                system_prompt = msg.content
            else:
                role = "assistant" if msg.role == "assistant" else "user"
                messages.append({"role": role, "content": msg.content})

        # Anthropic requires max_tokens
        max_tokens = request.max_tokens or 4096

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            payload["system"] = system_prompt
        if request.temperature is not None:
            # Map temperature (OpenAI is 0-2, Anthropic is 0-1)
            payload["temperature"] = min(max(request.temperature / 2, 0.0), 1.0)
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        
        return payload

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        start_time = time.perf_counter()
        
        payload = self._convert_request(request)
        
        response = await self.client.post(
            f"{self.base_url}/messages",
            json=payload
        )
        
        latency = (time.perf_counter() - start_time) * 1000
        
        if response.status_code != 200:
            raise httpx.HTTPStatusError(
                f"Anthropic error: {response.text}",
                request=response.request,
                response=response
            )

        data = response.json()
        
        # Anthropic response fields
        content_blocks = data.get("content", [])
        text_content = "".join([block.get("text", "") for block in content_blocks if block.get("type") == "text"])
        
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens

        choices = [
            Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content=text_content),
                finish_reason=data.get("stop_reason")
            )
        ]

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
            created=int(time.time()),
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
        payload = self._convert_request(request)
        payload["stream"] = True

        req = self.client.build_request(
            "POST",
            f"{self.base_url}/messages",
            json=payload
        )
        
        response = await self.client.send(req, stream=True)
        if response.status_code != 200:
            await response.aread()
            raise httpx.HTTPStatusError(
                f"Anthropic Stream error: {response.text}",
                request=req,
                response=response
            )

        # Anthropic server-sent events:
        # data format uses events: 'message_start', 'content_block_start', 'content_block_delta', 'content_block_stop', 'message_delta', 'message_stop'
        async for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:].strip()
                try:
                    event_data = json.loads(data_str)
                    event_type = event_data.get("type")
                    
                    if event_type == "content_block_delta":
                        delta = event_data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            
                            yield ChatCompletionStreamResponse(
                                id="anthropic-stream-id",
                                object="chat.completion.chunk",
                                created=int(time.time()),
                                model=request.model,
                                choices=[
                                    StreamChoice(
                                        index=0,
                                        delta=StreamChoiceDelta(role="assistant", content=text),
                                        finish_reason=None
                                    )
                                ]
                            )
                    elif event_type == "message_stop":
                        break
                except Exception:
                    continue

        await response.aclose()

    async def health_check(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            # Quick health probe: prompt with 1 max token
            payload = {
                "model": "claude-3-haiku-20240307",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            response = await self.client.post(
                f"{self.base_url}/messages",
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
    def from_env(cls) -> "AnthropicProvider | None":
        if settings.ANTHROPIC_API_KEY:
            return cls(api_key=settings.ANTHROPIC_API_KEY)
        return None
