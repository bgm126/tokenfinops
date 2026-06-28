import logging
import importlib
import pkgutil
from typing import Dict, Type
from tokenfinops.providers.base import LLMProvider

logger = logging.getLogger(__name__)

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._registered_classes: Dict[str, Type[LLMProvider]] = {}
        self.discover_and_register_core()

    def register_provider_class(self, provider_cls: Type[LLMProvider]) -> None:
        """Register a provider class definition."""
        name = provider_cls.provider_name
        self._registered_classes[name] = provider_cls
        
        # Instantiate if configuration allows
        try:
            instance = provider_cls.from_env()
            if instance:
                self._providers[name] = instance
                logger.info(f"Successfully configured provider: {name}")
            else:
                logger.debug(f"Provider {name} not configured (keys missing).")
        except Exception as e:
            logger.error(f"Failed to initialize provider {name} from environment: {e}")

    def discover_and_register_core(self) -> None:
        """Dynamically load and register all providers in this package."""
        from tokenfinops.providers.openai_provider import OpenAIProvider
        from tokenfinops.providers.anthropic_provider import AnthropicProvider
        from tokenfinops.providers.ollama_provider import OllamaProvider
        from tokenfinops.providers.gemini_provider import GeminiProvider
        from tokenfinops.providers.vllm_provider import VLLMProvider
        from tokenfinops.providers.openrouter_provider import OpenRouterProvider

        core_classes = [
            OpenAIProvider,
            AnthropicProvider,
            OllamaProvider,
            GeminiProvider,
            VLLMProvider,
            OpenRouterProvider
        ]

        for cls in core_classes:
            self.register_provider_class(cls)

        # Discover community contrib providers if directory exists
        try:
            import contrib.providers
            for _, name, _ in pkgutil.iter_modules(contrib.providers.__path__):
                try:
                    mod = importlib.import_module(f"contrib.providers.{name}")
                    for attr in dir(mod):
                        val = getattr(mod, attr)
                        if isinstance(val, type) and issubclass(val, LLMProvider) and val is not LLMProvider:
                            self.register_provider_class(val)
                except Exception as e:
                    logger.warning(f"Failed to load contrib provider module {name}: {e}")
        except ModuleNotFoundError:
            # Contrib directory not in path/not created yet, safe to skip
            pass

    def get_provider(self, name: str) -> LLMProvider:
        """Get an active, configured provider instance."""
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' is not configured or not supported. Check your .env file.")
        return self._providers[name]

    def list_active_providers(self) -> list[str]:
        """List names of configured and active providers."""
        return list(self._providers.keys())

    def list_supported_providers(self) -> list[str]:
        """List all discovered provider names, whether active or not."""
        return list(self._registered_classes.keys())

    async def get_health_report(self) -> Dict[str, dict]:
        """Fetch health check for all active providers."""
        report = {}
        for name, provider in self._providers.items():
            health = await provider.health_check()
            report[name] = {
                "healthy": health.is_healthy,
                "latency_ms": health.latency_ms,
                "error": health.error_message
            }
        return report

# Global registry instance
provider_registry = ProviderRegistry()
