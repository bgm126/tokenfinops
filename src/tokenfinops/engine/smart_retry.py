import asyncio
import logging
import time
from tokenfinops.config import settings
from tokenfinops.gateway.schemas import ChatCompletionRequest, ChatCompletionResponse
from tokenfinops.providers.registry import provider_registry

logger = logging.getLogger(__name__)

class SmartRetryEngine:
    """Retries failed completions on the primary provider, failing over to fallback providers if necessary."""

    @staticmethod
    def _get_fallback_model(current_provider: str, target_capabilities: list[str]) -> tuple[str, str] | None:
        # Scan configured models to find a model from a different, active provider
        active_providers = provider_registry.list_active_providers()
        
        for name, cfg in settings.models.items():
            if cfg.enabled and cfg.provider in active_providers and cfg.provider != current_provider:
                # Check if it matches at least one capability
                if any(cap in cfg.capabilities for cap in target_capabilities) or "general" in cfg.capabilities:
                    return name, cfg.provider
        return None

    @classmethod
    async def execute(cls, request: ChatCompletionRequest, primary_provider_name: str, max_retries: int = 2) -> ChatCompletionResponse:
        current_provider_name = primary_provider_name
        current_model = request.model
        
        attempt = 0
        backoff = 1.0  # seconds
        
        # Keep track of requested capabilities for potential model downgrades/fallbacks
        model_cfg = settings.models.get(current_model)
        target_capabilities = model_cfg.capabilities if model_cfg else ["general"]

        while True:
            try:
                provider = provider_registry.get_provider(current_provider_name)
                logger.info(f"Attempting completion on {current_provider_name}:{current_model} (attempt {attempt + 1})")
                
                start_time = time.perf_counter()
                response = await provider.complete(request)
                latency = (time.perf_counter() - start_time) * 1000
                
                # Success: record retry attempts in cost metadata if any failover occurred
                if response.cost_metadata:
                    response.cost_metadata.routing_reason = (
                        f"Resolved via {current_provider_name} after {attempt} retries/failovers."
                        if attempt > 0 else response.cost_metadata.routing_reason
                    )
                return response

            except Exception as e:
                attempt += 1
                logger.warning(
                    f"Failure executing request on provider '{current_provider_name}' with model '{current_model}': {e}"
                )

                # 1. Retry same provider with backoff for transient errors
                if attempt <= max_retries:
                    logger.info(f"Retrying transient error on same provider in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue

                # 2. Try failover to next active provider in the fallback chain
                fallback = cls._get_fallback_model(current_provider_name, target_capabilities)
                if fallback:
                    fallback_model, fallback_provider = fallback
                    logger.error(
                        f"All retries failed on '{current_provider_name}'. "
                        f"Initiating failover to fallback '{fallback_provider}' with model '{fallback_model}'..."
                    )
                    
                    # Update request model for fallback execution
                    request.model = fallback_model
                    current_provider_name = fallback_provider
                    current_model = fallback_model
                    attempt = 0  # reset attempts for the new provider
                    backoff = 1.0
                    continue
                
                # No more fallbacks available
                logger.error("All providers and failover options exhausted.")
                raise e
