# app/main.py

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    SERVICE_NAME,
    VERSION,
)
from app.database.database import (
    Base,
    engine,
    get_db,
)
from app.models.app_path import AppPath
from app.models.media import MediaItem
from app.scanners.books import scan_books_folder
from app.scanners.movies import scan_movies_folder
from app.scanners.music import scan_music_folder
from app.scanners.tv import scan_tv_folder
from app.services.app_path_service import (
    create_path,
    delete_path,
    get_path,
    list_paths,
    update_path,
)
from app.services.catalog_service import (
    get_item,
    insert_media_items,
    list_items,
)
from app.services.search_service import (
    search_items,
)
from app.services.semantic_search_service import (
    semantic_search_items,
)


# ===========================================================================
# Application lifecycle
# ===========================================================================

@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Application startup/shutdown lifecycle.

    Alembic remains the preferred schema-management mechanism.

    create_all() is retained as a development compatibility fallback.
    """

    Base.metadata.create_all(
        bind=engine,
    )

    yield


app = FastAPI(
    title="Catalog Service",
    version=VERSION,
    lifespan=lifespan,
)


# ===========================================================================
# Root
# ===========================================================================

@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": VERSION,
    }


# ===========================================================================
# Health
# ===========================================================================

@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }


# ===========================================================================
# App Paths
# ===========================================================================

class AppPathCreate(BaseModel):
    name: str = Field(
        min_length=1,
    )
    path: str = Field(
        min_length=1,
    )
    media_type: str = Field(
        min_length=1,
    )
    description: str | None = None
    enabled: bool = True


class AppPathUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    media_type: str | None = None
    description: str | None = None
    enabled: bool | None = None


def serialize_app_path(
    app_path: AppPath,
) -> dict[str, Any]:
    """
    Serialize an AppPath model into the public API representation.
    """

    return {
        "id": app_path.id,
        "name": app_path.name,
        "path": app_path.path,
        "media_type": app_path.media_type,
        "description": app_path.description,
        "enabled": app_path.enabled,
        "created_at": getattr(
            app_path,
            "created_at",
            None,
        ),
        "updated_at": getattr(
            app_path,
            "updated_at",
            None,
        ),
    }


@app.get("/catalog/paths")
def get_paths(
    media_type: str | None = Query(
        default=None,
    ),
    enabled_only: bool = Query(
        default=False,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List configured catalog paths.
    """

    try:
        paths = list_paths(
            db,
            media_type=media_type,
            enabled_only=enabled_only,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "count": len(paths),
        "paths": [
            serialize_app_path(path)
            for path in paths
        ],
    }


@app.get("/catalog/paths/{path_id}")
def get_single_path(
    path_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get one configured catalog path.
    """

    app_path = get_path(
        db,
        path_id,
    )

    if app_path is None:
        raise HTTPException(
            status_code=404,
            detail="AppPath not found",
        )

    return serialize_app_path(
        app_path,
    )


@app.post(
    "/catalog/paths",
    status_code=201,
)
def create_app_path(
    payload: AppPathCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a configured catalog path.
    """

    try:
        app_path = create_path(
            db=db,
            name=payload.name,
            path=payload.path,
            media_type=payload.media_type,
            description=payload.description,
            enabled=payload.enabled,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="A path with this filesystem path already exists",
        ) from exc

    return serialize_app_path(
        app_path,
    )


@app.put("/catalog/paths/{path_id}")
def update_app_path(
    path_id: int,
    payload: AppPathUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Update a configured catalog path.
    """

    app_path = get_path(
        db,
        path_id,
    )

    if app_path is None:
        raise HTTPException(
            status_code=404,
            detail="AppPath not found",
        )

    try:
        app_path = update_path(
            db=db,
            app_path=app_path,
            name=payload.name,
            path=payload.path,
            media_type=payload.media_type,
            description=payload.description,
            enabled=payload.enabled,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="A path with this filesystem path already exists",
        ) from exc

    return serialize_app_path(
        app_path,
    )


@app.delete("/catalog/paths/{path_id}")
def delete_app_path(
    path_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Delete a configured catalog path.

    This removes only the configuration. It does not delete the
    discovered media records or physical media files.
    """

    app_path = get_path(
        db,
        path_id,
    )

    if app_path is None:
        raise HTTPException(
            status_code=404,
            detail="AppPath not found",
        )

    delete_path(
        db,
        app_path,
    )

    return {
        "deleted": True,
        "id": path_id,
    }


# ===========================================================================
# Scanning
# ===========================================================================

def scan_path(
    db: Session,
    app_path: AppPath,
) -> dict[str, Any]:
    """
    Scan one configured path and insert newly discovered items.
    """

    scanner_map = {
        "music": scan_music_folder,
        "movie": scan_movies_folder,
        "tv": scan_tv_folder,
        "book": scan_books_folder,
    }

    scanner = scanner_map.get(
        app_path.media_type,
    )

    if scanner is None:
        raise ValueError(
            f"Unsupported media type: "
            f"{app_path.media_type}"
        )

    items = scanner(
        app_path.path,
    )

    inserted = insert_media_items(
        db,
        items,
        app_path.media_type,
    )

    return {
        "path_id": app_path.id,
        "name": app_path.name,
        "path": app_path.path,
        "media_type": app_path.media_type,
        "scanned": len(items),
        "inserted": inserted,
    }


@app.post("/catalog/scan")
def scan_catalog(
    media_type: str | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scan all enabled configured paths.

    Optionally restrict the scan to one media type.
    """

    try:
        paths = list_paths(
            db,
            media_type=media_type,
            enabled_only=True,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    results: list[dict[str, Any]] = []

    total_scanned = 0
    total_inserted = 0

    for app_path in paths:
        try:
            result = scan_path(
                db,
                app_path,
            )

        except Exception as exc:
            db.rollback()

            results.append({
                "path_id": app_path.id,
                "name": app_path.name,
                "path": app_path.path,
                "media_type": app_path.media_type,
                "scanned": 0,
                "inserted": 0,
                "error": str(exc),
            })

            continue

        results.append(
            result
        )

        total_scanned += result["scanned"]
        total_inserted += result["inserted"]

    return {
        "media_type": media_type,
        "paths_scanned": len(results),
        "scanned": total_scanned,
        "inserted": total_inserted,
        "results": results,
    }


@app.post("/catalog/scan/paths/{path_id}")
def scan_single_path(
    path_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scan one configured path.
    """

    app_path = get_path(
        db,
        path_id,
    )

    if app_path is None:
        raise HTTPException(
            status_code=404,
            detail="AppPath not found",
        )

    try:
        return scan_path(
            db,
            app_path,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Scan failed: {exc}",
        ) from exc


@app.post("/catalog/scan/music")
def scan_music(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scan all enabled music paths.
    """

    return scan_catalog(
        media_type="music",
        db=db,
    )


@app.post("/catalog/scan/movies")
def scan_movies(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scan all enabled movie paths.
    """

    return scan_catalog(
        media_type="movie",
        db=db,
    )


@app.post("/catalog/scan/tv")
def scan_tv(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scan all enabled TV paths.
    """

    return scan_catalog(
        media_type="tv",
        db=db,
    )


@app.post("/catalog/scan/books")
def scan_books(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scan all enabled book paths.
    """

    return scan_catalog(
        media_type="book",
        db=db,
    )


# ===========================================================================
# Items
# ===========================================================================

@app.get("/catalog/items")
def get_items(
    media_type: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List catalog items with optional media-type filtering.
    """

    try:
        items = list_items(
            db,
            media_type=media_type,
            limit=limit,
            offset=offset,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "count": len(items),
        "items": [
            serialize_media_item(
                item
            )
            for item in items
        ],
    }


@app.get("/catalog/items/{item_id}")
def get_single_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get one catalog item.
    """

    item = get_item(
        db,
        item_id,
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="MediaItem not found",
        )

    return serialize_media_item(
        item
    )


def serialize_media_item(
    item: MediaItem,
) -> dict[str, Any]:
    """
    Serialize a MediaItem without exposing the stored embedding
    vector through the public catalog API.
    """

    return {
        "id": item.id,
        "media_type": item.media_type,
        "title": item.title,
        "creator": item.creator,
        "collection": item.collection,
        "genre": item.genre,
        "year": item.year,
        "path": item.path,
        "metadata": item.metadata_json,
        "embedding_model": item.embedding_model,
        "embedding_created_at": getattr(
            item,
            "embedding_created_at",
            None,
        ),
    }


# ===========================================================================
# Search
# ===========================================================================

@app.get("/catalog/search")
def search_catalog(
    query: str = Query(
        min_length=1,
    ),
    media_type: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Perform traditional lexical catalog search.
    """

    try:
        results = search_items(
            db=db,
            query=query,
            media_type=media_type,
            limit=limit,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    serialized = []

    for item, score in results:
        serialized.append({
            **serialize_media_item(item),
            "score": float(score),
        })

    return {
        "query": query,
        "count": len(serialized),
        "results": serialized,
    }


@app.get("/catalog/search/semantic")
def semantic_search_catalog(
    query: str = Query(
        min_length=1,
    ),
    media_type: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Perform semantic catalog search using stored embeddings.
    """

    try:
        results = semantic_search_items(
            db=db,
            query=query,
            media_type=media_type,
            limit=limit,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    serialized = []

    for item, score in results:
        serialized.append({
            **serialize_media_item(item),
            "score": float(score),
        })

    return {
        "query": query,
        "count": len(serialized),
        "results": serialized,
    }


# ===========================================================================
# Statistics
# ===========================================================================

@app.get("/catalog/stats")
def stats(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return catalog and embedding statistics.
    """

    total_items = (
        db.query(
            MediaItem
        )
        .count()
    )

    music_items = (
        db.query(
            MediaItem
        )
        .filter(
            MediaItem.media_type == "music"
        )
        .count()
    )

    movie_items = (
        db.query(
            MediaItem
        )
        .filter(
            MediaItem.media_type == "movie"
        )
        .count()
    )

    tv_items = (
        db.query(
            MediaItem
        )
        .filter(
            MediaItem.media_type == "tv"
        )
        .count()
    )

    book_items = (
        db.query(
            MediaItem
        )
        .filter(
            MediaItem.media_type == "book"
        )
        .count()
    )

    embedded_items = (
        db.query(
            MediaItem
        )
        .filter(
            MediaItem.embedding.isnot(None)
        )
        .count()
    )

    missing_embeddings = (
        db.query(
            MediaItem
        )
        .filter(
            MediaItem.embedding.is_(None)
        )
        .count()
    )

    embedding_coverage = (
        round(
            embedded_items
            / total_items
            * 100,
            2,
        )
        if total_items > 0
        else 0.0
    )

    return {
        "total_items": total_items,
        "music_items": music_items,
        "movie_items": movie_items,
        "tv_items": tv_items,
        "book_items": book_items,
        "embedded_items": embedded_items,
        "missing_embeddings": missing_embeddings,
        "embedding_coverage": embedding_coverage,
    }
