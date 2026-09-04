# app/storage/factory.py

from app.storage.base import StorageProvider
from app.storage.local import LocalStorageProvider
from app.storage.smb import SMBStorageProvider


def get_storage_provider(
    path: str,
    username: str | None = None,
    password: str | None = None,
    domain: str | None = None,
) -> StorageProvider:
    """
    Return the appropriate storage provider for a path.

    Supported local paths:

        /media/music
        /var/lib/catalog_service

    Supported SMB paths:

        smb://server/share
        smb://server/share/music
        \\\\server\\share
        \\\\server\\share\\music

    SMB credentials are supplied separately and are never extracted
    from the path itself.
    """

    if not path or not path.strip():
        raise ValueError(
            "Storage path cannot be empty"
        )

    value = path.strip()

    # ------------------------------------------------------------------
    # SMB URL
    # ------------------------------------------------------------------

    if value.lower().startswith("smb://"):
        return SMBStorageProvider(
            username=username,
            password=password,
            domain=domain,
        )

    # ------------------------------------------------------------------
    # UNC SMB path
    # ------------------------------------------------------------------

    if value.startswith("\\\\"):
        return SMBStorageProvider(
            username=username,
            password=password,
            domain=domain,
        )

    # ------------------------------------------------------------------
    # Protocol-relative SMB path.
    #
    # //server/share is treated as SMB rather than a local path.
    # ------------------------------------------------------------------

    if value.startswith("//"):
        return SMBStorageProvider(
            username=username,
            password=password,
            domain=domain,
        )

    # ------------------------------------------------------------------
    # Local filesystem
    # ------------------------------------------------------------------

    return LocalStorageProvider()
