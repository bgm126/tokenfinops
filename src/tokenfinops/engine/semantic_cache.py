import hashlib
import json
import logging
from datetime import datetime, timezone
import faiss
import numpy as np
from redis import Redis
from sqlalchemy import select
from tokenfinops.config import settings
from tokenfinops.embeddings.registry import embedding_registry
from tokenfinops.engine.pipeline import PipelineStage, RequestContext
from tokenfinops.gateway.schemas import ChatCompletionResponse, Choice, ChoiceMessage, Usage, CostMetadata
from tokenfinops.models.cache_entry import DBCacheEntry

logger = logging.getLogger(__name__)

class SemanticCache(PipelineStage):
    """Pipeline stage implementing L1 Exact Cache and L2 Semantic Cache."""

    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.embedding_provider = None
        self.faiss_index = None
        self.db_ids = []
        self._initialized = False

    def _init_semantic_search(self, dim: int):
        # Cosine similarity index using Flat Inner Product (requires vectors to be L2 normalized)
        self.faiss_index = faiss.IndexFlatIP(dim)
        self._initialized = True

    async def initialize_cache_from_db(self, db_session):
        """Pre-load historical cache entries from DB into local FAISS index."""
        if not settings.ENABLE_SEMANTIC_CACHE:
            return

        try:
            self.embedding_provider = embedding_registry.get_active_provider()
            dim = self.embedding_provider.embedding_dim
            self._init_semantic_search(dim)
        except Exception as e:
            logger.error(f"Failed to load embedding provider for semantic cache: {e}. Semantic cache disabled.")
            return

        try:
            # Query all cache entries
            stmt = select(DBCacheEntry)
            result = await db_session.execute(stmt)
            entries = result.scalars().all()
            
            vectors = []
            for entry in entries:
                vec = np.array(entry.embedding, dtype=np.float32)
                # L2 normalize vector for cosine similarity
                faiss.normalize_L2(vec.reshape(1, -1))
                vectors.append(vec)
                self.db_ids.append(entry.id)

            if vectors:
                vectors_np = np.vstack(vectors)
                self.faiss_index.add(vectors_np)
                logger.info(f"Preloaded {len(vectors)} semantic cache entries into FAISS index.")
        except Exception as e:
            logger.error(f"Error preloading cache entries from DB: {e}")

    def _get_exact_key(self, prompt_text: str, model_name: str) -> str:
        # Create SHA256 hash of model + prompt text
        hasher = hashlib.sha256()
        hasher.update(f"{model_name}:{prompt_text}".encode("utf-8"))
        return f"cache:exact:{hasher.hexdigest()}"

    async def get_cached_response(self, prompt_text: str, model_name: str, db_session) -> tuple[ChatCompletionResponse | None, float | None]:
        # 1. Try L1 exact match in Redis
        exact_key = self._get_exact_key(prompt_text, model_name)
        try:
            cached_data = self.redis.get(exact_key)
            if cached_data:
                logger.info("L1 Exact Cache hit!")
                res_dict = json.loads(cached_data)
                return ChatCompletionResponse(**res_dict), 1.0
        except Exception as e:
            logger.warning(f"Redis L1 cache read failed: {e}")

        # 2. Try L2 semantic match via FAISS
        if not self._initialized or not self.faiss_index or self.faiss_index.ntotal == 0:
            return None, None

        try:
            query_vector = await self.embedding_provider.embed_single(prompt_text)
            query_vector = np.array(query_vector, dtype=np.float32).reshape(1, -1)
            faiss.normalize_L2(query_vector)
            
            # Query the single nearest neighbor
            D, I = self.faiss_index.search(query_vector, 1)
            similarity = float(D[0][0])
            idx = int(I[0][0])
            
            if idx != -1 and similarity >= settings.CACHE_SIMILARITY_THRESHOLD:
                db_id = self.db_ids[idx]
                entry = await db_session.get(DBCacheEntry, db_id)
                if entry:
                    logger.info(f"L2 Semantic Cache hit! Similarity: {similarity:.4f}")
                    # Update hit count asynchronously (fire and forget in background)
                    entry.hit_count += 1
                    await db_session.commit()
                    
                    return ChatCompletionResponse(**entry.response_json), similarity
        except Exception as e:
            logger.error(f"L2 Semantic Cache query failed: {e}")

        return None, None

    async def save_to_cache(self, prompt_text: str, model_name: str, response: ChatCompletionResponse, db_session) -> None:
        response_dict = response.model_dump()
        # Set cache hit metadata for stored data
        if "cost_metadata" in response_dict and response_dict["cost_metadata"]:
            response_dict["cost_metadata"]["cache_hit"] = True

        # 1. Save to L1 (Redis)
        exact_key = self._get_exact_key(prompt_text, model_name)
        try:
            self.redis.setex(
                exact_key,
                settings.CACHE_TTL_SECONDS,
                json.dumps(response_dict)
            )
        except Exception as e:
            logger.warning(f"Failed to write to L1 Redis cache: {e}")

        # 2. Save to L2 (DB + FAISS)
        if not self._initialized:
            return

        try:
            embedding = await self.embedding_provider.embed_single(prompt_text)
            embedding_list = [float(x) for x in embedding]
            
            new_entry = DBCacheEntry(
                prompt_text=prompt_text,
                response_json=response_dict,
                model=model_name,
                embedding=embedding_list,
                ttl_seconds=settings.CACHE_TTL_SECONDS
            )
            db_session.add(new_entry)
            await db_session.commit()
            await db_session.refresh(new_entry)
            
            # Add to local FAISS index
            vec = np.array(embedding_list, dtype=np.float32).reshape(1, -1)
            faiss.normalize_L2(vec)
            self.faiss_index.add(vec)
            self.db_ids.append(new_entry.id)
            logger.debug("Successfully saved request to L2 semantic cache index.")
        except Exception as e:
            logger.error(f"Failed to write to L2 semantic cache: {e}")

    async def process(self, ctx: RequestContext) -> RequestContext:
        if not settings.ENABLE_SEMANTIC_CACHE or ctx.request.cache_policy == "never":
            return ctx

        # Load cache entries on first request if not done
        if not self._initialized:
            await self.initialize_cache_from_db(ctx.db_session)

        prompt_text = "\n".join([m.content for m in ctx.request.messages])
        
        cached_resp, similarity = await self.get_cached_response(
            prompt_text=prompt_text,
            model_name=ctx.request.model,
            db_session=ctx.db_session
        )

        if cached_resp:
            ctx.response = cached_resp
            ctx.cache_hit = True
            # Complete request execution since response is fulfilled
            ctx.aborted = True
            
            # Populate cost metadata of hit response
            if ctx.response.cost_metadata:
                ctx.response.cost_metadata.cache_hit = True
                ctx.response.cost_metadata.latency_ms = (time.perf_counter() - ctx.start_time) * 1000
                ctx.response.cost_metadata.actual_cost = 0.0
                ctx.response.cost_metadata.routing_reason = f"Cached match (similarity: {similarity:.4f})"
                
            logger.info("Request served from Semantic Cache.")

        return ctx

# Global semantic cache instance
semantic_cache = SemanticCache()
