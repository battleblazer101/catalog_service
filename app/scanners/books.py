# app/scanners/books.py

import logging
import re
from typing import Any

from ebooklib import epub
from pypdf import PdfReader

from app.scanners.types import CatalogItem
from app.storage import get_storage_provider

logger = logging.getLogger(__name__)


BOOK_EXTENSIONS = {
    ".pdf",
    ".epub",
}


def clean_text(
    value: str,
) -> str:
    """
    Normalize whitespace and common filename separators.
    """

    value = value.strip()

    value = re.sub(
        r"[._-]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def split_camel_case(
    value: str,
) -> str:
    """
    Insert spaces between camel-case words.

    Examples:

        TheHobbit -> The Hobbit
        HarryPotter -> Harry Potter
    """

    return re.sub(
        r"(?<=[a-z])(?=[A-Z])",
        " ",
        value,
    )


def clean_title(
    value: str,
) -> str:
    """
    Normalize a book title extracted from metadata or a filename.
    """

    value = split_camel_case(
        value,
    )

    value = clean_text(
        value,
    )

    return value


def extract_year(
    value: str,
) -> int | None:
    """
    Extract the first four-digit year from a value.

    Only years from 1900 through 2099 are considered.
    """

    match = re.search(
        r"(?<!\d)((?:19|20)\d{2})(?!\d)",
        value,
    )

    if not match:
        return None

    try:
        return int(
            match.group(1)
        )
    except ValueError:
        return None


def filename_without_extension(
    filename: str,
) -> str:
    """
    Return a filename without its final extension.

    This deliberately avoids pathlib because the filename may
    originate from SMB or another non-local storage provider.
    """

    return re.sub(
        r"\.[^.]+$",
        "",
        filename,
    )


def get_source_directory(
    path: str,
) -> str:
    """
    Extract the immediate parent directory name.

    Supports:

        /media/books/Author/book.epub
        smb://server/books/Author/book.epub
        \\\\server\\books\\Author\\book.epub
    """

    value = path.strip()

    value = value.rstrip(
        "/\\"
    )

    if not value:
        return ""

    parts = [
        part
        for part in re.split(
            r"[/\\]+",
            value,
        )
        if part
    ]

    if len(parts) < 2:
        return ""

    return parts[-2]


def tag_text(
    value: Any,
) -> str | None:
    """
    Convert an EPUB metadata value into usable text.

    EbookLib commonly returns values as tuples such as:

        (value, attributes)

    or plain strings.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (list, tuple),
    ):
        if not value:
            return None

        # EbookLib metadata is often represented as:
        #
        # ("Title", {})
        #
        # Prefer the first element containing actual text.
        for item in value:
            if isinstance(
                item,
                str,
            ):
                text = item.strip()

                if text:
                    return text

        value = value[0]

    if isinstance(
        value,
        bytes,
    ):
        try:
            value = value.decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            return None

    text = str(
        value
    ).strip()

    return text or None


def epub_metadata_value(
    book: Any,
    namespace: str,
    key: str,
) -> str | None:
    """
    Safely read an EPUB metadata value.

    EbookLib exposes metadata through get_metadata().
    """

    try:
        values = book.get_metadata(
            namespace,
            key,
        )

    except Exception:
        logger.debug(
            "Failed reading EPUB metadata: %s",
            key,
            exc_info=True,
        )
        return None

    if not values:
        return None

    for value in values:
        text = tag_text(
            value
        )

        if text:
            return text

    return None


def extract_epub_metadata(
    file_handle: Any,
) -> dict[str, Any]:
    """
    Extract metadata from an EPUB file.

    Returns:

        {
            "title": str | None,
            "creator": str | None,
            "collection": str | None,
            "genre": str | None,
            "year": int | None,
        }

    The EPUB is read from a file-like object so the scanner
    remains storage-provider agnostic.
    """

    metadata: dict[str, Any] = {
        "title": None,
        "creator": None,
        "collection": None,
        "genre": None,
        "year": None,
    }

    try:
        file_handle.seek(0)

        book = epub.read_epub(
            file_handle,
        )

    except Exception:
        logger.exception(
            "Failed to read EPUB metadata",
        )
        return metadata

    metadata["title"] = epub_metadata_value(
        book,
        "DC",
        "title",
    )

    metadata["creator"] = epub_metadata_value(
        book,
        "DC",
        "creator",
    )

    metadata["collection"] = epub_metadata_value(
        book,
        "DC",
        "subject",
    )

    metadata["genre"] = epub_metadata_value(
        book,
        "DC",
        "subject",
    )

    date_value = epub_metadata_value(
        book,
        "DC",
        "date",
    )

    if date_value:
        metadata["year"] = extract_year(
            date_value,
        )

    return metadata


def extract_pdf_metadata(
    file_handle: Any,
) -> dict[str, Any]:
    """
    Extract metadata from a PDF file.

    Returns:

        {
            "title": str | None,
            "creator": str | None,
            "collection": str | None,
            "genre": str | None,
            "year": int | None,
        }
    """

    metadata: dict[str, Any] = {
        "title": None,
        "creator": None,
        "collection": None,
        "genre": None,
        "year": None,
    }

    try:
        file_handle.seek(0)

        reader = PdfReader(
            file_handle,
        )

        pdf_metadata = reader.metadata

    except Exception:
        logger.exception(
            "Failed to read PDF metadata",
        )
        return metadata

    if pdf_metadata is None:
        return metadata

    # --------------------------------------------------------------
    # Title
    # --------------------------------------------------------------

    title = getattr(
        pdf_metadata,
        "title",
        None,
    )

    if title:
        metadata["title"] = str(
            title
        ).strip()

    # --------------------------------------------------------------
    # Author
    # --------------------------------------------------------------

    author = getattr(
        pdf_metadata,
        "author",
        None,
    )

    if author:
        metadata["creator"] = str(
            author
        ).strip()

    # --------------------------------------------------------------
    # Subject
    # --------------------------------------------------------------

    subject = getattr(
        pdf_metadata,
        "subject",
        None,
    )

    if subject:
        metadata["collection"] = str(
            subject
        ).strip()

    # --------------------------------------------------------------
    # Creation date
    # --------------------------------------------------------------

    creation_date = getattr(
        pdf_metadata,
        "creation_date",
        None,
    )

    if creation_date:
        metadata["year"] = extract_year(
            str(creation_date)
        )

    # --------------------------------------------------------------
    # Some PDFs expose the raw metadata dictionary instead.
    # --------------------------------------------------------------

    if metadata["title"] is None:
        raw_title = pdf_metadata.get(
            "/Title"
        )

        if raw_title:
            metadata["title"] = str(
                raw_title
            ).strip()

    if metadata["creator"] is None:
        raw_author = pdf_metadata.get(
            "/Author"
        )

        if raw_author:
            metadata["creator"] = str(
                raw_author
            ).strip()

    if metadata["collection"] is None:
        raw_subject = pdf_metadata.get(
            "/Subject"
        )

        if raw_subject:
            metadata["collection"] = str(
                raw_subject
            ).strip()

    if metadata["year"] is None:
        raw_creation_date = pdf_metadata.get(
            "/CreationDate"
        )

        if raw_creation_date:
            metadata["year"] = extract_year(
                str(raw_creation_date)
            )

    return metadata


def extract_book_metadata(
    storage,
    path: str,
    extension: str,
) -> dict[str, Any]:
    """
    Read embedded metadata from a book.

    The storage provider is responsible for opening the file,
    allowing this function to work with local and SMB storage.
    """

    metadata: dict[str, Any] = {
        "title": None,
        "creator": None,
        "collection": None,
        "genre": None,
        "year": None,
    }

    try:
        with storage.open(
            path,
            "rb",
        ) as file_handle:

            if extension == ".epub":
                return extract_epub_metadata(
                    file_handle
                )

            if extension == ".pdf":
                return extract_pdf_metadata(
                    file_handle
                )

    except Exception:
        logger.exception(
            "Failed to extract book metadata: %s",
            path,
        )

    return metadata


def scan_books_folder(
    base_path: str,
) -> list[CatalogItem]:
    """
    Scan a book folder and return normalized catalog items.

    The storage provider is selected automatically from the
    supplied path.

    Supported storage:

        Local filesystem
        SMB

    Supported book formats:

        PDF
        EPUB

    Metadata priority:

        1. Embedded document metadata
        2. Filename fallback for title
        3. Directory fallback for creator

    Files that cannot be read are still allowed to enter the
    catalog when a usable filename title can be determined.
    """

    results: list[CatalogItem] = []

    # --------------------------------------------------------------
    # Select storage backend.
    # --------------------------------------------------------------

    try:
        storage = get_storage_provider(
            base_path,
        )

    except Exception:
        logger.exception(
            "Failed to create storage provider for: %s",
            base_path,
        )
        return results

    # --------------------------------------------------------------
    # Validate configured path.
    # --------------------------------------------------------------

    try:
        if not storage.exists(base_path):
            logger.error(
                "Book path does not exist: %s",
                base_path,
            )
            return results

        if not storage.is_dir(base_path):
            logger.error(
                "Book path is not a directory: %s",
                base_path,
            )
            return results

    except Exception:
        logger.exception(
            "Failed to access book path: %s",
            base_path,
        )
        return results

    # --------------------------------------------------------------
    # Scan recursively.
    # --------------------------------------------------------------

    try:
        for entry in storage.walk(
            base_path,
        ):
            logger.debug(
                "Scanning: %s",
                entry.path,
            )

            if not entry.is_file:
                continue

            extension = entry.suffix.lower()

            if extension not in BOOK_EXTENSIONS:
                continue

            # ------------------------------------------------------
            # Filename fallback.
            # ------------------------------------------------------

            fallback_title = clean_title(
                filename_without_extension(
                    entry.name,
                )
            )

            source_directory = get_source_directory(
                entry.path,
            )

            fallback_creator = clean_title(
                source_directory,
            )

            # ------------------------------------------------------
            # Extract embedded metadata.
            # ------------------------------------------------------

            metadata = extract_book_metadata(
                storage,
                entry.path,
                extension,
            )

            title = metadata.get(
                "title"
            )

            creator = metadata.get(
                "creator"
            )

            collection = metadata.get(
                "collection"
            )

            genre = metadata.get(
                "genre"
            )

            year = metadata.get(
                "year"
            )

            # ------------------------------------------------------
            # Normalize metadata.
            # ------------------------------------------------------

            if title:
                title = clean_title(
                    str(title)
                )

            if creator:
                creator = clean_text(
                    str(creator)
                )

            if collection:
                collection = clean_text(
                    str(collection)
                )

            if genre:
                genre = clean_text(
                    str(genre)
                )

            # ------------------------------------------------------
            # Apply fallbacks.
            # ------------------------------------------------------

            if not title:
                title = fallback_title

            if not creator:
                creator = (
                    fallback_creator
                    if fallback_creator
                    else "Unknown"
                )

            if not collection:
                collection = "Unknown"

            if not genre:
                genre = "Unknown"

            # ------------------------------------------------------
            # Year fallback from filename.
            # ------------------------------------------------------

            if year is None:
                year = extract_year(
                    entry.name,
                )

            # ------------------------------------------------------
            # A book without a title cannot be catalogued.
            # ------------------------------------------------------

            if not title:
                logger.warning(
                    "Could not determine book title: %s",
                    entry.path,
                )
                continue

            # ------------------------------------------------------
            # Catalog item.
            # ------------------------------------------------------

            results.append({
                "title": title,
                "creator": creator,
                "collection": collection,
                "genre": genre,
                "year": year,
                "path": entry.path,
                "metadata": {
                    "media_format": extension.lstrip("."),
                    "source_filename": entry.name,
                    "source_directory": source_directory,
                },
            })

    except Exception:
        logger.exception(
            "Book scan failed for: %s",
            base_path,
        )

    logger.info(
        "Book scan completed: %d items found in %s",
        len(results),
        base_path,
    )

    return results
