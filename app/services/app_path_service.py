# app/services/app_path_service.py

from sqlalchemy.orm import Session

from app.models.app_path import AppPath


VALID_MEDIA_TYPES = {
    "music",
    "movie",
    "tv",
    "book",
}


def validate_media_type(
    media_type: str,
) -> str:
    """
    Validate and normalize a catalog media type.

    Supported values:

        music
        movie
        tv
        book
    """

    value = media_type.strip().lower()

    if value not in VALID_MEDIA_TYPES:
        raise ValueError(
            f"Unsupported media type: {media_type}"
        )

    return value


def list_paths(
    db: Session,
    media_type: str | None = None,
    enabled_only: bool = False,
) -> list[AppPath]:
    """
    Return configured catalog paths.

    Results are ordered by media type and then path name.
    """

    query = db.query(
        AppPath
    )

    if media_type is not None:
        media_type = validate_media_type(
            media_type
        )

        query = query.filter(
            AppPath.media_type == media_type
        )

    if enabled_only:
        query = query.filter(
            AppPath.enabled.is_(True)
        )

    return (
        query
        .order_by(
            AppPath.media_type,
            AppPath.name,
        )
        .all()
    )


def get_path(
    db: Session,
    path_id: int,
) -> AppPath | None:
    """
    Return a configured path by database ID.
    """

    return (
        db.query(
            AppPath
        )
        .filter(
            AppPath.id == path_id
        )
        .first()
    )


def create_path(
    db: Session,
    name: str,
    path: str,
    media_type: str,
    description: str | None = None,
    enabled: bool = True,
) -> AppPath:
    """
    Create a configured catalog path.

    Database uniqueness constraints are intentionally left to the
    AppPath model/database layer. The API layer is responsible for
    translating IntegrityError into an appropriate HTTP response.
    """

    clean_name = name.strip()
    clean_path = path.strip()

    if not clean_name:
        raise ValueError(
            "Path name cannot be empty"
        )

    if not clean_path:
        raise ValueError(
            "Path cannot be empty"
        )

    media_type = validate_media_type(
        media_type
    )

    app_path = AppPath(
        name=clean_name,
        path=clean_path,
        media_type=media_type,
        description=description,
        enabled=enabled,
    )

    db.add(
        app_path
    )

    db.commit()
    db.refresh(
        app_path
    )

    return app_path


def update_path(
    db: Session,
    app_path: AppPath,
    name: str | None = None,
    path: str | None = None,
    media_type: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
) -> AppPath:
    """
    Update an existing configured catalog path.

    None means that a field was not supplied and therefore should
    remain unchanged.

    An explicitly supplied empty name or path is rejected.
    """

    if name is not None:
        clean_name = name.strip()

        if not clean_name:
            raise ValueError(
                "Path name cannot be empty"
            )

        app_path.name = clean_name

    if path is not None:
        clean_path = path.strip()

        if not clean_path:
            raise ValueError(
                "Path cannot be empty"
            )

        app_path.path = clean_path

    if media_type is not None:
        app_path.media_type = validate_media_type(
            media_type
        )

    if description is not None:
        app_path.description = description

    if enabled is not None:
        app_path.enabled = enabled

    db.commit()
    db.refresh(
        app_path
    )

    return app_path


def delete_path(
    db: Session,
    app_path: AppPath,
) -> None:
    """
    Delete a configured catalog path.

    Deleting the configuration does not itself delete media files
    or catalog items discovered from that path.
    """

    db.delete(
        app_path
    )

    db.commit()
