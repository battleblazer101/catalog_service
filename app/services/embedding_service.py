# app/services/embedding_service.py

import json
import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """
    Load and cache the sentence-transformer model.

    The model is loaded lazily rather than at module import time.
    This keeps application imports lightweight and makes failures
    easier to handle during application startup.
    """

    logger.info(
        "Loading embedding model: %s",
        MODEL_NAME,
    )

    model = SentenceTransformer(
        MODEL_NAME
    )

    logger.info(
        "Embedding model loaded: %s",
        MODEL_NAME,
    )

    return model


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def create_embedding(
    text: str,
) -> list[float]:
    """
    Generate an embedding for text.

    The returned value is always a plain Python list of floats,
    making it suitable for JSON serialization and database storage.
    """

    if not isinstance(text, str):
        raise TypeError(
            "Embedding text must be a string"
        )

    text = text.strip()

    if not text:
        raise ValueError(
            "Cannot create an embedding from empty text"
        )

    model = get_model()

    vector = model.encode(
        text,
        convert_to_numpy=True,
    )

    return vector.tolist()


def create_embeddings(
    texts: list[str],
) -> list[list[float]]:
    """
    Generate embeddings for multiple text values.

    This is more efficient than repeatedly calling create_embedding()
    because SentenceTransformer can encode the complete batch in one
    operation.
    """

    if not isinstance(texts, list):
        raise TypeError(
            "Embedding texts must be a list"
        )

    if not texts:
        return []

    normalized_texts: list[str] = []

    for text in texts:
        if not isinstance(text, str):
            raise TypeError(
                "Every embedding text must be a string"
            )

        normalized = text.strip()

        if not normalized:
            raise ValueError(
                "Cannot create an embedding from empty text"
            )

        normalized_texts.append(
            normalized
        )

    model = get_model()

    vectors = model.encode(
        normalized_texts,
        convert_to_numpy=True,
    )

    return [
        vector.tolist()
        for vector in vectors
    ]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_embedding(
    vector: list[float],
) -> str:
    """
    Serialize an embedding vector to JSON for database storage.
    """

    if not isinstance(vector, list):
        raise TypeError(
            "Embedding vector must be a list"
        )

    return json.dumps(
        vector,
        separators=(",", ":"),
    )


def deserialize_embedding(
    text: str,
) -> list[float]:
    """
    Deserialize an embedding stored as JSON.

    Raises ValueError if the stored value is not a valid
    embedding representation.
    """

    if not isinstance(text, str):
        raise TypeError(
            "Serialized embedding must be a string"
        )

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid serialized embedding"
        ) from exc

    if not isinstance(value, list):
        raise ValueError(
            "Serialized embedding must contain a JSON list"
        )

    try:
        return [
            float(item)
            for item in value
        ]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Serialized embedding contains non-numeric values"
        ) from exc


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def embedding_dimension() -> int:
    """
    Return the dimensionality of the configured embedding model.
    """

    model = get_model()

    return int(
        model.get_sentence_embedding_dimension()
    )


def clear_model_cache() -> None:
    """
    Clear the cached model.

    Primarily useful for tests or controlled model reloading.
    """

    get_model.cache_clear()
