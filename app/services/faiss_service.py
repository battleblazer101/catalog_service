# app/services/faiss_service.py

import logging
from dataclasses import dataclass

import faiss
import numpy as np

from app.services.embedding_service import (
    deserialize_embedding,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FAISSResult:
    """
    A single FAISS search result.

    index:
        Position of the matching vector in the FAISS index.

    score:
        Similarity/distance score returned by FAISS.
    """

    index: int
    score: float


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class FAISSIndex:
    """
    In-memory FAISS index for catalog embeddings.

    The catalog database remains the source of truth.

    FAISS is only responsible for efficiently finding candidate
    vectors. The returned integer positions are mapped back to
    MediaItem IDs by the semantic search service.
    """

    def __init__(
        self,
        dimension: int,
    ):
        if dimension <= 0:
            raise ValueError(
                "FAISS index dimension must be greater than zero"
            )

        self.dimension = dimension

        # Inner product is used with normalized vectors.
        #
        # For normalized vectors:
        #
        #     inner product == cosine similarity
        #
        self._index = faiss.IndexFlatIP(
            dimension
        )

        self._item_ids: list[int] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """
        Number of vectors currently stored in the index.
        """

        return self._index.ntotal

    @property
    def item_ids(self) -> list[int]:
        """
        Return the database IDs corresponding to indexed vectors.
        """

        return list(
            self._item_ids
        )

    # ------------------------------------------------------------------
    # Internal validation
    # ------------------------------------------------------------------

    def _validate_vector(
        self,
        vector: list[float],
    ) -> np.ndarray:
        """
        Convert and validate a single embedding vector.
        """

        array = np.asarray(
            vector,
            dtype=np.float32,
        )

        if array.ndim != 1:
            raise ValueError(
                "Embedding vector must be one-dimensional"
            )

        if array.shape[0] != self.dimension:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {self.dimension}, "
                f"got {array.shape[0]}"
            )

        return array

    def _validate_vectors(
        self,
        vectors: list[list[float]],
    ) -> np.ndarray:
        """
        Convert and validate multiple embedding vectors.
        """

        array = np.asarray(
            vectors,
            dtype=np.float32,
        )

        if array.ndim != 2:
            raise ValueError(
                "Embedding vectors must be a two-dimensional array"
            )

        if array.shape[1] != self.dimension:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {self.dimension}, "
                f"got {array.shape[1]}"
            )

        return array

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    def add(
        self,
        item_id: int,
        vector: list[float],
    ) -> None:
        """
        Add one database item and its embedding.
        """

        if item_id <= 0:
            raise ValueError(
                "item_id must be greater than zero"
            )

        array = self._validate_vector(
            vector
        )

        array = array.reshape(
            1,
            -1,
        )

        faiss.normalize_L2(
            array
        )

        self._index.add(
            array
        )

        self._item_ids.append(
            item_id
        )

    def add_many(
        self,
        items: list[tuple[int, list[float]]],
    ) -> None:
        """
        Add multiple database items and embeddings.

        Each tuple must contain:

            (database_item_id, embedding)
        """

        if not items:
            return

        item_ids = [
            item_id
            for item_id, _ in items
        ]

        vectors = [
            vector
            for _, vector in items
        ]

        for item_id in item_ids:
            if item_id <= 0:
                raise ValueError(
                    "item_id must be greater than zero"
                )

        array = self._validate_vectors(
            vectors
        )

        faiss.normalize_L2(
            array
        )

        self._index.add(
            array
        )

        self._item_ids.extend(
            item_ids
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        vector: list[float],
        limit: int = 10,
    ) -> list[FAISSResult]:
        """
        Search for the nearest vectors.

        Results are ordered by descending cosine similarity.
        """

        if limit <= 0:
            return []

        if self.size == 0:
            return []

        array = self._validate_vector(
            vector
        )

        array = array.reshape(
            1,
            -1,
        )

        faiss.normalize_L2(
            array
        )

        count = min(
            limit,
            self.size,
        )

        scores, indices = self._index.search(
            array,
            count,
        )

        results: list[FAISSResult] = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):
            if index < 0:
                continue

            results.append(
                FAISSResult(
                    index=int(index),
                    score=float(score),
                )
            )

        return results

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def item_id_for_index(
        self,
        index: int,
    ) -> int | None:
        """
        Convert a FAISS vector position into a database item ID.
        """

        if index < 0:
            return None

        if index >= len(
            self._item_ids
        ):
            return None

        return self._item_ids[index]

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """
        Remove all vectors from the index.
        """

        self._index.reset()
        self._item_ids.clear()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def create_index(
    dimension: int,
) -> FAISSIndex:
    """
    Create a new empty FAISS index.
    """

    return FAISSIndex(
        dimension=dimension
    )


def build_index(
    items: list[tuple[int, str]],
) -> FAISSIndex:
    """
    Build an index from database item IDs and serialized embeddings.

    Input:

        [
            (123, "[0.1, 0.2, ...]"),
            (456, "[0.3, 0.4, ...]"),
        ]

    The embedding dimension is determined from the first item.
    """

    if not items:
        raise ValueError(
            "Cannot build FAISS index from an empty item list"
        )

    first_vector = deserialize_embedding(
        items[0][1]
    )

    if not first_vector:
        raise ValueError(
            "First embedding is empty"
        )

    index = FAISSIndex(
        dimension=len(first_vector)
    )

    decoded_items: list[
        tuple[int, list[float]]
    ] = []

    for item_id, serialized_vector in items:
        vector = deserialize_embedding(
            serialized_vector
        )

        decoded_items.append(
            (
                item_id,
                vector,
            )
        )

    index.add_many(
        decoded_items
    )

    logger.info(
        "Built FAISS index with %d vectors",
        index.size,
    )

    return index
