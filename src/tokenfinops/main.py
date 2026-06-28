import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app
from tokenfinops.config import settings
from tokenfinops.gateway.router import router as gateway_router
from tokenfinops.gateway.middleware import RequestLoggingMiddleware
from tokenfinops.dashboard.api import router as dashboard_router
from tokenfinops.providers.registry import provider_registry

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Initializing TokenFinOps platform...")
    active_providers = provider_registry.list_active_providers()
    logger.info(f"Active LLM providers: {active_providers}")
    yield
    # Shutdown tasks
    logger.info("Shutting down TokenFinOps...")

app = FastAPI(
    title="TokenFinOps",
    description="Pluggable, open-ended, self-hostable AI Cost Optimizer API gateway.",
    version="0.1.0",
    lifespan=lifespan
)

# Apply middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# Register routes
app.include_router(gateway_router, prefix="/v1")
app.include_router(dashboard_router, prefix="/api/dashboard")

# Mount Prometheus metrics endpoint
app.mount("/metrics", make_asgi_app())

# Serve static dashboard files
app.mount("/static", StaticFiles(directory="src/tokenfinops/dashboard/static"), name="static")

@app.get("/")
async def serve_dashboard():
    """Serve the cost optimizer dashboard web UI."""
    return FileResponse("src/tokenfinops/dashboard/static/index.html")

@app.get("/health")
async def health_check():
    """Retrieve platform and LLM provider health status."""
    provider_report = await provider_registry.get_health_report()
    return {
        "status": "healthy",
        "active_providers": provider_registry.list_active_providers(),
        "providers_health": provider_report,
        "feature_flags": {
            "semantic_cache": settings.ENABLE_SEMANTIC_CACHE,
            "prompt_optimization": settings.ENABLE_PROMPT_OPTIMIZATION,
            "model_routing": settings.ENABLE_MODEL_ROUTING,
            "budget_enforcement": settings.ENABLE_BUDGET_ENFORCEMENT
        }
    }
