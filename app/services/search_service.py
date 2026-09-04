# app/services/search_service.py

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.media import MediaItem


# ---------------------------------------------------------------------------
# Text search
# ---------------------------------------------------------------------------

def search_items(
    db: Session,
    query: str,
    limit: int = 50,
    media_type: str | None = None,
):
    """
    Perform a simple weighted text search over the catalog.

    Ranking:

        title       -> 3.0
        creator     -> 2.0
        collection  -> 1.5
        genre       -> 1.0

    A match in multiple fields receives the combined score.

    This is deliberately separate from semantic search. It provides
    deterministic substring matching and is useful for exact names,
    artists, titles, collections and similar lookups.
    """

    query = query.strip()

    if not query:
        return []

    if limit <= 0:
        return []

    pattern = f"%{query}%"

    score = (
        case(
            (
                MediaItem.title.ilike(pattern),
                3.0,
            ),
            else_=0.0,
        )
        +
        case(
            (
                MediaItem.creator.ilike(pattern),
                2.0,
            ),
            else_=0.0,
        )
        +
        case(
            (
                MediaItem.collection.ilike(pattern),
                1.5,
            ),
            else_=0.0,
        )
        +
        case(
            (
                MediaItem.genre.ilike(pattern),
                1.0,
            ),
            else_=0.0,
        )
    )

    stmt = (
        select(
            MediaItem,
            score.label("score"),
        )
        .where(
            score > 0
        )
    )

    if media_type is not None:
        stmt = stmt.where(
            MediaItem.media_type == media_type
        )

    stmt = (
        stmt
        .order_by(
            score.desc(),
            MediaItem.title.asc(),
            MediaItem.id.asc(),
        )
        .limit(limit)
    )

    return db.execute(
        stmt
    ).all()


# ---------------------------------------------------------------------------
# Exact item lookup
# ---------------------------------------------------------------------------

def search_by_title(
    db: Session,
    title: str,
    limit: int = 50,
    media_type: str | None = None,
):
    """
    Search specifically against media titles.
    """

    title = title.strip()

    if not title:
        return []

    pattern = f"%{title}%"

    stmt = (
        select(MediaItem)
        .where(
            MediaItem.title.ilike(pattern)
        )
    )

    if media_type is not None:
        stmt = stmt.where(
            MediaItem.media_type == media_type
        )

    return (
        db.execute(
            stmt
        )
        .scalars()
        .order_by(
            MediaItem.title.asc(),
            MediaItem.id.asc(),
        )
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Media-type search
# ---------------------------------------------------------------------------

def search_by_media_type(
    db: Session,
    media_type: str,
    limit: int = 100,
):
    """
    Return catalog items belonging to a specific media type.
    """

    media_type = media_type.strip().lower()

    if not media_type:
        return []

    if limit <= 0:
        return []

    stmt = (
        select(MediaItem)
        .where(
            MediaItem.media_type == media_type
        )
        .order_by(
            MediaItem.title.asc(),
            MediaItem.id.asc(),
        )
        .limit(limit)
    )

    return (
        db.execute(
            stmt
        )
        .scalars()
        .all()
    )
