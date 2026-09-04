# app/storage/smb.py

from pathlib import PureWindowsPath
from typing import BinaryIO, Iterator, cast

import smbclient

from app.storage.base import (
    StorageEntry,
    StorageProvider,
)


class SMBStorageProvider(StorageProvider):
    """
    Storage provider for SMB/CIFS network shares.

    SMB paths are represented internally using UNC-style paths:

        \\\\server\\share\\directory

    Supported input formats include:

        smb://server/share
        smb://server/share/folder
        \\\\server\\share
        \\\\server\\share\\folder

    Authentication is supplied separately and is never embedded
    into the filesystem path.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        domain: str | None = None,
        port: int = 445,
    ) -> None:
        self.username = username
        self.password = password
        self.domain = domain
        self.port = port

    # ------------------------------------------------------------------
    # Path handling
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_path(
        path: str,
    ) -> str:
        """
        Convert an SMB path into the UNC format expected by smbclient.

        Examples:

            smb://server/share
                -> \\\\server\\share

            smb://server/share/folder
                -> \\\\server\\share\\folder

            \\\\server\\share
                -> \\\\server\\share
        """

        value = path.strip()

        if not value:
            raise ValueError(
                "SMB path cannot be empty"
            )

        # --------------------------------------------------------------
        # SMB URL
        # --------------------------------------------------------------

        if value.lower().startswith("smb://"):
            value = value[6:]

            # SMB URLs use forward slashes.
            value = value.replace(
                "/",
                "\\",
            )

            value = "\\\\" + value

        # --------------------------------------------------------------
        # Protocol-relative SMB path.
        #
        # //server/share is accepted as an SMB path as well.
        # --------------------------------------------------------------

        elif value.startswith("//"):
            value = value.replace(
                "/",
                "\\",
            )

            if not value.startswith("\\\\"):
                value = "\\" + value

        # --------------------------------------------------------------
        # Already UNC-style.
        # --------------------------------------------------------------

        elif value.startswith("\\\\"):
            value = value

        else:
            raise ValueError(
                f"Invalid SMB path: {path}"
            )

        # Avoid accidentally returning a path with trailing separators
        # except for the root share itself. smbclient handles both, but
        # keeping paths normalized makes catalog paths deterministic.
        if len(value) > 2:
            value = value.rstrip("\\")

        return value

    @staticmethod
    def server_from_path(
        path: str,
    ) -> str:
        """
        Extract the SMB server name from an SMB/UNC path.
        """

        normalized = SMBStorageProvider.normalize_path(
            path,
        )

        # Validate that the path represents a real UNC structure.
        parts = PureWindowsPath(normalized).parts

        if len(parts) < 1:
            raise ValueError(
                f"Invalid SMB path: {path}"
            )

        stripped = normalized.lstrip("\\")

        if not stripped:
            raise ValueError(
                f"Could not determine SMB server from path: {path}"
            )

        server = stripped.split(
            "\\",
            1,
        )[0]

        if not server:
            raise ValueError(
                f"Could not determine SMB server from path: {path}"
            )

        return server

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _register_session(
        self,
        path: str,
    ) -> None:
        """
        Register an SMB session for the server.

        Authentication is intentionally kept separate from the path.

        If no credentials were supplied, smbclient's normal/default
        authentication mechanisms are used.
        """

        server = self.server_from_path(
            path,
        )

        kwargs: dict[str, object] = {
            "port": self.port,
        }

        if self.username is not None:
            kwargs["username"] = self.username

        if self.password is not None:
            kwargs["password"] = self.password

        if self.domain is not None:
            kwargs["domain"] = self.domain

        smbclient.register_session(
            server,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Filesystem operations
    # ------------------------------------------------------------------

    def exists(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether an SMB path exists.
        """

        smb_path = self.normalize_path(
            path,
        )

        self._register_session(
            smb_path,
        )

        return smbclient.path.exists(
            smb_path,
        )

    def is_dir(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether an SMB path is a directory.
        """

        smb_path = self.normalize_path(
            path,
        )

        self._register_session(
            smb_path,
        )

        return smbclient.path.isdir(
            smb_path,
        )

    def scandir(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Enumerate the immediate contents of an SMB directory.
        """

        smb_path = self.normalize_path(
            path,
        )

        self._register_session(
            smb_path,
        )

        for entry in smbclient.scandir(
            smb_path,
        ):
            entry_path = self._join(
                smb_path,
                entry.name,
            )

            yield StorageEntry(
                name=entry.name,
                path=entry_path,
                is_file=entry.is_file(),
                is_dir=entry.is_dir(),
            )

    def walk(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Recursively enumerate all files and directories below
        an SMB directory.

        The root directory itself is not yielded.
        """

        smb_path = self.normalize_path(
            path,
        )

        self._register_session(
            smb_path,
        )

        yield from self._walk_directory(
            smb_path,
        )

    def _walk_directory(
        self,
        path: str,
    ) -> Iterator[StorageEntry]:
        """
        Recursively walk an SMB directory.
        """

        for entry in smbclient.scandir(
            path,
        ):
            entry_path = self._join(
                path,
                entry.name,
            )

            storage_entry = StorageEntry(
                name=entry.name,
                path=entry_path,
                is_file=entry.is_file(),
                is_dir=entry.is_dir(),
            )

            yield storage_entry

            if entry.is_dir():
                yield from self._walk_directory(
                    entry_path,
                )

    def open(
        self,
        path: str,
        mode: str = "rb",
    ) -> BinaryIO:
        """
        Open a file on an SMB share.

        The scanner currently requires read-only binary access.
        """

        if mode != "rb":
            raise ValueError(
                "SMBStorageProvider only supports binary read mode"
            )

        smb_path = self.normalize_path(
            path,
        )

        self._register_session(
            smb_path,
        )

        file_handle = smbclient.open_file(
            smb_path,
            mode="rb",
        )

        return cast(
            BinaryIO,
            file_handle,
        )

    def stat(
        self,
        path: str,
    ):
        """
        Return SMB file metadata.
        """

        smb_path = self.normalize_path(
            path,
        )

        self._register_session(
            smb_path,
        )

        return smbclient.stat(
            smb_path,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _join(
        parent: str,
        child: str,
    ) -> str:
        """
        Join two SMB path components using UNC separators.
        """

        return (
            parent.rstrip("\\")
            + "\\"
            + child
        )
