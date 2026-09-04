# app/scanners/tv.py

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

        BreakingBad -> Breaking Bad
        TheOffice -> The Office
        BetterCallSaul -> Better Call Saul
    """

    return re.sub(
        r"(?<=[a-z])(?=[A-Z])",
        " ",
        value,
    )


def clean_text(
    value: str,
) -> str:
    """
    Normalize common filename and directory separators.
    """

    value = split_camel_case(
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


def extract_year(
    value: str,
) -> tuple[str, int | None]:
    """
    Extract a four-digit year.

    Only years from 1900 through 2099 are considered.
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


def clean_series_name(
    value: str,
) -> tuple[str, int | None]:
    """
    Clean the series directory name and optionally extract
    a release/year value.

    Examples:

        Breaking.Bad
            -> ("Breaking Bad", None)

        BreakingBad
            -> ("Breaking Bad", None)

        The.Office.US.2005
            -> ("The Office US", 2005)

        TheOfficeUS2005
            -> ("The Office US", 2005)
    """

    value, year = extract_year(
        value,
    )

    value = clean_text(
        value,
    )

    return value, year


def extract_season_from_directory(
    directory_name: str,
) -> int | None:
    """
    Extract a season number from a directory name.

    Supported examples:

        Season 01
        Season.01
        Season-01
        Season_01
        S01
        s01
        Specials
        Special

    Specials are represented as season 0.
    """

    normalized = directory_name.strip()

    if re.fullmatch(
        r"(?i)specials?",
        normalized,
    ):
        return 0

    match = re.search(
        r"(?i)\bSeason[ ._-]*(\d{1,3})\b",
        normalized,
    )

    if match:
        return int(
            match.group(1)
        )

    match = re.search(
        r"(?i)^S[ ._-]*(\d{1,3})$",
        normalized,
    )

    if match:
        return int(
            match.group(1)
        )

    return None


def extract_episode_info(
    filename: str,
) -> tuple[
    int | None,
    int | None,
    str,
]:
    """
    Extract season, episode and remaining filename text.

    Supported patterns include:

        S01E01
        s01e01
        S1E1
        1x01
        01x01
        Season 1 Episode 1
        Season.1.Episode.1
        Season 1 Ep 1

    Returns:

        (
            season,
            episode,
            remaining_filename,
        )

    If no episode pattern is found:

        (None, None, filename_without_extension)
    """

    # --------------------------------------------------------------
    # Remove the final extension.
    # --------------------------------------------------------------

    value = re.sub(
        r"\.[^.]+$",
        "",
        filename,
    )

    # --------------------------------------------------------------
    # S01E01
    # --------------------------------------------------------------

    match = re.search(
        r"(?i)\bS(\d{1,3})E(\d{1,4})\b",
        value,
    )

    if match:
        season = int(
            match.group(1)
        )

        episode = int(
            match.group(2)
        )

        remaining = (
            value[:match.start()]
            + " "
            + value[match.end():]
        )

        return (
            season,
            episode,
            remaining,
        )

    # --------------------------------------------------------------
    # 1x01
    # --------------------------------------------------------------

    match = re.search(
        r"(?i)\b(\d{1,3})x(\d{1,4})\b",
        value,
    )

    if match:
        season = int(
            match.group(1)
        )

        episode = int(
            match.group(2)
        )

        remaining = (
            value[:match.start()]
            + " "
            + value[match.end():]
        )

        return (
            season,
            episode,
            remaining,
        )

    # --------------------------------------------------------------
    # Season 1 Episode 1
    # Season.1.Episode.1
    # Season 1 Ep 1
    # --------------------------------------------------------------

    match = re.search(
        r"(?i)\bSeason[ ._-]*"
        r"(\d{1,3})"
        r"[ ._-]*"
        r"(?:Episode|Ep)[ ._-]*"
        r"(\d{1,4})\b",
        value,
    )

    if match:
        season = int(
            match.group(1)
        )

        episode = int(
            match.group(2)
        )

        remaining = (
            value[:match.start()]
            + " "
            + value[match.end():]
        )

        return (
            season,
            episode,
            remaining,
        )

    return (
        None,
        None,
        value,
    )


def remove_series_prefix(
    value: str,
    series: str,
) -> str:
    """
    Remove a series-name prefix from an episode filename.

    Handles differences such as:

        BreakingBad
        Breaking.Bad
        Breaking-Bad
        Breaking Bad
    """

    value_normalized = re.sub(
        r"[\s._-]+",
        "",
        value,
    ).lower()

    series_normalized = re.sub(
        r"[\s._-]+",
        "",
        series,
    ).lower()

    if not value_normalized.startswith(
        series_normalized
    ):
        return value

    series_words = series.split()

    if not series_words:
        return value

    pattern = r"[\s._-]*".join(
        re.escape(word)
        for word in series_words
    )

    value = re.sub(
        rf"(?i)^{pattern}",
        "",
        value,
    )

    return value


def is_technical_token(
    token: str,
) -> bool:
    """
    Determine whether a token represents common release,
    video or audio information.
    """

    normalized = token.strip(
        " \t\r\n.,;:!?_+-=[]{}()"
    ).lower()

    if not normalized:
        return False

    if normalized in TECHNICAL_TOKENS:
        return True

    if re.fullmatch(
        r"\d{3,4}p",
        normalized,
    ):
        return True

    if re.fullmatch(
        r"(?:x|h)\d{3,4}",
        normalized,
    ):
        return True

    return False


def clean_episode_title(
    value: str,
    series: str,
) -> str:
    """
    Convert the remaining filename text into an episode title.

    Examples:

        Breaking.Bad.S01E01.Pilot.1080p.mkv
            -> Pilot

        BreakingBad.S01E02.The.Boys.1080p.WEB-DL.mkv
            -> The Boys

        S01E03.Some.Episode.Title.mkv
            -> Some Episode Title
    """

    # --------------------------------------------------------------
    # Remove series prefix.
    # --------------------------------------------------------------

    value = remove_series_prefix(
        value,
        series,
    )

    # --------------------------------------------------------------
    # Remove year values.
    # --------------------------------------------------------------

    value = re.sub(
        r"(?<!\d)(?:19|20)\d{2}(?!\d)",
        " ",
        value,
    )

    # --------------------------------------------------------------
    # Remove bracketed release information.
    # --------------------------------------------------------------

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

    # --------------------------------------------------------------
    # Normalize separators before token processing.
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

    return value


def get_path_components(
    path: str,
) -> list[str]:
    """
    Split a local, UNC or SMB path into components.

    Supports:

        /media/tv/Breaking Bad/Season 01/Episode.mkv

        \\\\server\\share\\TV\\Breaking Bad\\Season 01\\Episode.mkv

        smb://server/share/TV/Breaking Bad/Season 01/Episode.mkv
    """

    value = path.strip()

    # --------------------------------------------------------------
    # SMB URL.
    # --------------------------------------------------------------

    if value.lower().startswith(
        "smb://"
    ):
        value = value[6:]

    return [
        component
        for component in re.split(
            r"[\\/]+",
            value,
        )
        if component
    ]


def get_parent_directory_name(
    path: str,
) -> str | None:
    """
    Return the immediate parent directory name.
    """

    components = get_path_components(
        path,
    )

    if len(components) < 2:
        return None

    return components[-2]


def get_series_directory_name(
    path: str,
) -> str | None:
    """
    Determine the series directory name.

    The immediate parent directory is normally the series
    directory.

    If the immediate parent is a season directory, the
    directory above it is used as the series directory.

    Examples:

        TV/Breaking Bad/Episode.mkv
            -> Breaking Bad

        TV/Breaking Bad/Season 01/Episode.mkv
            -> Breaking Bad

        TV/Breaking Bad/S01/Episode.mkv
            -> Breaking Bad
    """

    components = get_path_components(
        path,
    )

    if len(components) < 2:
        return None

    parent_directory = components[-2]

    if extract_season_from_directory(
        parent_directory,
    ) is not None:

        if len(components) < 3:
            return None

        return components[-3]

    return parent_directory


def scan_tv_folder(
    base_path: str,
) -> list[CatalogItem]:
    """
    Scan a TV folder and return normalized catalog items.

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

    Supported TV structures include:

        TV/
        └── Breaking Bad/
            ├── Breaking.Bad.S01E01.Pilot.mkv
            └── Breaking.Bad.S01E02.Cat's.in.the.Bag.mkv

    And:

        TV/
        └── Breaking Bad/
            ├── Season 01/
            │   ├── S01E01.Pilot.mkv
            │   └── S01E02.Cat's.in.the.Bag.mkv
            └── Season 02/
                └── S02E01.Seven.Thirty-Seven.mkv

    Series name priority:

        1. Series directory

    Season priority:

        1. Season from filename
        2. Season from directory

    Episode:

        Extracted from the filename.

    Year priority:

        1. Year from series directory
        2. Year from filename

    Files that cannot be completely parsed are still catalogued.
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
                "TV path does not exist: %s",
                base_path,
            )
            return results

        if not storage.is_dir(base_path):
            logger.error(
                "TV path is not a directory: %s",
                base_path,
            )
            return results

    except Exception:
        logger.exception(
            "Failed to access TV path: %s",
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
            # Determine parent and series directories.
            # ------------------------------------------------------

            parent_directory = get_parent_directory_name(
                entry.path,
            )

            series_directory = get_series_directory_name(
                entry.path,
            )

            if parent_directory is None:
                logger.warning(
                    "Could not determine parent directory for: %s",
                    entry.path,
                )
                continue

            if series_directory is None:
                logger.warning(
                    "Could not determine TV series for: %s",
                    entry.path,
                )
                continue

            # ------------------------------------------------------
            # Determine season from directory.
            # ------------------------------------------------------

            parent_season = extract_season_from_directory(
                parent_directory,
            )

            # ------------------------------------------------------
            # Clean series name.
            # ------------------------------------------------------

            series, series_year = clean_series_name(
                series_directory,
            )

            if not series:
                logger.warning(
                    "Could not determine TV series for: %s",
                    entry.path,
                )
                continue

            # ------------------------------------------------------
            # Extract season and episode from filename.
            # ------------------------------------------------------

            (
                filename_season,
                episode,
                remaining,
            ) = extract_episode_info(
                entry.name,
            )

            # Filename season takes priority.
            season = filename_season

            if season is None:
                season = parent_season

            # ------------------------------------------------------
            # Extract episode title.
            # ------------------------------------------------------

            episode_title = clean_episode_title(
                remaining,
                series,
            )

            if not episode_title:

                if episode is not None:
                    episode_title = (
                        f"Episode {episode}"
                    )

                else:
                    episode_title = re.sub(
                        r"\.[^.]+$",
                        "",
                        entry.name,
                    )

                    episode_title = clean_text(
                        episode_title,
                    )

            # ------------------------------------------------------
            # Determine year.
            # ------------------------------------------------------

            year = series_year

            if year is None:
                _, filename_year = extract_year(
                    entry.name,
                )

                year = filename_year

            # ------------------------------------------------------
            # Log incomplete episode information.
            #
            # We still catalogue the file. This is intentional:
            # one malformed filename should not prevent the rest
            # of a TV library from being indexed.
            # ------------------------------------------------------

            if season is None or episode is None:
                logger.warning(
                    "Could not completely determine "
                    "season/episode for: %s",
                    entry.path,
                )

            # ------------------------------------------------------
            # Catalog item.
            # ------------------------------------------------------

            results.append({
                "title": episode_title,
                "creator": "Unknown",
                "collection": series,
                "genre": "Unknown",
                "year": year,
                "path": entry.path,
                "metadata": {
                    "media_format": extension.lstrip("."),
                    "series": series,
                    "season": season,
                    "episode": episode,
                    "source_filename": entry.name,
                    "source_directory": series_directory,
                },
            })

    except Exception:
        logger.exception(
            "TV scan failed for: %s",
            base_path,
        )

    logger.info(
        "TV scan completed: %d items found in %s",
        len(results),
        base_path,
    )

    return results
