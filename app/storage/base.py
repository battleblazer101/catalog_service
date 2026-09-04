# app/storage/base.py

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Iterator


class StorageEntry:
    """
    Represents a file or directory discovered through a storage provider.

    Scanners operate on StorageEntry objects and therefore do not need
    to know whether the underlying storage is local, SMB, or another
    supported backend.
    """

    def __init__(
        self,
        name: str,
        path: str,
        is_file: bool,
        is_dir: bool,
    ) -> None:
        self.name = name
        self.path = path
        self.is_file = is_file
        self.is_dir = is_dir

    @property
    def suffix(self) -> str:
        """
        Return the lowercase file extension including the leading dot.

        Examples:

            movie.mkv -> ".mkv"
            song.MP3  -> ".mp3"
            book.epub -> ".epub"

        Directory entries normally return an empty string.
        """

        return Path(self.name).suffix.lower()

    @property
    def parent_name(self) -> str:
        """
        Return the immediate parent directory name.

        This deliberately handles local, UNC and SMB-style paths
        without relying on the local operating system's path rules.

        Examples:

            /media/music/Artist/song.mp3
                -> Artist

            smb://server/share/Music/Artist/song.mp3
                -> Artist

            \\\\server\\share\\Music\\Artist\\song.mp3
                -> Artist
        """

        value = self.path.strip().rstrip("\\/")

        if not value:
            return ""

        parts = [
            part
            for part in re.split(
                r"[\\/]+",
                value,
            )
            if part
        ]

        if len(parts) < 2:
            return ""

        return parts[-2]

    def __repr__(self) -> str:
        return (
            "StorageEntry("
            f"name={self.name!r}, "
            f"path={self.path!r}, "
            f"is_file={self.is_file!r}, "
            f"is_dir={self.is_dir!r}"
            ")"
        )


class StorageProvider(ABC):
    """
    Abstract interface for media storage.

    Scanners depend only on this interface.

    Implementations may provide access to:

        - Local filesystem
        - SMB/CIFS shares
        - Future storage backends

    The interface intentionally exposes only the operations required
    by catalog scanning and media ingestion.
    """

    @abstractmethod
    def exists(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether a path exists.
        """

        raise NotImplementedError

    @abstractmethod
    def is_dir(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether a path is a directory.
        """

        raise NotImplementedError

    @abstractmethod
    def scandir(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Enumerate the immediate contents of a directory.

        Implementations should yield StorageEntry objects for both
        files and directories.
        """

        raise NotImplementedError

    @abstractmethod
    def walk(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Recursively enumerate files and directories below a path.

        The supplied root directory itself does not need to be yielded.
        """

        raise NotImplementedError

    @abstractmethod
    def open(
        self,
        path: str,
        mode: str = "rb",
    ) -> BinaryIO:
        """
        Open a file and return a file-like object.

        Scanner consumers currently require binary read access.
        Implementations may restrict unsupported modes.
        """

        raise NotImplementedError

    @abstractmethod
    def stat(
        self,
        path: str,
    ):
        """
        Return storage-provider-specific file metadata.

        The exact return type intentionally remains provider-specific.
        """

        raise NotImplementedError
