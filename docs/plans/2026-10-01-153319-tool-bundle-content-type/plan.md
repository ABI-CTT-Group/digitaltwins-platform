# Approved GUI Tool Content-Type Fix: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Approved GUI tools load the same UI as their unapproved test build, because digitaltwins-api stores MinIO objects with the right `Content-Type`.

**Architecture:** Approval hands the built tool to digitaltwins-api. The API copies it into the MinIO `tools` bucket under the new dataset UUID, and the portal launcher then loads `/tools/<uuid>/primary/my-app.umd.js`. The API's `Uploader.upload_file` does not pass a `ContentType`, so MinIO stores every object as `binary/octet-stream`. MinIO also sends `X-Content-Type-Options: nosniff`, so the browser refuses to run the plugin script and its web workers. The fix sets `ContentType` from the file extension at upload time, the way the portal's own uploader already does (`services/portal/backend/app/client/minio.py:132-142`). The objects already in the `tools` bucket are then repaired in place.

**Tech Stack:** Python 3.11 (API container), boto3 against MinIO, pytest.

**Spec:** No separate spec. The root-cause evidence is in [Background](#background) below.

## Background

These are measurements from the local stack on 2026-10-01 for `tool_volview`. It was approved as dataset `0c57cce8-bd3b-11f1-8870-2a34b780cc74` from build `toolvolview_1ed5eb95`.

| | `tool-builds/toolvolview_1ed5eb95/primary/…` (portal upload) | `tools/0c57cce8-…/primary/…` (API upload) |
|---|---|---|
| `my-app.umd.js` md5 | `4703b655…` | `4703b655…` (identical) |
| `my-app.umd.js` Content-Type | `text/javascript` | `binary/octet-stream` |
| `assets/*.worker-*.js`, `itk/*.js` | `text/javascript` | `binary/octet-stream` |
| `favicon.ico` | `image/vnd.microsoft.icon` | `binary/octet-stream` |
| `X-Content-Type-Options` | `nosniff` | `nosniff` |

`tool_volview-2` was never approved, so it still loads from `tool-builds` and works.

Both tools show `/tool-view` in the address bar because that is a single generic route. The tool's bundle path is passed through the Pinia `remoteApp` store, not the URL. This plan does not change that.

**Alternatives considered:** The other option was to override `Content-Type` when serving, in the portal-frontend nginx `location /tools/` block. That was rejected for three reasons:
- It only fixes one URL prefix.
- It leaves the stored objects wrong for every other consumer.
- It hides an inconsistency between the two uploaders instead of removing it.

No ADR is needed. This is a bug fix that makes the API uploader match the existing portal uploader.

## Global Constraints

- Do not modify the portal backend or frontend. The portal already sets content types correctly.
- No secrets in commands or docs. MinIO keys are written as `<REDACTED>` (AGENTS.md).
- Unknown or missing extensions fall back to `application/octet-stream`, the same as the portal (`minio.py:141`).
- API image is baked (source is not mounted): code changes only take effect after `docker compose build digitaltwins-api && docker compose up -d digitaltwins-api`.
- Known pre-existing API test failures, which are allowed: `test_delete_existing_dataset`, `test_upload_workspace_datasets_jupyter`, `test_upload_zip`.

## Review Focus

1. **Files with no extension or an unknown extension** (`CHANGES`, `tool_volview.cwl`, `*.wasm.zst`, and `*.xlsx` in the API container, which has no `/etc/mime.types`). The upload must still succeed and store `application/octet-stream`. This is pinned in Task 1, Step 1 (`CHANGES`, `x.unknownext`) and Task 1, Step 5 (`.wasm.zst`).
2. **The host and the container guess different JS types.** The container returns `application/javascript`. A host whose `/etc/mime.types` is newer may return `text/javascript`. Browsers accept both. The tests accept either value (`JS_TYPES`) so they pass in both places.
3. **Other dataset categories use the same uploader** (measurements, models, workflows). They now get real content types instead of `binary/octet-stream`. The `Downloader` ignores `ContentType`, so downloads are unaffected. This is checked by the full API suite run in Task 1, Step 6.
4. **Running the repair twice, or on objects that are already correct.** The repair must skip objects whose type already matches and must change nothing in dry-run mode. This is pinned in Task 2, Steps 2-3 (dry run first, then apply, then re-run expecting 0 changes).
5. **Cached failed responses in the browser.** Worker URLs are not cache-busted. Only `my-app.umd.js` gets `?v=<ts>`. A browser that already got the `binary/octet-stream` response may reuse it. Verification in Task 2, Step 5 uses DevTools with "Disable cache" turned on.

---

### Task 1: API uploader stores objects with a Content-Type

**Files:**
- Modify: `services/api/src/digitaltwins/minio/uploader.py` (imports, and `upload_file` around line 96)
- Create: `services/api/tests/test_minio_content_type.py`

**Interfaces:**
- Consumes: the existing `minio_bucket` and `s3` fixtures in `services/api/tests/conftest.py:95-138`.
- Produces: `Uploader.upload_file` and `Uploader.upload_folder` keep their signatures and return values. Every object they write now has `ContentType` set to `mimetypes.guess_type(file_path)[0] or "application/octet-stream"`.

- [ ] **Step 1: Write the failing unit test (no MinIO needed)**

Create `services/api/tests/test_minio_content_type.py`:

```python
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
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd services/api && pytest tests/test_minio_content_type.py -k upload_file_sets -v`
Expected: all 6 FAIL with `AssertionError: upload_file passed no ExtraArgs`.

- [ ] **Step 3: Write the minimal implementation**

In `services/api/src/digitaltwins/minio/uploader.py`, add the import next to `import os`:

```python
import mimetypes
import os
```

Then replace the upload call in `upload_file` (currently `self.s3_client.upload_file(file_path, bucket_name, object_name)`):

```python
        try:
            # MinIO serves with nosniff: without a real type, browsers refuse JS/CSS/workers.
            content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            self.s3_client.upload_file(file_path, bucket_name, object_name,
                                       ExtraArgs={"ContentType": content_type})
```

- [ ] **Step 4: Run it and confirm it passes**

Run: `cd services/api && pytest tests/test_minio_content_type.py -k upload_file_sets -v`
Expected: 6 passed.

- [ ] **Step 5: Add the real-MinIO integration test**

This test proves that MinIO stores and returns the type, which the fake cannot show. Append to `services/api/tests/test_minio_content_type.py`:

```python
@pytest.mark.integration
def test_upload_folder_content_type_round_trips_through_minio(minio_bucket, s3, tmp_path):
    bundle = tmp_path / "bundle"
    files = {
        "primary/my-app.umd.js": JS_TYPES,
        "primary/assets/histogram.worker-Dk1Y0_vM.js": JS_TYPES,
        "primary/itk/image-io/gdcm-read-image.wasm.zst": {"application/octet-stream", "application/zstd"},
        "primary/tool_volview.cwl": {"application/octet-stream", "application/cwl"},  # host /etc/mime.types knows .cwl
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
```

Run it with the stack up (MinIO is published on host port 8011):

```bash
cd services/api && MINIO_ENDPOINT=http://localhost:8011 \
  MINIO_SERVER_ACCESS_KEY=<REDACTED> MINIO_SERVER_SECRET_KEY=<REDACTED> \
  pytest tests/test_minio_content_type.py -v
```

Expected: 7 passed. It must not be skipped. If it is reported as skipped, MinIO was unreachable, so fix the env and re-run.

To confirm this test actually catches the bug, temporarily revert Step 3 with `git stash -- src/digitaltwins/minio/uploader.py`. Re-run, and the test should FAIL on `primary/my-app.umd.js` with `'binary/octet-stream' in {...}`. Then `git stash pop`.

- [ ] **Step 6: Run the full API suite**

Run: `pytest services/api/tests` with the stack up, using the same env as Step 5.
Expected: the only failures are the three pre-existing ones listed under Global Constraints.

- [ ] **Step 7: Commit**

```bash
git add services/api/src/digitaltwins/minio/uploader.py services/api/tests/test_minio_content_type.py \
        docs/artifacts/2026-10-01-153319-tool-bundle-content-type/
git commit -m "fix(api): store MinIO objects with a Content-Type so approved GUI tools load"
```

---

### Task 2: Redeploy and repair existing `tools` objects (operational, no code commit)

The fix only affects new uploads. `tool_volview` is already in the `tools` bucket with the wrong types, and so is any other tool approved before the fix.

**Files:** none committed, apart from `walkthrough.md` in this artifact folder.

**Interfaces:**
- Consumes: the Task 1 change, deployed in the `digitaltwins-api` container.

- [ ] **Step 1: Rebuild and restart the API**

```bash
docker compose build digitaltwins-api && docker compose up -d digitaltwins-api
```

- [ ] **Step 2: Dry-run the repair (prints only, changes nothing)**

```bash
docker exec -i digitaltwins-platform-digitaltwins-api-1 python - <<'EOF'
import mimetypes
from digitaltwins.minio.uploader import Uploader
APPLY = False
s3, bucket, changed = Uploader().s3_client, "tools", 0
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        want = mimetypes.guess_type(key)[0] or "application/octet-stream"
        have = s3.head_object(Bucket=bucket, Key=key)["ContentType"]
        if have == want:
            continue
        changed += 1
        print(f"{key}: {have} -> {want}")
        if APPLY:
            s3.copy_object(Bucket=bucket, Key=key, CopySource={"Bucket": bucket, "Key": key},
                           ContentType=want, MetadataDirective="REPLACE")
print(f"{'changed' if APPLY else 'would change'}: {changed}")
EOF
```

Expected: the lines include `0c57cce8-bd3b-11f1-8870-2a34b780cc74/primary/my-app.umd.js: binary/octet-stream -> application/javascript`. Files with no known type (for example `.xlsx`, `.md`, `.wasm.zst` and `CHANGES` in this container) also appear, as `binary/octet-stream -> application/octet-stream`. Browsers treat those two values the same, so rewriting them is harmless and makes the bucket consistent with new uploads.

`MetadataDirective="REPLACE"` drops any user metadata on the object. The API never sets user metadata (it passed no `ExtraArgs` before this fix), so nothing is lost.

- [ ] **Step 3: Apply, then confirm the repair is idempotent**

Re-run Step 2 with `APPLY = True`. Expected: `changed: N`, where N matches the dry run.
Re-run it again with `APPLY = True`. Expected: `changed: 0`.

- [ ] **Step 4: Verify headers**

```bash
curl -sI http://localhost/tools/0c57cce8-bd3b-11f1-8870-2a34b780cc74/primary/my-app.umd.js | grep -i content-type
curl -sI http://localhost/tools/0c57cce8-bd3b-11f1-8870-2a34b780cc74/primary/assets/histogram.worker-Dk1Y0_vM.js | grep -i content-type
```

Expected: `Content-Type: application/javascript` for both.

- [ ] **Step 5: Verify in the browser**

Open `http://localhost/upload-tool-dataset` and open DevTools with **Network → Disable cache** turned on. Launch `tool_volview`.
Expected:
- The VolView UI renders, the same as `tool_volview-2`.
- The console has no `Refused to execute script … MIME type` errors.
- Loading a sample image works, which proves the web workers run.

- [ ] **Step 6 (optional, only with user consent): End-to-end approval of a new tool**

Approving `tool_volview-2` exercises the fixed upload path end to end. It also creates SEEK and FHIR records and a new `tools` dataset, so do it only if the user agrees. After approval, launch it. It should render correctly without any repair step.

- [ ] **Step 7: Write `walkthrough.md` and sync artifacts**

Record what was run, the repair counts and the verification results in `docs/artifacts/2026-10-01-153319-tool-bundle-content-type/walkthrough.md`. Check that it contains no secrets (`gitleaks detect --source docs/artifacts/2026-10-01-153319-tool-bundle-content-type --no-git`). Commit it on the same branch as Task 1:

```bash
git add docs/artifacts/2026-10-01-153319-tool-bundle-content-type/
git commit -m "docs(artifacts): walkthrough for approved GUI tool content-type fix"
```

---

## Open questions for review

1. **Other deployments:** If any other environment (staging or production) has tools approved before this fix, it needs the Task 2 repair too. Should the repair snippet become a committed script under `services/api/scripts/`, or is keeping it in this plan enough of a record?
2. **Task 2, Step 6:** Do you want the end-to-end re-approval of `tool_volview-2`, given its side effects in SEEK and FHIR?
