import hashlib
import logging
from tokenfinops.gateway.schemas import ChatCompletionRequest

logger = logging.getLogger(__name__)

class KVCacheManager:
    """Tracks shared system prompts and instruction prefixes to optimize self-hosted vLLM KV cache reuse."""

    def __init__(self):
        # Maps SHA256 hashes of prefixes to active hit counts
        self._prefix_hits: dict[str, int] = {}

    def process_and_track_prefix(self, request: ChatCompletionRequest) -> tuple[bool, int]:
        """Verify if the initial instruction/system message matches a known prefix.
        Returns (is_prefix_cached, estimated_saved_tokens).
        """
        messages = request.messages
        if not messages or messages[0].role != "system":
            return False, 0

        system_content = messages[0].content
        # We only cache/track prefixes of substantial size (e.g. system instructions > 200 chars)
        if len(system_content) < 200:
            return False, 0

        prefix_hash = hashlib.sha256(system_content.encode("utf-8")).hexdigest()
        
        # Approximate tokens in system prompt (4 chars per token)
        prefix_tokens = len(system_content) // 4

        if prefix_hash in self._prefix_hits:
            self._prefix_hits[prefix_hash] += 1
            logger.info(f"KV Cache match! Reusing system prompt prefix ({prefix_tokens} tokens).")
            return True, prefix_tokens

        # Register new prefix
        self._prefix_hits[prefix_hash] = 1
        logger.debug(f"Registered new system prompt prefix ({prefix_tokens} tokens) for KV tracking.")
        return False, 0

# Global KV cache tracker instance
kv_cache_manager = KVCacheManager()
