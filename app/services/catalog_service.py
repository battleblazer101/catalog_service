# app/services/catalog_service.py

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.media import MediaItem
from app.scanners.types import CatalogItem
from app.services.embedding_service import (
    MODEL_NAME,
    create_embedding,
    serialize_embedding,
)


# ---------------------------------------------------------------------------
# Search text / embeddings
# ---------------------------------------------------------------------------

def build_search_text(
    item: CatalogItem,
) -> str:
    """
    Build the text representation used for semantic embeddings.
    """

    return " ".join(
        filter(
            None,
            [
                item["title"],
                item["creator"],
                item["collection"],
                item["genre"],
            ],
        )
    )


def build_media_search_text(
    item: MediaItem,
) -> str:
    """
    Build the text representation for an existing database item.
    """

    return " ".join(
        filter(
            None,
            [
                item.title,
                item.creator,
                item.collection,
                item.genre,
            ],
        )
    )


# ---------------------------------------------------------------------------
# Individual items
# ---------------------------------------------------------------------------

def get_item(
    db: Session,
    item_id: int,
) -> MediaItem | None:
    """
    Return a media item by database ID.
    """

    return (
        db.query(MediaItem)
        .filter(
            MediaItem.id == item_id
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def list_items(
    db: Session,
    media_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MediaItem]:
    """
    Return catalog items.

    Results are ordered consistently by ID.

    Optional media_type filtering is supported.
    """

    query = db.query(MediaItem)

    if media_type is not None:
        query = query.filter(
            MediaItem.media_type == media_type
        )

    return (
        query
        .order_by(MediaItem.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def insert_media_items(
    db: Session,
    items: list[CatalogItem],
    media_type: str,
) -> int:
    """
    Insert newly discovered media items.

    Existing filesystem paths are not inserted again.

    New items receive an embedding immediately.
    """

    inserted = 0

    for item in items:
        existing = (
            db.query(MediaItem.id)
            .filter(
                MediaItem.path == item["path"]
            )
            .first()
        )

        if existing is not None:
            continue

        search_text = build_search_text(
            item
        )

        embedding = create_embedding(
            search_text
        )

        media_values: dict[str, object] = {
            "media_type": media_type,
            "title": item["title"],
            "creator": item["creator"],
            "collection": item["collection"],
            "genre": item["genre"],
            "path": item["path"],
            "metadata_json": item["metadata"],
            "embedding": serialize_embedding(
                embedding
            ),
            "embedding_model": MODEL_NAME,
            "embedding_created_at": datetime.now(),
        }

        year = item.get("year")

        if year is not None:
            media_values["year"] = year

        db_item = MediaItem(
            **media_values
        )

        db.add(db_item)
        inserted += 1

    db.commit()

    return inserted


# ---------------------------------------------------------------------------
# Updating existing items
# ---------------------------------------------------------------------------

def update_media_item(
    db: Session,
    db_item: MediaItem,
    item: CatalogItem,
) -> MediaItem:
    """
    Update an existing database item from scanner metadata.

    The embedding is regenerated because the searchable metadata
    may have changed.
    """

    db_item.title = item["title"]
    db_item.creator = item["creator"]
    db_item.collection = item["collection"]
    db_item.genre = item["genre"]
    db_item.path = item["path"]
    db_item.metadata_json = item["metadata"]

    year = item.get("year")

    db_item.year = year

    search_text = build_search_text(
        item
    )

    embedding = create_embedding(
        search_text
    )

    db_item.embedding = serialize_embedding(
        embedding
    )
    db_item.embedding_model = MODEL_NAME
    db_item.embedding_created_at = datetime.now()

    db.commit()
    db.refresh(db_item)

    return db_item


# ---------------------------------------------------------------------------
# Synchronisation
# ---------------------------------------------------------------------------

def delete_missing_items(
    db: Session,
    scanned_paths: list[str],
    media_type: str | None = None,
    base_path: str | None = None,
) -> int:
    """
    Delete catalog items that were not present in a completed scan.

    This is deliberately scoped so that a scan of one media directory
    cannot accidentally delete items belonging to another directory.

    Parameters:

        scanned_paths:
            Paths currently discovered by the scanner.

        media_type:
            Optional media type to restrict deletion.

        base_path:
            Optional filesystem root being synchronised.

    Behaviour:

        If base_path is supplied, only items whose stored path is
        inside that path are considered.

        If scanned_paths is empty, no deletion is performed unless
        base_path is explicitly supplied. This prevents a failed or
        inaccessible scan from wiping the catalog accidentally.
    """

    # An empty scan result is potentially caused by an inaccessible
    # storage location. Never interpret that as "everything disappeared"
    # unless the caller explicitly supplied a scan scope.
    if not scanned_paths and base_path is None:
        return 0

    query = db.query(MediaItem)

    if media_type is not None:
        query = query.filter(
            MediaItem.media_type == media_type
        )

    if base_path is not None:
        normalized_base = base_path.rstrip(
            "/\\"
        )

        # SQLite/PostgreSQL both support LIKE for this simple
        # path-prefix restriction. The separator prevents
        # /movies2 from matching /movies.
        query = query.filter(
            MediaItem.path.startswith(
                normalized_base + "/"
            )
            |
            MediaItem.path.startswith(
                normalized_base + "\\"
            )
            |
            (MediaItem.path == normalized_base)
        )

    existing_items = query.all()

    scanned_set = {
        path.rstrip("/\\")
        for path in scanned_paths
    }

    deleted = 0

    for item in existing_items:
        item_path = item.path.rstrip(
            "/\\"
        )

        if item_path in scanned_set:
            continue

        db.delete(item)
        deleted += 1

    if deleted:
        db.commit()

    return deleted


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def sync_media_items(
    db: Session,
    items: list[CatalogItem],
    media_type: str,
    base_path: str | None = None,
) -> dict[str, int]:
    """
    Synchronise scanner results with the database.

    Existing paths are updated.
    New paths are inserted.
    Missing paths are deleted within the supplied scan scope.

    Returns counts for inserted, updated and deleted items.
    """

    scanned_paths = [
        item["path"]
        for item in items
    ]

    inserted = 0
    updated = 0

    for item in items:
        existing = (
            db.query(MediaItem)
            .filter(
                MediaItem.path == item["path"]
            )
            .first()
        )

        if existing is None:
            search_text = build_search_text(
                item
            )

            embedding = create_embedding(
                search_text
            )

            media_values: dict[str, object] = {
                "media_type": media_type,
                "title": item["title"],
                "creator": item["creator"],
                "collection": item["collection"],
                "genre": item["genre"],
                "path": item["path"],
                "metadata_json": item["metadata"],
                "embedding": serialize_embedding(
                    embedding
                ),
                "embedding_model": MODEL_NAME,
                "embedding_created_at": datetime.now(),
            }

            year = item.get("year")

            if year is not None:
                media_values["year"] = year

            db.add(
                MediaItem(
                    **media_values
                )
            )

            inserted += 1

        else:
            existing.title = item["title"]
            existing.creator = item["creator"]
            existing.collection = item["collection"]
            existing.genre = item["genre"]
            existing.media_type = media_type
            existing.metadata_json = item["metadata"]
            existing.year = item.get("year")

            search_text = build_search_text(
                item
            )

            embedding = create_embedding(
                search_text
            )

            existing.embedding = serialize_embedding(
                embedding
            )
            existing.embedding_model = MODEL_NAME
            existing.embedding_created_at = datetime.now()

            updated += 1

    db.commit()

    deleted = delete_missing_items(
        db=db,
        scanned_paths=scanned_paths,
        media_type=media_type,
        base_path=base_path,
    )

    return {
        "scanned": len(items),
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted,
    }
