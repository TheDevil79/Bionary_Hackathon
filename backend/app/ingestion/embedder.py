"""
EvidenceLens — Embedding Generator.

Model: sentence-transformers/all-mpnet-base-v2
Dimension: 768
Similarity: Cosine similarity (unit-normalized vectors)

Why this model:
  - Produces exactly 768-dimensional dense vector embeddings.
  - Top-tier performance on the Massive Text Embedding Benchmark (MTEB)
    for retrieval, semantic search, and sentence similarity.
  - Runs efficiently on CPU/GPU.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIMENSION = 768

_embedder_instance: Embedder | None = None


class Embedder:
    """Wrapper around sentence-transformers for 768-dim vector generation."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self.dimension = EMBEDDING_DIMENSION
        self._model: Any = None

    def _get_model(self) -> Any:
        """Lazy load the sentence-transformer model."""
        if self._model is None:
            logger.info("Loading sentence-transformers model: %s", self.model_name)
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully. Embedding dimension: %d", self.dimension)
            except Exception as exc:
                logger.error("Failed to load SentenceTransformer '%s': %s", self.model_name, exc)
                raise RuntimeError(
                    f"Could not load embedding model '{self.model_name}'. "
                    f"Ensure 'sentence-transformers' is installed."
                ) from exc
        return self._model

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Generate 768-dimensional normalized embeddings for a list of texts.

        Args:
            texts: List of strings to embed.
            batch_size: Batch size for model inference.

        Returns:
            List of 768-dimensional float lists.
        """
        if not texts:
            return []

        model = self._get_model()
        # normalize_embeddings=True produces unit-length vectors for cosine similarity
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 20,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        result: list[list[float]] = embeddings.tolist()
        for idx, vec in enumerate(result):
            if len(vec) != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimension}, got {len(vec)} at index {idx}"
                )
        return result

    def embed_query(self, query: str) -> list[float]:
        """Generate a 768-dimensional normalized embedding for a single query."""
        if not query.strip():
            # Return zero vector if empty query
            return [0.0] * self.dimension
        embeddings = self.embed_texts([query])
        return embeddings[0]


def get_embedder(model_name: str = DEFAULT_MODEL_NAME) -> Embedder:
    """Get or create singleton Embedder instance."""
    global _embedder_instance
    if _embedder_instance is None or _embedder_instance.model_name != model_name:
        _embedder_instance = Embedder(model_name=model_name)
    return _embedder_instance
