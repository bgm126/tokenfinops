import logging
from dataclasses import dataclass, field
from tokenfinops.config import settings, ModelConfig
from tokenfinops.engine.pipeline import PipelineStage, RequestContext
from tokenfinops.providers.registry import provider_registry

logger = logging.getLogger(__name__)

@dataclass
class RoutingDecision:
    selected_model: str
    selected_provider: str
    estimated_cost: float
    reasoning: str
    alternatives: list[str] = field(default_factory=list)

class ModelRouter(PipelineStage):
    """Pipeline stage that selects the most optimal model based on cost, quality, and constraints."""

    def _determine_task_type(self, prompt_text: str) -> str:
        prompt_lower = prompt_text.lower()
        
        # Simple heuristic classification
        if any(marker in prompt_lower for marker in ["def ", "class ", "import ", "function ", "const ", "<html>", "python"]):
            return "coding"
        elif any(marker in prompt_lower for marker in ["translate", "spanish", "french", "german", "chinese", "translation"]):
            return "translation"
        elif any(marker in prompt_lower for marker in ["why", "explain", "how do i", "prove", "solve"]):
            return "reasoning"
        elif len(prompt_text.split()) < 10:
            return "classification"
        return "general"

    def make_routing_decision(
        self, 
        requested_model: str, 
        prompt_text: str, 
        strategy: str | None = None
    ) -> RoutingDecision:
        strategy = strategy or settings.DEFAULT_ROUTING_STRATEGY
        task_type = self._determine_task_type(prompt_text)
        
        # If model routing is disabled, stick to requested model
        if not settings.ENABLE_MODEL_ROUTING:
            model_cfg = settings.models.get(requested_model)
            if not model_cfg:
                raise ValueError(f"Requested model '{requested_model}' not found in configuration.")
            return RoutingDecision(
                selected_model=requested_model,
                selected_provider=model_cfg.provider,
                estimated_cost=0.0,
                reasoning="Routing disabled; using requested model."
            )

        # Get list of enabled and active models
        active_providers = provider_registry.list_active_providers()
        candidate_models = {
            name: cfg for name, cfg in settings.models.items()
            if cfg.enabled and cfg.provider in active_providers
        }

        if not candidate_models:
            raise ValueError("No active LLM providers configured. Verify your .env API keys.")

        # Find models matching the task requirements
        viable_candidates = []
        for name, cfg in candidate_models.items():
            if task_type in cfg.capabilities or "general" in cfg.capabilities:
                viable_candidates.append((name, cfg))

        if not viable_candidates:
            # Fallback to all enabled models
            viable_candidates = list(candidate_models.items())

        # Sort candidates based on routing strategy
        if strategy == "lowest_cost":
            # Sort by cheapest input cost
            viable_candidates.sort(key=lambda x: x[1].cost_per_1k_input)
            reasoning = f"Routed to cheapest model supporting task: '{task_type}'"
        elif strategy == "best_quality":
            # Premium models first
            tier_priority = {"premium": 0, "standard": 1, "economy": 2}
            viable_candidates.sort(key=lambda x: tier_priority.get(x[1].quality_tier, 1))
            reasoning = f"Routed to highest quality model supporting task: '{task_type}'"
        else: # "balanced"
            # Sort by balanced heuristics: if coding/reasoning, prefer standard/premium. Else economy.
            if task_type in ["coding", "reasoning"]:
                # Premium/standard first
                tier_priority = {"premium": 0, "standard": 1, "economy": 2}
                viable_candidates.sort(key=lambda x: tier_priority.get(x[1].quality_tier, 1))
                reasoning = f"Balanced strategy routed task '{task_type}' to quality model"
            else:
                # Economy first
                tier_priority = {"economy": 0, "standard": 1, "premium": 2}
                viable_candidates.sort(key=lambda x: tier_priority.get(x[1].quality_tier, 1))
                reasoning = f"Balanced strategy routed task '{task_type}' to economical model"

        selected_name, selected_cfg = viable_candidates[0]
        alternatives = [name for name, _ in viable_candidates[1:]]

        return RoutingDecision(
            selected_model=selected_name,
            selected_provider=selected_cfg.provider,
            estimated_cost=0.0,  # Populate when calling cost predictor
            reasoning=reasoning,
            alternatives=alternatives
        )

    async def process(self, ctx: RequestContext) -> RequestContext:
        prompt_text = "\n".join([m.content for m in ctx.request.messages])
        strategy = ctx.request.routing_preference
        
        try:
            decision = self.make_routing_decision(
                requested_model=ctx.request.model,
                prompt_text=prompt_text,
                strategy=strategy
            )
            ctx.routing_decision = decision
            
            # Rewrite requested model to optimized model
            ctx.request.model = decision.selected_model
            ctx.metadata["routed_provider"] = decision.selected_provider
            ctx.metadata["routing_reason"] = decision.reasoning
            logger.info(f"Model Router decision: {ctx.request.model} via {decision.selected_provider}. Reason: {decision.reasoning}")
        except Exception as e:
            ctx.aborted = True
            ctx.abort_reason = f"Routing failed: {str(e)}"
            ctx.abort_status_code = 400
            
        return ctx
