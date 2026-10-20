"""Shared FastAPI dependency factories used across multiple routers."""

from fastapi import Depends

from digitaltwins import Querier, Uploader, Downloader, Deleter
from .auth import validate_credentials


def get_querier(credentials: dict = Depends(validate_credentials)) -> Querier:
    """Create a per-request Querier using the authenticated user's Keycloak token."""
    return Querier(api_token=credentials["token"])


def get_uploader() -> Uploader:
    """Build an Uploader() instance for dependency injection."""
    return Uploader()


def get_downloader() -> Downloader:
    """Build a Downloader() instance for dependency injection."""
    return Downloader()


def get_deleter(credentials: dict = Depends(validate_credentials)) -> Deleter:
    """Create a per-request Deleter that removes a tool's SEEK Workflow as the calling user."""
    return Deleter(api_token=credentials["token"])


def get_minio_downloader():
    """The MinIO object store itself (buckets, keys, streams), as opposed to the core dataset Downloader."""
    from digitaltwins.minio.downloader import Downloader as MinioDownloader

    return MinioDownloader()


def get_jupyterhub():
    """JupyterHub as the api service: starts users' servers and writes into their workspaces."""
    from digitaltwins.jupyterhub.hub import JupyterHub

    return JupyterHub()
