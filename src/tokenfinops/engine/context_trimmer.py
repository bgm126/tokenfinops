import logging
from tokenfinops.config import settings
from tokenfinops.engine.pipeline import PipelineStage, RequestContext
from tokenfinops.embeddings.registry import embedding_registry
from tokenfinops.providers.registry import provider_registry
import numpy as np

logger = logging.getLogger(__name__)

class ContextTrimmer(PipelineStage):
    """Pipeline stage that monitors and trims prompt context size to avoid context limit overflow and save cost."""

    def __init__(self):
        self.max_tokens_threshold = 4000  # Default target limit if model context window is large

    async def trim_context(self, request, model_limit: int, provider) -> int:
        messages = request.messages
        if len(messages) <= 4:
            return 0  # Not enough messages to prune safely

        # Calculate current total tokens
        prompt_text = "\n".join([m.content for m in messages])
        total_tokens = provider.count_tokens(prompt_text, request.model)
        
        # Determine ceiling (80% of model limit, or global default)
        target_max = min(int(model_limit * 0.8), self.max_tokens_threshold)
        
        if total_tokens <= target_max:
            return 0

        logger.info(f"Context size ({total_tokens} tokens) exceeds target limit ({target_max} tokens). Trimming...")

        # Keep system prompt (index 0 if exists)
        system_prompt = None
        if messages[0].role == "system":
            system_prompt = messages[0]
            chat_history = messages[1:]
        else:
            chat_history = messages

        # Always retain last 3 messages (latest history context)
        essential_tail = chat_history[-3:]
        intermediate_history = chat_history[:-3]

        if not intermediate_history:
            return 0

        # Run semantic pruning using embedding similarity to the last user message
        try:
            embedder = embedding_registry.get_active_provider()
            query_vector = await embedder.embed_single(messages[-1].content)
            query_vector = np.array(query_vector, dtype=np.float32)

            scored_messages = []
            for msg in intermediate_history:
                msg_vector = await embedder.embed_single(msg.content)
                msg_vector = np.array(msg_vector, dtype=np.float32)
                # Compute simple cosine similarity
                similarity = np.dot(query_vector, msg_vector) / (np.linalg.norm(query_vector) * np.linalg.norm(msg_vector) + 1e-9)
                scored_messages.append((similarity, msg))

            # Sort by similarity desc and keep top 50%
            scored_messages.sort(key=lambda x: x[0], reverse=True)
            keep_count = max(len(scored_messages) // 2, 1)
            retained_intermediates = [item[1] for item in scored_messages[:keep_count]]
            
            # Rebuild original ordering
            retained_intermediates.sort(key=lambda x: intermediate_history.index(x))
            
            # Reconstruct request message list
            new_messages = []
            if system_prompt:
                new_messages.append(system_prompt)
            new_messages.extend(retained_intermediates)
            new_messages.extend(essential_tail)
            
            original_count = len(request.messages)
            request.messages = new_messages
            
            new_prompt_text = "\n".join([m.content for m in new_messages])
            new_total = provider.count_tokens(new_prompt_text, request.model)
            
            saved = total_tokens - new_total
            logger.info(f"Trimmed {original_count - len(new_messages)} messages. Saved {saved} tokens.")
            return saved
        except Exception as e:
            logger.error(f"Semantic context trimming failed: {e}. Falling back to chronological prune.")
            # Fallback: simple slice of latest items
            new_messages = []
            if system_prompt:
                new_messages.append(system_prompt)
            new_messages.extend(chat_history[-5:])
            request.messages = new_messages
            return 0

    async def process(self, ctx: RequestContext) -> RequestContext:
        model_name = ctx.request.model
        model_cfg = settings.models.get(model_name)
        if not model_cfg:
            return ctx

        try:
            provider = provider_registry.get_provider(model_cfg.provider)
            saved = await self.trim_context(
                request=ctx.request,
                model_limit=model_cfg.context_window,
                provider=provider
            )
            if saved > 0:
                ctx.tokens_saved += saved
                ctx.metadata["context_trimmer_tokens_saved"] = saved
        except Exception as e:
            logger.warning(f"Context trimming stage skipped: {e}")
            
        return ctx
