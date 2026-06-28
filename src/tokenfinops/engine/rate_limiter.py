import logging
import time
from redis import Redis
from tokenfinops.config import settings
from tokenfinops.engine.pipeline import PipelineStage, RequestContext

logger = logging.getLogger(__name__)

class RateLimiter(PipelineStage):
    """Pipeline stage that enforces requests-per-minute (RPM) limits per user/key using Redis sliding windows."""

    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def is_rate_limited(self, identifier: str, limit: int, window: int = 60) -> tuple[bool, int]:
        """Check if requests from the identifier exceed limits in the given window (in seconds).
        Returns (is_limited, remaining_tokens).
        """
        key = f"rate_limit:{identifier}"
        now = time.time()
        cutoff = now - window

        try:
            # Multi/exec transaction pipeline to clean old requests and count active ones
            pipe = self.redis.pipeline()
            # Remove timestamps older than window
            pipe.zremrangebyscore(key, 0, cutoff)
            # Count elements remaining
            pipe.zcard(key)
            # Add current timestamp
            pipe.zadd(key, {str(now): now})
            # Set TTL on key to auto-clean inactive clients
            pipe.expire(key, window * 2)
            
            results = pipe.execute()
            current_count = results[1]
            
            if current_count >= limit:
                # Limit reached, remove the entry we just added to keep size accurate
                self.redis.zrem(key, str(now))
                return True, 0
                
            return False, limit - current_count - 1
        except Exception as e:
            logger.error(f"Redis rate limiting lookup error: {e}. Passing check.")
            # Graceful failure: do not block traffic if Redis experiences temporary issues
            return False, limit

    async def process(self, ctx: RequestContext) -> RequestContext:
        # Determine client identity identifier: user parameter or fallback to global limit key
        user_id = ctx.request.user or "default_user"
        limit = settings.RATE_LIMIT_RPM

        is_limited, remaining = self.is_rate_limited(user_id, limit)
        ctx.metadata["rate_limit_remaining"] = remaining

        if is_limited:
            ctx.aborted = True
            ctx.abort_reason = f"Rate limit exceeded. Maximum allowed is {limit} requests per minute."
            ctx.abort_status_code = 429
            logger.warning(f"User '{user_id}' was rate limited.")
            
        return ctx
