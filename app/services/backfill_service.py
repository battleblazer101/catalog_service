# app/services/backfill_service.py

from datetime import datetime

from app.database.database import SessionLocal
from app.models.media import MediaItem
from app.services.embedding_service import (
    MODEL_NAME,
    create_embedding,
    serialize_embedding,
)


def build_embedding_text(
    item: MediaItem,
) -> str:
    """
    Build the text representation used to generate an embedding.

    Only descriptive catalog fields are included. The filesystem path
    and internal database identifiers are deliberately excluded.
    """

    return " ".join(
        value
        for value in (
            item.title,
            item.creator,
            item.collection,
            item.genre,
        )
        if value
    )


def backfill_embeddings(
    force: bool = False,
) -> dict[str, int]:
    """
    Generate embeddings for catalog items.

    By default only items without an embedding are processed.

    When force=True, every catalog item is regenerated.

    Returns:

        {
            "updated": <number of items updated>
        }

    A new database session is created and always closed by this
    function.
    """

    db = SessionLocal()

    try:
        query = db.query(
            MediaItem
        )

        if not force:
            query = query.filter(
                MediaItem.embedding.is_(None)
            )

        items = query.all()

        updated = 0

        for item in items:
            search_text = build_embedding_text(
                item
            )

            # Do not generate an embedding for an entirely empty
            # descriptive record.
            if not search_text:
                continue

            vector = create_embedding(
                search_text
            )

            item.embedding = serialize_embedding(
                vector
            )

            item.embedding_model = MODEL_NAME
            item.embedding_created_at = datetime.now()

            updated += 1

        db.commit()

        return {
            "updated": updated,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
