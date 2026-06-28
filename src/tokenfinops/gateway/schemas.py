from typing import Any, Literal
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    name: str | None = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    user: str | None = None
    
    # Custom TokenFinOps extensions
    budget_id: str | None = None
    routing_preference: Literal["lowest_cost", "best_quality", "balanced", "budget_aware"] | None = "balanced"
    cache_policy: Literal["always", "never", "auto"] | None = "auto"

class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str

class Choice(BaseModel):
    index: int
    message: ChoiceMessage
    finish_reason: str | None = None

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class CostMetadata(BaseModel):
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    model_used: str
    provider_used: str
    cache_hit: bool = False
    tokens_saved: int = 0
    latency_ms: float = 0.0
    routing_reason: str | None = None

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
    cost_metadata: CostMetadata | None = None

# Streaming response schemas
class StreamChoiceDelta(BaseModel):
    role: str | None = None
    content: str | None = ""

class StreamChoice(BaseModel):
    index: int
    delta: StreamChoiceDelta
    finish_reason: str | None = None

class ChatCompletionStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    usage: Usage | None = None
    cost_metadata: CostMetadata | None = None
