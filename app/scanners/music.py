# app/scanners/music.py

import logging
import re
from typing import Any

from mutagen import File as MutagenFile

from app.scanners.types import CatalogItem
from app.storage import get_storage_provider


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".wav",
    ".ogg",
}


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def tag_value(
    tags: Any,
    keys: tuple[str, ...],
    default: str = "Unknown",
) -> str:
    """
    Return the first usable metadata value.

    Different audio formats use different tag names:

        MP3:
            TIT2
            TPE1
            TALB
            TCON

        MP4/M4A:
            ©nam
            ©ART
            ©alb
            ©gen

        FLAC/Vorbis:
            title
            artist
            album
            genre
    """

    if tags is None:
        return default

    for key in keys:
        try:
            value = tags.get(key)

            if value is None:
                continue

            # Mutagen commonly returns list-like values.
            if isinstance(value, (list, tuple)):
                if not value:
                    continue

                value = value[0]

            text = str(value).strip()

            if text:
                return text

        except Exception:
            logger.debug(
                "Failed reading tag '%s'",
                key,
                exc_info=True,
            )

    return default


def extract_year(
    tags: Any,
) -> int | None:
    """
    Extract a four-digit year from common music metadata.

    Supported examples include:

        MP3:
            TDRC
            TYER
            TDOR

        FLAC/Vorbis:
            date

        MP4/M4A:
            ©day
    """

    value = tag_value(
        tags,
        (
            "TDRC",
            "TYER",
            "TDOR",
            "date",
            "DATE",
            "©day",
        ),
        default="",
    )

    if not value:
        return None

    match = re.search(
        r"(?<!\d)(?:19|20)\d{2}(?!\d)",
        value,
    )

    if not match:
        return None

    try:
        return int(
            match.group(0)
        )
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Filename/path helpers
# ---------------------------------------------------------------------------

def get_source_directory(
    path: str,
) -> str:
    """
    Return the immediate parent directory name.

    Works with:

        /media/music/Artist/song.mp3
        smb://server/Music/Artist/song.mp3
        \\\\server\\Music\\Artist\\song.mp3
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


def get_filename_without_extension(
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


def clean_filename_title(
    filename: str,
) -> str:
    """
    Produce a reasonable title fallback from a filename.

    Common separators are converted to spaces and whitespace
    is normalized.

    Examples:

        Song_Title.mp3
            -> Song Title

        Song.Title.mp3
            -> Song Title

        Song-Title.mp3
            -> Song Title
    """

    value = get_filename_without_extension(
        filename
    )

    # Insert spaces between common camel-case boundaries.
    value = re.sub(
        r"(?<=[a-z])(?=[A-Z])",
        " ",
        value,
    )

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


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_music_folder(
    base_path: str,
) -> list[CatalogItem]:
    """
    Scan a music folder and return normalized catalog items.

    The storage provider is selected automatically from the supplied
    path, allowing both local filesystem and SMB locations.

    Supported formats:

        MP3
        FLAC
        M4A
        WAV
        OGG

    Metadata priority:

        1. Embedded audio metadata
        2. Filename fallback for title

    Files that cannot be read are skipped and logged.
    """

    results: list[CatalogItem] = []

    # ------------------------------------------------------------------
    # Select storage backend.
    # ------------------------------------------------------------------

    try:
        storage = get_storage_provider(
            base_path
        )

    except Exception:
        logger.exception(
            "Failed to create storage provider for: %s",
            base_path,
        )

        return results

    # ------------------------------------------------------------------
    # Validate configured path.
    # ------------------------------------------------------------------

    try:
        if not storage.exists(
            base_path
        ):
            logger.error(
                "Music path does not exist: %s",
                base_path,
            )

            return results

        if not storage.is_dir(
            base_path
        ):
            logger.error(
                "Music path is not a directory: %s",
                base_path,
            )

            return results

    except Exception:
        logger.exception(
            "Failed to access music path: %s",
            base_path,
        )

        return results

    # ------------------------------------------------------------------
    # Recursive scan.
    # ------------------------------------------------------------------

    try:
        for entry in storage.walk(
            base_path
        ):
            logger.debug(
                "Scanning: %s",
                entry.path,
            )

            if not entry.is_file:
                continue

            extension = entry.suffix.lower()

            if extension not in AUDIO_EXTENSIONS:
                continue

            # ----------------------------------------------------------
            # Read metadata through the storage provider.
            #
            # This is important for SMB: the scanner never needs the
            # network share to be mounted locally.
            # ----------------------------------------------------------

            try:
                with storage.open(
                    entry.path,
                    "rb",
                ) as file_handle:

                    file_handle.seek(0)

                    audio = MutagenFile(
                        file_handle
                    )

            except Exception:
                logger.exception(
                    "Failed to read audio file: %s",
                    entry.path,
                )

                continue

            if audio is None:
                logger.warning(
                    "Unsupported or unreadable audio file: %s",
                    entry.path,
                )

                continue

            tags = audio.tags

            if tags is None:
                logger.debug(
                    "No metadata tags found: %s",
                    entry.path,
                )

                tags = {}

            # ----------------------------------------------------------
            # Title
            # ----------------------------------------------------------

            title = tag_value(
                tags,
                (
                    "TIT2",
                    "©nam",
                    "title",
                    "TITLE",
                ),
                default=clean_filename_title(
                    entry.name
                ),
            )

            if not title:
                logger.warning(
                    "Could not determine title: %s",
                    entry.path,
                )

                continue

            # ----------------------------------------------------------
            # Artist
            # ----------------------------------------------------------

            artist = tag_value(
                tags,
                (
                    "TPE1",
                    "©ART",
                    "artist",
                    "ARTIST",
                ),
            )

            # ----------------------------------------------------------
            # Album
            # ----------------------------------------------------------

            album = tag_value(
                tags,
                (
                    "TALB",
                    "©alb",
                    "album",
                    "ALBUM",
                ),
            )

            # ----------------------------------------------------------
            # Genre
            # ----------------------------------------------------------

            genre = tag_value(
                tags,
                (
                    "TCON",
                    "©gen",
                    "genre",
                    "GENRE",
                ),
            )

            # ----------------------------------------------------------
            # Year
            # ----------------------------------------------------------

            year = extract_year(
                tags
            )

            # ----------------------------------------------------------
            # Catalog item
            # ----------------------------------------------------------

            results.append(
                {
                    "title": title,
                    "creator": artist,
                    "collection": album,
                    "genre": genre,
                    "year": year,
                    "path": entry.path,
                    "metadata": {
                        "media_format": extension.lstrip("."),
                        "source_filename": entry.name,
                        "source_directory": get_source_directory(
                            entry.path
                        ),
                    },
                }
            )

    except Exception:
        logger.exception(
            "Music scan failed for: %s",
            base_path,
        )

    logger.info(
        "Music scan completed: %d items found in %s",
        len(results),
        base_path,
    )

    return results
