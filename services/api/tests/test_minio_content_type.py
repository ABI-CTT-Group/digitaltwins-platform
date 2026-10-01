"""The API's MinIO uploader must store a real Content-Type.

MinIO serves objects with X-Content-Type-Options: nosniff, so a JS file stored
as binary/octet-stream is refused by the browser. Approved GUI tools are loaded
straight from the API-written `tools` bucket, so this breaks them.
"""
import pytest

from digitaltwins.minio import uploader as uploader_module
from digitaltwins.minio.uploader import Uploader

JS_TYPES = {"application/javascript", "text/javascript"}


class FakeS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.uploads.append({"key": key, "extra_args": ExtraArgs})


@pytest.fixture
def fake_uploader(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio.invalid:9000")
    monkeypatch.setenv("MINIO_SERVER_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SERVER_SECRET_KEY", "test")
    fake = FakeS3()
    monkeypatch.setattr(uploader_module.boto3, "client", lambda *a, **kw: fake)
    return Uploader(), fake


@pytest.mark.parametrize("name, accepted", [
    ("my-app.umd.js", JS_TYPES),
    ("histogram.worker-Dk1Y0_vM.js", JS_TYPES),
    ("style.css", {"text/css"}),
    ("favicon.ico", {"image/vnd.microsoft.icon", "image/x-icon"}),
    ("CHANGES", {"application/octet-stream"}),
    ("x.unknownext", {"application/octet-stream"}),
])
def test_upload_file_sets_content_type(fake_uploader, tmp_path, name, accepted):
    uploader, fake = fake_uploader
    f = tmp_path / name
    f.write_bytes(b"x")

    assert uploader.upload_file(str(f), "tools", f"uuid/primary/{name}", overwrite=True)

    (upload,) = fake.uploads
    assert upload["extra_args"] is not None, "upload_file passed no ExtraArgs"
    assert upload["extra_args"]["ContentType"] in accepted


@pytest.mark.integration
def test_upload_folder_content_type_round_trips_through_minio(minio_bucket, s3, tmp_path):
    bundle = tmp_path / "bundle"
    files = {
        "primary/my-app.umd.js": JS_TYPES,
        "primary/assets/histogram.worker-Dk1Y0_vM.js": JS_TYPES,
        "primary/itk/image-io/gdcm-read-image.wasm.zst": {"application/octet-stream", "application/zstd"},
        "primary/tool_volview.cwl": {"application/octet-stream", "application/cwl"},
        "CHANGES": {"application/octet-stream"},
    }
    for rel in files:
        p = bundle / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    s3.create_bucket(Bucket=minio_bucket)

    assert Uploader().upload_folder(str(bundle), minio_bucket, prefix="some-uuid")

    for rel, accepted in files.items():
        head = s3.head_object(Bucket=minio_bucket, Key=f"some-uuid/{rel}")
        assert head["ContentType"] in accepted, rel
