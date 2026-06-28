import os
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class ModelConfig(BaseModel):
    provider: str
    capabilities: list[str] = Field(default_factory=list)
    quality_tier: str = "standard"  # economy, standard, premium
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    context_window: int = 4096
    enabled: bool = True

class RoutingConfig(BaseModel):
    default_strategy: str = "balanced"
    fallback_chain: list[str] = Field(default_factory=list)
    task_routing: dict[str, list[str]] = Field(default_factory=dict)

class Settings(BaseSettings):
    # Database and Cache
    DATABASE_URL: str = "postgresql+asyncpg://tokenfinops:tokenfinops@localhost:5432/tokenfinops"
    REDIS_URL: str = "redis://localhost:6379/0"

    # API Keys & URLs
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    VLLM_BASE_URL: str | None = None
    OPENROUTER_API_KEY: str | None = None

    # Pluggable Embeddings
    EMBEDDING_PROVIDER: str = "sentence-transformers"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Feature Flags
    ENABLE_SEMANTIC_CACHE: bool = True
    ENABLE_PROMPT_OPTIMIZATION: bool = True
    ENABLE_MODEL_ROUTING: bool = True
    ENABLE_BUDGET_ENFORCEMENT: bool = True
    CACHE_SIMILARITY_THRESHOLD: float = 0.95
    CACHE_TTL_SECONDS: int = 3600

    # Routing Defaults
    DEFAULT_ROUTING_STRATEGY: str = "balanced"
    DEFAULT_MODEL: str | None = None

    # Rate Limits
    RATE_LIMIT_RPM: int = 60
    RATE_LIMIT_TPM: int = 100000

    # Config Path
    CONFIG_YAML_PATH: str = "config.yaml"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime model catalog loaded from config.yaml
    _models: dict[str, ModelConfig] = {}
    _routing: RoutingConfig = RoutingConfig()

    def model_post_init(self, __context: Any) -> None:
        self.load_yaml_config()

    def load_yaml_config(self) -> None:
        yaml_path = Path(self.CONFIG_YAML_PATH)
        if not yaml_path.exists():
            # Fall back to example config if exists, otherwise default
            yaml_path = Path("config.yaml.example")
            if not yaml_path.exists():
                # Default hardcoded configuration
                self._models = {
                    "llama3:8b": ModelConfig(
                        provider="ollama",
                        capabilities=["classification", "translation", "summarization", "general"],
                        quality_tier="economy",
                        cost_per_1k_input=0.0,
                        cost_per_1k_output=0.0,
                        context_window=8192,
                        enabled=True
                    )
                }
                self._routing = RoutingConfig(
                    default_strategy="balanced",
                    fallback_chain=["ollama"],
                    task_routing={"general": ["llama3:8b"]}
                )
                return

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            models_data = data.get("models", {})
            self._models = {
                name: ModelConfig(**cfg) for name, cfg in models_data.items()
            }
            
            routing_data = data.get("routing", {})
            self._routing = RoutingConfig(**routing_data)
        except Exception as e:
            # Simple error recovery, do not crash but print/log
            print(f"Error loading configuration from {yaml_path}: {e}")
            self._models = {}
            self._routing = RoutingConfig()

    @property
    def models(self) -> dict[str, ModelConfig]:
        return self._models

    @property
    def routing(self) -> RoutingConfig:
        return self._routing

# Global settings instance
settings = Settings()
