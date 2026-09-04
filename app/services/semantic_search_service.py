# app/services/semantic_search_service.py

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.media import MediaItem
from app.services.embedding_service import (
    create_embedding,
    deserialize_embedding,
    embedding_dimension,
)
from app.services.faiss_service import (
    FAISSIndex,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemanticSearchResult:
    """
    A semantic catalog search result.
    """

    item: MediaItem
    score: float


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

_index: FAISSIndex | None = None


def get_index() -> FAISSIndex | None:
    """
    Return the currently loaded FAISS index.

    The index is intentionally kept in memory. The database remains
    the source of truth.
    """

    return _index


def rebuild_index(
    db: Session,
    media_type: str | None = None,
) -> FAISSIndex:
    """
    Rebuild the in-memory FAISS index from database embeddings.

    If media_type is supplied, only items of that type are indexed.

    The database IDs are stored alongside the FAISS vectors so search
    results can be mapped back to MediaItem records.
    """

    global _index

    query = (
        db.query(MediaItem)
        .filter(
            MediaItem.embedding.isnot(None)
        )
    )

    if media_type is not None:
        query = query.filter(
            MediaItem.media_type == media_type
        )

    items = (
        query
        .order_by(MediaItem.id)
        .all()
    )

    dimension = embedding_dimension()

    index = FAISSIndex(
        dimension=dimension
    )

    indexed = 0

    for item in items:
        if item.embedding is None:
            continue

        try:
            vector = deserialize_embedding(
                item.embedding
            )

            if len(vector) != dimension:
                logger.warning(
                    "Skipping item %s: embedding dimension "
                    "is %d, expected %d",
                    item.id,
                    len(vector),
                    dimension,
                )
                continue

            index.add(
                item_id=item.id,
                vector=vector,
            )

            indexed += 1

        except Exception:
            logger.exception(
                "Failed to index media item %s",
                item.id,
            )

    _index = index

    logger.info(
        "FAISS index rebuilt: %d/%d items indexed",
        indexed,
        len(items),
    )

    return index


def clear_index() -> None:
    """
    Clear the current in-memory index.
    """

    global _index

    _index = None


def ensure_index(
    db: Session,
) -> FAISSIndex:
    """
    Return the current index, building it if necessary.
    """

    if _index is None:
        return rebuild_index(
            db
        )

    return _index


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def semantic_search_items(
    db: Session,
    query: str,
    limit: int = 20,
    media_type: str | None = None,
    min_score: float | None = None,
) -> list[SemanticSearchResult]:
    """
    Perform semantic catalog search.

    The query is embedded using the same model used when catalog
    items were ingested.

    FAISS returns candidate database IDs. The actual MediaItem
    records are then loaded from SQLAlchemy.
    """

    query = query.strip()

    if not query:
        return []

    if limit <= 0:
        return []

    vector = create_embedding(
        query
    )

    # A media-type-specific search requires an index containing only
    # that media type. The global index cannot safely be reused because
    # FAISS positions map to a different item set.
    if media_type is not None:
        index = rebuild_index(
            db,
            media_type=media_type,
        )
    else:
        index = ensure_index(
            db
        )

    if index.size == 0:
        return []

    search_results = index.search(
        vector=vector,
        limit=limit,
    )

    if not search_results:
        return []

    item_ids = [
        index.item_id_for_index(
            result.index
        )
        for result in search_results
    ]

    item_ids = [
        item_id
        for item_id in item_ids
        if item_id is not None
    ]

    if not item_ids:
        return []

    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.id.in_(item_ids)
        )
        .all()
    )

    items_by_id = {
        item.id: item
        for item in items
    }

    results: list[
        SemanticSearchResult
    ] = []

    for search_result in search_results:
        item_id = index.item_id_for_index(
            search_result.index
        )

        if item_id is None:
            continue

        item = items_by_id.get(
            item_id
        )

        if item is None:
            continue

        score = search_result.score

        if (
            min_score is not None
            and score < min_score
        ):
            continue

        results.append(
            SemanticSearchResult(
                item=item,
                score=score,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Convenience search API
# ---------------------------------------------------------------------------

def search_items_semantic(
    db: Session,
    query: str,
    limit: int = 20,
    media_type: str | None = None,
    min_score: float | None = None,
) -> list[SemanticSearchResult]:
    """
    Alias for semantic_search_items().

    Kept as a descriptive public API for callers that prefer the
    search_items_semantic naming convention.
    """

    return semantic_search_items(
        db=db,
        query=query,
        limit=limit,
        media_type=media_type,
        min_score=min_score,
    )


# ---------------------------------------------------------------------------
# Index status
# ---------------------------------------------------------------------------

def get_index_stats() -> dict[str, int | bool]:
    """
    Return basic information about the current in-memory index.
    """

    if _index is None:
        return {
            "loaded": False,
            "vectors": 0,
        }

    return {
        "loaded": True,
        "vectors": _index.size,
    }
