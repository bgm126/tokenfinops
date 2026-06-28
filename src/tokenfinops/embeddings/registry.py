import logging
from typing import Dict, Type
from tokenfinops.config import settings
from tokenfinops.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class EmbeddingRegistry:
    def __init__(self):
        self._provider_classes: Dict[str, Type[EmbeddingProvider]] = {}
        self._active_provider: EmbeddingProvider | None = None
        self.discover_and_register_core()
        self.initialize_active_provider()

    def register_provider_class(self, provider_cls: Type[EmbeddingProvider]) -> None:
        name = provider_cls.provider_name
        self._provider_classes[name] = provider_cls

    def discover_and_register_core(self) -> None:
        from tokenfinops.embeddings.sentence_transformers import SentenceTransformersProvider
        from tokenfinops.embeddings.openai_embeddings import OpenAIEmbeddingsProvider
        from tokenfinops.embeddings.cohere_embeddings import CohereEmbeddingsProvider
        from tokenfinops.embeddings.ollama_embeddings import OllamaEmbeddingsProvider

        core_classes = [
            SentenceTransformersProvider,
            OpenAIEmbeddingsProvider,
            CohereEmbeddingsProvider,
            OllamaEmbeddingsProvider
        ]

        for cls in core_classes:
            self.register_provider_class(cls)

    def initialize_active_provider(self) -> None:
        configured_provider_name = settings.EMBEDDING_PROVIDER
        
        if configured_provider_name in self._provider_classes:
            cls = self._provider_classes[configured_provider_name]
            try:
                instance = cls.from_env()
                if instance:
                    self._active_provider = instance
                    logger.info(f"Initialized active embedding provider: {configured_provider_name}")
                    return
            except Exception as e:
                logger.error(f"Error initializing embedding provider {configured_provider_name}: {e}")

        # Fallback search if configured provider fails or is not available
        logger.warning(
            f"Configured embedding provider '{configured_provider_name}' could not be initialized. "
            "Searching for any viable alternative..."
        )
        
        for name, cls in self._provider_classes.items():
            if name == configured_provider_name:
                continue
            try:
                instance = cls.from_env()
                if instance:
                    self._active_provider = instance
                    logger.info(f"Fell back to embedding provider: {name}")
                    return
            except Exception:
                continue

        logger.error(
            "NO embedding provider could be initialized. "
            "Please check your API keys or install local sentence-transformers (pip install tokenfinops[local-embeddings])."
        )

    def get_active_provider(self) -> EmbeddingProvider:
        if not self._active_provider:
            raise ValueError(
                "No embedding provider is active. "
                "Verify that your configured EMBEDDING_PROVIDER in .env has valid keys or local packages installed."
            )
        return self._active_provider

    def list_supported_providers(self) -> list[str]:
        return list(self._provider_classes.keys())

# Global registry instance
embedding_registry = EmbeddingRegistry()
