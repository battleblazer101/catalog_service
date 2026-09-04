# app/services/scanner_service.py

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.app_path import AppPath
from app.scanners.movies import scan_movies_folder
from app.scanners.music import scan_music_folder
from app.scanners.tv import scan_tv_folder
from app.services.catalog_service import sync_media_items
from app.storage import get_storage_provider


@dataclass
class ScanResult:
    path_id: int
    name: str
    media_type: str
    path: str
    inserted: int
    updated: int
    deleted: int
    total: int


def scan_path(
    db: Session,
    app_path: AppPath,
) -> ScanResult:
    """
    Scan one configured media path and synchronize
    the resulting catalog items.
    """

    media_type = app_path.media_type
    path = app_path.path

    storage = get_storage_provider(
        path
    )

    if media_type == "movie":
        items = scan_movies_folder(
            storage,
            path,
        )

    elif media_type == "tv":
        items = scan_tv_folder(
            storage,
            path,
        )

    elif media_type == "music":
        items = scan_music_folder(
            path,
        )

    elif media_type == "book":
        items = _scan_books(
            path,
        )

    else:
        raise ValueError(
            f"Unsupported media type: {media_type}"
        )

    counts = sync_media_items(
        db,
        items,
        media_type,
        path,
    )

    return ScanResult(
        path_id=app_path.id,
        name=app_path.name,
        media_type=media_type,
        path=path,
        inserted=counts["inserted"],
        updated=counts["updated"],
        deleted=counts["deleted"],
        total=len(items),
    )


def scan_enabled_paths(
    db: Session,
) -> list[ScanResult]:
    """
    Scan every enabled configured path.
    """

    paths = (
        db.query(AppPath)
        .filter(
            AppPath.enabled.is_(True)
        )
        .order_by(
            AppPath.media_type,
            AppPath.name,
        )
        .all()
    )

    results = []

    for app_path in paths:
        results.append(
            scan_path(
                db,
                app_path,
            )
        )

    return results


def _scan_books(
    path: str,
):
    """
    Book scanner adapter.

    The book scanner should expose the same CatalogItem
    contract as the other scanners.
    """

    from app.scanners.books import (
        scan_books_folder,
    )

    return scan_books_folder(
        path,
    )
