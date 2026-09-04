# app/scanners/types/catalog_item.py

from typing import TypedDict


class CatalogMetadata(TypedDict, total=False):
    """
    Metadata attached to a catalog item.

    The common fields are available to every scanner. Individual
    media scanners may populate additional fields.

    All fields are optional because scanners do not necessarily
    have access to every piece of metadata.
    """

    # ------------------------------------------------------------------
    # Common media metadata
    # ------------------------------------------------------------------

    media_format: str
    source_filename: str
    source_directory: str

    # ------------------------------------------------------------------
    # TV metadata
    # ------------------------------------------------------------------

    series: str
    season: int | None
    episode: int | None

    # ------------------------------------------------------------------
    # Book metadata
    # ------------------------------------------------------------------

    isbn: str
    publisher: str
    language: str

    # ------------------------------------------------------------------
    # Music metadata
    # ------------------------------------------------------------------

    disc_number: int | None
    track_number: int | None

    # ------------------------------------------------------------------
    # Future / provider-specific metadata
    #
    # Scanners may add additional values without changing the
    # CatalogItem structure itself.
    # ------------------------------------------------------------------


class CatalogItem(TypedDict):
    """
    Standard output contract for all catalog scanners.

    Every scanner returns a list of CatalogItem objects.

    The catalog service is deliberately independent of the scanner
    implementation. A scanner is responsible only for discovering
    media and normalizing its metadata into this structure.

    The catalog service is then responsible for persistence,
    deduplication and embedding generation.
    """

    # ------------------------------------------------------------------
    # Core catalog fields
    # ------------------------------------------------------------------

    title: str
    creator: str
    collection: str
    genre: str
    year: int | None

    # ------------------------------------------------------------------
    # Original storage location
    #
    # This is the canonical path returned by the storage provider and
    # is used by the catalog service for item identity/deduplication.
    # ------------------------------------------------------------------

    path: str

    # ------------------------------------------------------------------
    # Scanner-specific metadata
    # ------------------------------------------------------------------

    metadata: CatalogMetadata
