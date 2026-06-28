import time
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from tokenfinops.config import settings
from tokenfinops.gateway.schemas import ChatCompletionRequest, ChatCompletionResponse
from tokenfinops.engine.pipeline import RequestPipeline
from tokenfinops.engine.rate_limiter import RateLimiter
from tokenfinops.engine.prompt_optimizer import PromptOptimizer
from tokenfinops.engine.context_trimmer import ContextTrimmer
from tokenfinops.engine.model_router import ModelRouter
from tokenfinops.engine.cost_predictor import CostPredictor
from tokenfinops.engine.budget_manager import BudgetManager
from tokenfinops.engine.semantic_cache import semantic_cache
from tokenfinops.engine.smart_retry import SmartRetryEngine
from tokenfinops.providers.registry import provider_registry
from tokenfinops.models.usage import UsageRecord
from tokenfinops.observability.metrics import MetricsCollector

router = APIRouter()

# Instantiate core request processing pipeline
pipeline = RequestPipeline() \
    .add_stage(RateLimiter()) \
    .add_stage(PromptOptimizer()) \
    .add_stage(ContextTrimmer()) \
    .add_stage(ModelRouter()) \
    .add_stage(CostPredictor()) \
    .add_stage(BudgetManager()) \
    .add_stage(semantic_cache)

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint routed through the optimization pipeline."""
    # 1. Execute Request Pipeline
    ctx = await pipeline.execute(request)
    
    # 2. Check if request was aborted (e.g. rate limited or cache hit)
    if ctx.aborted:
        # Cache hit represents a successful abort
        if ctx.cache_hit and ctx.response:
            try:
                record = UsageRecord(
                    requested_model=request.model,
                    routed_model=ctx.request.model,
                    provider=ctx.response.cost_metadata.provider_used if ctx.response.cost_metadata else "cache",
                    input_tokens=ctx.response.usage.prompt_tokens,
                    output_tokens=ctx.response.usage.completion_tokens,
                    total_tokens=ctx.response.usage.total_tokens,
                    estimated_cost=ctx.estimated_cost,
                    actual_cost=0.0,
                    latency_ms=int(ctx.latency_ms),
                    cache_hit=True,
                    status="success"
                )
                ctx.db_session.add(record)
                await ctx.db_session.commit()
                
                # Record metrics
                MetricsCollector.record_request(
                    model=request.model,
                    provider="cache",
                    input_tokens=ctx.response.usage.prompt_tokens,
                    output_tokens=ctx.response.usage.completion_tokens,
                    cost=0.0,
                    latency_ms=ctx.latency_ms,
                    cache_hit=True,
                    status="success"
                )
                MetricsCollector.record_savings(
                    saved_tokens=ctx.response.usage.total_tokens,
                    optimization_type="caching"
                )
            except Exception:
                pass
            return ctx.response
            
        # Actual error abort
        raise HTTPException(
            status_code=ctx.abort_status_code,
            detail=ctx.abort_reason
        )

    # 3. Cache miss: Execute routed LLM Provider with Smart Failover/Retry
    routed_model = ctx.request.model
    provider_name = ctx.metadata.get("routed_provider", "openai")

    # Support standard non-streaming flow
    if not request.stream:
        try:
            start_time = time.perf_counter()
            # Run inference via retry/failover engine
            response = await SmartRetryEngine.execute(ctx.request, provider_name)
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Fetch model config to determine actual execution rates
            model_cfg = settings.models.get(routed_model)
            if model_cfg:
                input_cost = (response.usage.prompt_tokens / 1000) * model_cfg.cost_per_1k_input
                output_cost = (response.usage.completion_tokens / 1000) * model_cfg.cost_per_1k_output
                actual_cost = input_cost + output_cost
            else:
                actual_cost = 0.0

            # Update response metadata
            if response.cost_metadata:
                response.cost_metadata.actual_cost = actual_cost
                response.cost_metadata.latency_ms = latency_ms
                response.cost_metadata.routing_reason = ctx.metadata.get("routing_reason")
                response.cost_metadata.estimated_cost = ctx.estimated_cost

            # Record spent in budget manager if budget_id was specified
            if request.budget_id:
                await BudgetManager.record_actual_spend(ctx.db_session, request.budget_id, actual_cost)

            # Write cache in background
            prompt_text = "\n".join([m.content for m in request.messages])
            await semantic_cache.save_to_cache(prompt_text, routed_model, response, ctx.db_session)

            # Log usage record
            record = UsageRecord(
                requested_model=request.model,
                routed_model=routed_model,
                provider=provider_name,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                original_input_tokens=ctx.metadata.get("estimated_input_tokens"),
                tokens_saved=ctx.tokens_saved,
                estimated_cost=ctx.estimated_cost,
                actual_cost=actual_cost,
                latency_ms=int(latency_ms),
                cache_hit=False,
                status="success"
            )
            ctx.db_session.add(record)
            await ctx.db_session.commit()

            # Record metrics
            MetricsCollector.record_request(
                model=routed_model,
                provider=provider_name,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                cost=actual_cost,
                latency_ms=latency_ms,
                cache_hit=False,
                status="success"
            )
            if ctx.tokens_saved > 0:
                MetricsCollector.record_savings(
                    saved_tokens=ctx.tokens_saved,
                    optimization_type="prompt_optimization"
                )

            return response
        except Exception as e:
            # Log failure record
            try:
                record = UsageRecord(
                    requested_model=request.model,
                    routed_model=routed_model,
                    provider=provider_name,
                    status="error",
                    error_type=type(e).__name__
                )
                ctx.db_session.add(record)
                await ctx.db_session.commit()
                
                # Record failure metrics
                MetricsCollector.record_request(
                    model=routed_model,
                    provider=provider_name,
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    latency_ms=0.0,
                    cache_hit=False,
                    status="error"
                )
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Inference execution failed: {str(e)}")

    # Support streaming flow (streaming skips budget decrement and cache writing for simplicity in v1)
    try:
        provider = provider_registry.get_provider(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def stream_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in provider.stream(ctx.request):
                yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            err_msg = f"Stream failed: {str(e)}"
            yield f"data: {{\"error\": \"{err_msg}\"}}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )

@router.post("/chat/completions/estimate")
async def estimate_cost(request: ChatCompletionRequest):
    """Estimate cost of the query without executing the actual model call."""
    model_name = request.model
    model_config = settings.models.get(model_name)
    if not model_config:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' is not configured."
        )

    provider_name = model_config.provider
    try:
        provider = provider_registry.get_provider(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Calculate input tokens
    full_prompt = "\n".join([m.content for m in request.messages])
    input_tokens = provider.count_tokens(full_prompt, model_name)
    
    # Estimate output tokens using 0.7x ratio
    estimated_output_tokens = int(input_tokens * 0.7)
    if estimated_output_tokens < 50:
        estimated_output_tokens = 50
    
    est_input_cost = (input_tokens / 1000) * model_config.cost_per_1k_input
    est_output_cost = (estimated_output_tokens / 1000) * model_config.cost_per_1k_output
    total_est_cost = est_input_cost + est_output_cost

    return {
        "model": model_name,
        "provider": provider_name,
        "input_tokens": input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_input_cost": est_input_cost,
        "estimated_output_cost": est_output_cost,
        "estimated_total_cost": total_est_cost,
        "quality_tier": model_config.quality_tier
    }

@router.get("/models")
async def list_models():
    """List available models configured in config.yaml."""
    active_providers = provider_registry.list_active_providers()
    models_list = []
    
    for name, cfg in settings.models.items():
        if cfg.enabled and cfg.provider in active_providers:
            models_list.append({
                "id": name,
                "provider": cfg.provider,
                "quality_tier": cfg.quality_tier,
                "cost_per_1k_input": cfg.cost_per_1k_input,
                "cost_per_1k_output": cfg.cost_per_1k_output,
                "context_window": cfg.context_window,
                "capabilities": cfg.capabilities
            })
            
    return {"object": "list", "data": models_list}
