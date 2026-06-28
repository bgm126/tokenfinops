from dataclasses import dataclass, field
import time
from typing import Any, Callable, Type
from sqlalchemy.ext.asyncio import AsyncSession
from tokenfinops.gateway.schemas import ChatCompletionRequest, ChatCompletionResponse
from tokenfinops.models.base import SessionLocal

@dataclass
class RequestContext:
    request: ChatCompletionRequest
    db_session: AsyncSession
    start_time: float = field(default_factory=time.perf_counter)
    response: ChatCompletionResponse | None = None
    cache_hit: bool = False
    tokens_saved: int = 0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    latency_ms: float = 0.0
    routing_decision: Any = None  # Will hold RoutingDecision object
    metadata: dict[str, Any] = field(default_factory=dict)
    aborted: bool = False
    abort_reason: str | None = None
    abort_status_code: int = 400

class PipelineStage:
    async def process(self, ctx: RequestContext) -> RequestContext:
        """Run step within request pipeline. Return modified context."""
        return ctx

class RequestPipeline:
    def __init__(self):
        self._stages: list[PipelineStage] = []

    def add_stage(self, stage: PipelineStage) -> "RequestPipeline":
        self._stages.append(stage)
        return self

    async def execute(self, request: ChatCompletionRequest) -> RequestContext:
        """Execute request context through configured pipeline stages."""
        async with SessionLocal() as session:
            ctx = RequestContext(request=request, db_session=session)
            
            for stage in self._stages:
                if ctx.aborted:
                    break
                try:
                    ctx = await stage.process(ctx)
                except Exception as e:
                    ctx.aborted = True
                    ctx.abort_reason = f"Pipeline execution failed at stage {stage.__class__.__name__}: {str(e)}"
                    ctx.abort_status_code = 500
                    break
            
            ctx.latency_ms = (time.perf_counter() - ctx.start_time) * 1000
            return ctx
