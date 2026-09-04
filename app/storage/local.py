# app/storage/local.py

from pathlib import Path
from typing import BinaryIO, Iterator, cast

from app.storage.base import (
    StorageEntry,
    StorageProvider,
)


class LocalStorageProvider(StorageProvider):
    """
    Storage provider for the local filesystem.

    Local paths are handled using pathlib. The provider exposes the
    same interface used by the SMB implementation so scanners remain
    storage-provider agnostic.
    """

    def exists(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether a local path exists.
        """

        return Path(path).exists()

    def is_dir(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether a local path is a directory.
        """

        return Path(path).is_dir()

    def scandir(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Enumerate the immediate contents of a local directory.
        """

        directory = Path(path)

        for entry in directory.iterdir():
            yield StorageEntry(
                name=entry.name,
                path=str(entry),
                is_file=entry.is_file(),
                is_dir=entry.is_dir(),
            )

    def walk(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Recursively enumerate all files and directories below
        a local directory.

        The root directory itself is not yielded.
        """

        directory = Path(path)

        for entry in directory.rglob("*"):
            yield StorageEntry(
                name=entry.name,
                path=str(entry),
                is_file=entry.is_file(),
                is_dir=entry.is_dir(),
            )

    def open(
        self,
        path: str,
        mode: str = "rb",
    ) -> BinaryIO:
        """
        Open a local file.

        The return value is cast to BinaryIO so the storage interface
        remains compatible with scanners using binary file handles.
        """

        return cast(
            BinaryIO,
            open(
                path,
                mode,
            ),
        )

    def stat(
        self,
        path: str,
    ):
        """
        Return local filesystem metadata.
        """

        return Path(path).stat()
