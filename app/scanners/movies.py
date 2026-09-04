# app/scanners/movies.py

import logging
import re

from app.scanners.types import CatalogItem
from app.storage import get_storage_provider

logger = logging.getLogger(__name__)


VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".m4v",
}


TECHNICAL_TOKENS = {
    "2160p",
    "1080p",
    "720p",
    "576p",
    "480p",
    "2160",
    "1080",
    "720",
    "576",
    "480",
    "4k",
    "8k",
    "uhd",
    "fhd",
    "hd",
    "webdl",
    "web-dl",
    "webrip",
    "web",
    "bluray",
    "blu-ray",
    "brrip",
    "bdrip",
    "dvdrip",
    "hdtv",
    "hdr",
    "hdr10",
    "hdr10+",
    "dolbyvision",
    "dolby-vision",
    "dv",
    "remux",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "avc",
    "aac",
    "ac3",
    "eac3",
    "dts",
    "truehd",
    "atmos",
    "10bit",
    "8bit",
    "proper",
    "repack",
    "extended",
    "unrated",
    "limited",
    "internal",
    "sample",
}


def split_camel_case(
    value: str,
) -> str:
    """
    Insert spaces between camel-case words.

    Examples:

        TheMatrix -> The Matrix
        MyMovieTitle -> My Movie Title
        SpiderManNoWayHome -> Spider Man No Way Home
    """

    return re.sub(
        r"(?<=[a-z])(?=[A-Z])",
        " ",
        value,
    )


def extract_year(
    value: str,
) -> tuple[str, int | None]:
    """
    Extract the first four-digit year from a value.

    Only years from 1900 through 2099 are considered.

    Examples:

        "The Matrix 1999" -> ("The Matrix  ", 1999)
        "Movie 2024 1080p" -> ("Movie   1080p", 2024)
    """

    match = re.search(
        r"(?<!\d)((?:19|20)\d{2})(?!\d)",
        value,
    )

    if not match:
        return value, None

    year = int(match.group(1))

    value = (
        value[:match.start()]
        + " "
        + value[match.end():]
    )

    return value, year


def remove_bracketed_information(
    value: str,
) -> str:
    """
    Remove common bracketed release information.

    Examples:

        Movie [1080p] -> Movie
        Movie (BluRay) -> Movie
    """

    value = re.sub(
        r"\[[^\]]*\]",
        " ",
        value,
    )

    value = re.sub(
        r"\([^)]*\)",
        " ",
        value,
    )

    return value


def normalize_token(
    value: str,
) -> str:
    """
    Normalize a token for technical-token comparison.

    Punctuation surrounding a token is removed so values such as:

        1080p,
        (1080p)
        [1080p]

    are recognized correctly.
    """

    return value.strip(
        " \t\r\n.,;:!?_+-=[]{}()"
    ).lower()


def is_technical_token(
    token: str,
) -> bool:
    """
    Determine whether a filename token represents common
    technical or release information.
    """

    normalized = normalize_token(token)

    if not normalized:
        return False

    if normalized in TECHNICAL_TOKENS:
        return True

    # Common resolution forms not explicitly listed.
    if re.fullmatch(
        r"\d{3,4}p",
        normalized,
    ):
        return True

    # Common audio/video codec patterns.
    if re.fullmatch(
        r"(?:x|h)\d{3,4}",
        normalized,
    ):
        return True

    return False


def clean_movie_title(
    filename: str,
) -> tuple[str, int | None]:
    """
    Convert a potentially messy movie filename into a
    normalized title and optional year.

    Examples:

        The.Matrix.1999.1080p.WEB-DL.x264.mkv
            -> ("The Matrix", 1999)

        TheMatrix1999WEB-DL.mkv
            -> ("The Matrix", 1999)

        Interstellar (2014) 1080p BluRay.mkv
            -> ("Interstellar", 2014)

        Spider-Man.No.Way.Home.2021.2160p.mkv
            -> ("Spider Man No Way Home", 2021)
    """

    # --------------------------------------------------------------
    # Remove the final extension.
    #
    # Do not use pathlib here because filenames may originate
    # from SMB or another non-local storage provider.
    # --------------------------------------------------------------

    value = re.sub(
        r"\.[^.]+$",
        "",
        filename,
    )

    # --------------------------------------------------------------
    # Split camel-case words before normalizing separators.
    # --------------------------------------------------------------

    value = split_camel_case(
        value,
    )

    # --------------------------------------------------------------
    # Extract the year before removing technical information.
    # --------------------------------------------------------------

    value, year = extract_year(
        value,
    )

    # --------------------------------------------------------------
    # Remove bracketed release information.
    # --------------------------------------------------------------

    value = remove_bracketed_information(
        value,
    )

    # --------------------------------------------------------------
    # Normalize common filename separators.
    # --------------------------------------------------------------

    value = re.sub(
        r"[._-]+",
        " ",
        value,
    )

    # --------------------------------------------------------------
    # Remove technical/release tokens.
    # --------------------------------------------------------------

    tokens = value.split()

    cleaned_tokens: list[str] = []

    for token in tokens:
        if is_technical_token(token):
            continue

        cleaned_tokens.append(token)

    value = " ".join(
        cleaned_tokens,
    )

    # --------------------------------------------------------------
    # Collapse whitespace.
    # --------------------------------------------------------------

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value, year


def scan_movies_folder(
    base_path: str,
) -> list[CatalogItem]:
    """
    Scan a movie folder and return normalized catalog items.

    The storage provider is selected automatically from the
    supplied path.

    Supported storage:

        Local filesystem
        SMB

    Supported video formats:

        MKV
        MP4
        AVI
        MOV
        M4V

    Movie metadata is currently derived from filenames.

    The scanner attempts to:

        - Normalize filename separators.
        - Split camel-case filenames.
        - Extract a four-digit year.
        - Remove common release information.
        - Preserve the original filename.
        - Preserve the source directory.
        - Support local and SMB storage transparently.

    Files that cannot produce a usable title are skipped.
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
                "Movie path does not exist: %s",
                base_path,
            )
            return results

        if not storage.is_dir(base_path):
            logger.error(
                "Movie path is not a directory: %s",
                base_path,
            )
            return results

    except Exception:
        logger.exception(
            "Failed to access movie path: %s",
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

            if extension not in VIDEO_EXTENSIONS:
                continue

            # ------------------------------------------------------
            # Extract movie title and year.
            # ------------------------------------------------------

            title, year = clean_movie_title(
                entry.name,
            )

            if not title:
                logger.warning(
                    "Could not determine movie title: %s",
                    entry.path,
                )
                continue

            # ------------------------------------------------------
            # Catalog item.
            # ------------------------------------------------------

            results.append({
                "title": title,
                "creator": "Unknown",
                "collection": "Unknown",
                "genre": "Unknown",
                "year": year,
                "path": entry.path,
                "metadata": {
                    "media_format": extension.lstrip("."),
                    "source_filename": entry.name,
                    "source_directory": entry.parent_name,
                },
            })

    except Exception:
        logger.exception(
            "Movie scan failed for: %s",
            base_path,
        )

    logger.info(
        "Movie scan completed: %d items found in %s",
        len(results),
        base_path,
    )

    return results
