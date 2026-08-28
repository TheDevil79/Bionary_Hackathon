import pytest
from app.ingestion.embedder import Embedder, get_embedder, EMBEDDING_DIMENSION


def test_embedder_dimensions():
    embedder = get_embedder()
    assert embedder.dimension == 768

    texts = [
        "Severe flash flood and downpour in Chennai.",
        "NASA James Webb Space Telescope discovery on exoplanet.",
    ]
    vectors = embedder.embed_texts(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 768
    assert len(vectors[1]) == 768


def test_embed_single_query():
    embedder = get_embedder()
    vec = embedder.embed_query("Heavy rain and road flooding")
    assert isinstance(vec, list)
    assert len(vec) == 768

    # Empty query returns 768-dim zero vector
    empty_vec = embedder.embed_query("   ")
    assert len(empty_vec) == 768
    assert all(v == 0.0 for v in empty_vec)
