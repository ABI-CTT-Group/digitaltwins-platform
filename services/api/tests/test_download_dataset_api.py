"""GET /datasets/{uuid}/download: zips what the Downloader fetched; storage errors map to HTTP codes."""
import io
import os
import sys
import zipfile
from pathlib import Path

# Ensure the project root is on sys.path so `app` can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.auth import validate_credentials
from app.routers.dependencies import get_downloader

DATASET_UUID = "11111111-2222-3333-4444-555555555555"

client = TestClient(app)


class FakeDownloader:
    """Writes files the way the core Downloader does (<save_dir>/<uuid>/...), or raises `error`."""

    def __init__(self, files=None, error=None):
        self.files = files or {}
        self.error = error
        self.save_dir = None

    def download_dataset(self, dataset_uuid, save_dir="./tmp"):
        self.save_dir = save_dir
        if self.error:
            raise self.error
        for rel, content in self.files.items():
            path = os.path.join(save_dir, dataset_uuid, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(content)


@pytest.fixture(autouse=True)
def _bypass_auth(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, validate_credentials, lambda: {"username": "testuser"})


def _use(monkeypatch, downloader):
    monkeypatch.setitem(app.dependency_overrides, get_downloader, lambda: downloader)
    return downloader


def test_download_returns_zip_of_dataset_files(monkeypatch):
    downloader = _use(monkeypatch, FakeDownloader(files={
        "dataset_description.xlsx": b"desc",
        "primary/sub-1/sam-1/image.dcm": b"pixels",
    }))

    response = client.get(f"/datasets/{DATASET_UUID}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert f'filename="{DATASET_UUID}.zip"' in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        # Paths are relative to the dataset root, not the temp dir
        assert sorted(zf.namelist()) == ["dataset_description.xlsx", "primary/sub-1/sam-1/image.dcm"]
        assert zf.read("primary/sub-1/sam-1/image.dcm") == b"pixels"
    # The temp dir is removed once the stream has been consumed
    assert not os.path.exists(os.path.dirname(downloader.save_dir))


@pytest.mark.parametrize("error, status_code, detail", [
    (FileNotFoundError("no objects for dataset"), 404, "no objects for dataset"),
    (ConnectionError("minio down"), 503, "Storage backend unavailable: minio down"),
    # The MinIO downloader raises RuntimeError when a transfer fails
    (RuntimeError("transfer failed"), 500, "Failed to download dataset: transfer failed"),
    (EnvironmentError("Missing Downloader"), 500, "Failed to download dataset: Missing Downloader"),
    (ValueError("boom"), 500, "Unexpected error while downloading dataset."),
])
def test_download_maps_storage_errors(monkeypatch, error, status_code, detail):
    downloader = _use(monkeypatch, FakeDownloader(error=error))

    response = client.get(f"/datasets/{DATASET_UUID}/download")

    assert response.status_code == status_code
    assert response.json()["detail"] == detail
    assert not os.path.exists(os.path.dirname(downloader.save_dir))
