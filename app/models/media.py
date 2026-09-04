# app/models/media.py

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class MediaItem(Base):
    """
    Catalog entry representing a single media item.

    A MediaItem is created by one of the media scanners and
    represents the normalized catalog representation of a file.

    The original filesystem path is retained so that the catalog
    can identify the source item and avoid duplicate ingestion.
    """

    __tablename__ = "media_items"

    # ------------------------------------------------------------------
    # Primary identity
    # ------------------------------------------------------------------

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ------------------------------------------------------------------
    # Media classification
    # ------------------------------------------------------------------

    media_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Catalog metadata
    # ------------------------------------------------------------------

    title: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        index=True,
    )

    creator: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="Unknown",
    )

    collection: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="Unknown",
    )

    genre: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="Unknown",
    )

    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Source filesystem information
    # ------------------------------------------------------------------

    path: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
        unique=True,
        index=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Semantic-search embedding
    # ------------------------------------------------------------------

    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    embedding_created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Record timestamps
    # ------------------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_media_items_media_type_title",
            "media_type",
            "title",
        ),
        Index(
            "ix_media_items_media_type_creator",
            "media_type",
            "creator",
        ),
        Index(
            "ix_media_items_media_type_collection",
            "media_type",
            "collection",
        ),
    )

    def __repr__(self) -> str:
        return (
            "MediaItem("
            f"id={self.id!r}, "
            f"media_type={self.media_type!r}, "
            f"title={self.title!r}, "
            f"path={self.path!r}"
            ")"
        )
