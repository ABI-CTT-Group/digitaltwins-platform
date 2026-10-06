"""``digitaltwins.minio.downloader.Downloader`` object helpers against a live MinIO (skipped when unreachable).

Datasets are stored one bucket per category under ``<dataset_uuid>/…``; a gui assay launch needs to find
that bucket, list a sample's objects and stream one of them.
"""
import pytest

from digitaltwins.minio.downloader import Downloader


@pytest.fixture
def dataset(minio_bucket, s3):
    s3.create_bucket(Bucket=minio_bucket)
    for key, body in {
        "ds-x/primary/sub-1/sam-1/a.dcm": b"aaa",
        "ds-x/primary/sub-1/sam-1/b.dcm": b"bb",
        "ds-x/primary/sub-2/sam-2/c.dcm": b"c",
    }.items():
        s3.put_object(Bucket=minio_bucket, Key=key, Body=body)
    return minio_bucket


def test_find_bucket_returns_the_bucket_holding_the_dataset(dataset):
    assert Downloader().find_bucket("ds-x") == dataset
    assert Downloader().find_bucket("no-such-dataset") is None


def test_list_objects_returns_the_keys_under_a_prefix(dataset):
    assert Downloader().list_objects(dataset, "ds-x/primary/sub-1/sam-1/") == [
        "ds-x/primary/sub-1/sam-1/a.dcm",
        "ds-x/primary/sub-1/sam-1/b.dcm",
    ]
    assert Downloader().list_objects(dataset, "ds-x/primary/sub-9/") == []


def test_open_object_streams_the_body_with_its_length(dataset):
    chunks, length = Downloader().open_object(dataset, "ds-x/primary/sub-1/sam-1/a.dcm")
    assert (b"".join(chunks), length) == (b"aaa", 3)


def test_open_object_raises_file_not_found_for_a_missing_key(dataset):
    with pytest.raises(FileNotFoundError):
        Downloader().open_object(dataset, "ds-x/primary/sub-1/sam-1/missing.dcm")
