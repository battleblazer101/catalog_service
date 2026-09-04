# app/models/app_path.py

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database.database import Base


class AppPath(Base):
    __tablename__ = "app_paths"

    id = Column(
        Integer,
        primary_key=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    path = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    media_type = Column(
        String,
        nullable=False,
        index=True,
    )

    description = Column(
        String,
        nullable=True,
    )

    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
