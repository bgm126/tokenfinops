import re
import logging
from tokenfinops.config import settings
from tokenfinops.engine.pipeline import PipelineStage, RequestContext

logger = logging.getLogger(__name__)

class PromptOptimizer(PipelineStage):
    """Pipeline stage that compresses instructions and removes excess characters from prompts to reduce inputs cost."""

    def optimize_text(self, text: str) -> tuple[str, int]:
        original_len = len(text)
        
        # 1. Whitespace normalization: convert multi-spaces/tabs to single space
        text = re.sub(r"[ \t]+", " ", text)
        
        # 2. Normalize excess consecutive empty newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # 3. Strip verbose conversational prefixes (frequent in assistant prompts)
        prefixes_to_strip = [
            r"^(please|kindly)\s+(answer|respond|tell\s+me)\s+(to\s+)?",
            r"^as\s+an\s+ai\s+language\s+model,\s*",
            r"^i\s+want\s+you\s+to\s+act\s+as\s+a\s+"
        ]
        for pattern in prefixes_to_strip:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        saved_chars = original_len - len(text)
        # Approximate tokens saved (4 chars per token)
        tokens_saved = saved_chars // 4
        return text.strip(), max(tokens_saved, 0)

    async def process(self, ctx: RequestContext) -> RequestContext:
        if not settings.ENABLE_PROMPT_OPTIMIZATION:
            return ctx

        total_saved_tokens = 0
        for msg in ctx.request.messages:
            if msg.role in ["user", "system"]:
                optimized_content, saved_tokens = self.optimize_text(msg.content)
                if saved_tokens > 0:
                    msg.content = optimized_content
                    total_saved_tokens += saved_tokens
        
        if total_saved_tokens > 0:
            ctx.tokens_saved += total_saved_tokens
            ctx.metadata["prompt_optimizer_tokens_saved"] = total_saved_tokens
            logger.info(f"Prompt Optimizer compressed inputs. Estimated savings: {total_saved_tokens} tokens.")
            
        return ctx
