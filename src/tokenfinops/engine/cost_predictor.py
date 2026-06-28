import logging
from dataclasses import dataclass
from tokenfinops.config import settings
from tokenfinops.engine.pipeline import PipelineStage, RequestContext
from tokenfinops.providers.registry import provider_registry

logger = logging.getLogger(__name__)

@dataclass
class CostEstimate:
    input_tokens: int
    estimated_output_tokens: int
    estimated_cost: float
    confidence: float

class CostPredictor(PipelineStage):
    """Pipeline stage that estimates prompt tokens and potential costs before call execution."""

    def predict_cost(self, prompt_text: str, model_name: str) -> CostEstimate:
        model_cfg = settings.models.get(model_name)
        if not model_cfg:
            logger.warning(f"Model {model_name} not found in model catalog. Defaulting to free rates.")
            return CostEstimate(input_tokens=0, estimated_output_tokens=0, estimated_cost=0.0, confidence=0.5)

        # Get tokenizer logic from provider
        try:
            provider = provider_registry.get_provider(model_cfg.provider)
            input_tokens = provider.count_tokens(prompt_text, model_name)
        except Exception:
            # Fallback heuristic
            input_tokens = len(prompt_text) // 4

        # Output estimation heuristic: standard chat prompt usually requests answers ~0.7x prompt length
        # unless specific context parameters are set.
        estimated_output_tokens = int(input_tokens * 0.7)
        if estimated_output_tokens < 50:
            estimated_output_tokens = 50

        # Calculate costs based on model catalog rates
        input_cost = (input_tokens / 1000) * model_cfg.cost_per_1k_input
        output_cost = (estimated_output_tokens / 1000) * model_cfg.cost_per_1k_output
        estimated_cost = input_cost + output_cost

        return CostEstimate(
            input_tokens=input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_cost=estimated_cost,
            confidence=0.8
        )

    async def process(self, ctx: RequestContext) -> RequestContext:
        if not settings.ENABLE_MODEL_ROUTING and not settings.ENABLE_BUDGET_ENFORCEMENT:
            return ctx

        # Construct prompt text to size
        prompt_text = "\n".join([m.content for m in ctx.request.messages])
        
        estimate = self.predict_cost(prompt_text, ctx.request.model)
        ctx.estimated_cost = estimate.estimated_cost
        ctx.metadata["estimated_input_tokens"] = estimate.input_tokens
        ctx.metadata["estimated_output_tokens"] = estimate.estimated_output_tokens
        ctx.metadata["cost_estimate_confidence"] = estimate.confidence

        logger.info(f"Cost estimation for model {ctx.request.model}: ${estimate.estimated_cost:.6f} ({estimate.input_tokens} input tokens)")
        return ctx
