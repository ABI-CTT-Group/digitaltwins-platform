# `tool_download_samples.py` — two fixes

Found while bringing up the remote Airflow compute node. `workflow_38`'s
`download_samples` took **~17 minutes** for what should have been ~2 samples.

**Evidence (from `airflow-workspace/workflow_1/run_1/inputs/` in MinIO):**

```
sam-1   316 slices   88.8 MB
sam-2   160 slices   64.6 MB   ┐
sam-3   160 slices   64.6 MB   │ same series (all start 1-001.dcm, 160 files each)
sam-4   160 slices   64.6 MB   │ staged four times
sam-5   160 slices   64.6 MB   ┘
TOTAL   956 files    347 MB
```

A single object transfers in **11 ms** (measured), so the network/MinIO are fine —
347 MB should move in ~7 s. The 17 minutes is entirely per-file overhead in the
tool. Two independent problems:

---

## Bug 1 — `sample_type` is never applied (correctness → over-fetch)

`run()` builds the source prefix without `sample_type` and downloads the whole
subject:

```python
source_prefix = f"{dataset_uuid}/primary/{subject_id}/"      # sample_type not used
log.info("... (sample_type=%s)", source_bucket, source_prefix, sample_type)  # only logged
count = _download_prefix(s3, source_bucket, source_prefix, download_dir)      # grabs everything
```

So a run that intends ~2 samples stages **all 5** the subject has under it. This is
why "2 vs 5". `sample_type` needs to actually filter.

**Recommended fix (needs your domain knowledge — I did NOT guess the mapping):**
`discover_subjects` already calls `/datasets/{uuid}/samples?sample_type=...` and
gets back the matching samples. The clean fix is to **pass those matching sample
identifiers/paths down into `download_samples`** and copy only those, rather than
having this tool re-list the whole subject and re-derive the type→storage mapping.
If instead the sample directory names encode the type, a key-level predicate works
too — insert it at the `# sample-type filter` point in the patch below. Either way,
**the predicate is yours to define**; the point is that today there is none.

---

## Bug 2 — serial MinIO→disk→MinIO relay (performance)

`_download_prefix` GETs every object to a temp dir one at a time, then
`_upload_directory` PUTs every file back one at a time — ~1,900 serial round-trips
for 956 files. And since **source and destination are the same MinIO server**, the
bytes never needed to touch the worker at all.

**Fix: parallel server-side `copy_object`.** No temp dir, no bytes over the VLAN,
concurrent. 347 MB of intra-MinIO copy becomes a couple of seconds.

### Patch (replaces `_download_prefix` + `_upload_directory` + the body of `run()`)

```python
from concurrent.futures import ThreadPoolExecutor

def _list_keys(s3, bucket: str, prefix: str) -> list[str]:
    """All object keys under *prefix* (excludes directory placeholders)."""
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                keys.append(obj["Key"])
    return keys


def _copy_keys(s3, src_bucket: str, src_prefix: str, keys: list[str],
               dst_bucket: str, dst_prefix: str, max_workers: int = 32) -> int:
    """Server-side copy each key src_bucket → dst_bucket, in parallel.

    boto3 low-level clients are thread-safe for API calls, so one shared client
    across the pool is fine. copy_object is a server-side op — no data flows
    through this process.
    """
    def _copy(key: str) -> None:
        relative = key[len(src_prefix):].lstrip("/")
        s3.copy_object(
            Bucket=dst_bucket,
            Key=f"{dst_prefix}/{relative}",
            CopySource={"Bucket": src_bucket, "Key": key},
        )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # list() forces evaluation so any copy exception propagates (fail-loud).
        list(pool.map(_copy, keys))
    return len(keys)


def run(*, bucket: str, dataset_uuid: str, subject_id: str, sample_type: str,
        dag_id: str, run_index: int) -> str:
    s3 = _get_s3_client()

    source_bucket = _find_source_bucket(s3, dataset_uuid)
    if not source_bucket:
        raise FileNotFoundError(f"No bucket found containing dataset '{dataset_uuid}'.")

    source_prefix = f"{dataset_uuid}/primary/{subject_id}/"
    target_prefix = f"{dag_id}/run_{run_index}/inputs"
    log.info("Copying samples from s3://%s/%s (sample_type=%s)",
             source_bucket, source_prefix, sample_type)

    keys = _list_keys(s3, source_bucket, source_prefix)

    # --- sample-type filter (Bug 1) --------------------------------------
    # TODO(dev): restrict `keys` to those matching `sample_type`. See note above —
    # ideally driven by the sample list discover_subjects already fetched, not a
    # re-derivation here. Without this, ALL of the subject's samples are staged.
    # if sample_type:
    #     keys = [k for k in keys if _matches_sample_type(k, sample_type)]

    if not keys:
        raise FileNotFoundError(
            f"No objects under s3://{source_bucket}/{source_prefix}"
            + (f" matching sample_type '{sample_type}'" if sample_type else "")
        )

    staged = _copy_keys(s3, source_bucket, source_prefix, keys, bucket, target_prefix)
    log.info("Staged %d file(s) to s3://%s/%s", staged, bucket, target_prefix)
    return f"{target_prefix}/"
```

`_download_prefix`, `_upload_directory`, and the `tempfile` import can be deleted
(the CLI `__main__` block is unchanged — it just calls `run()`).

### Expected result
- 347 MB / 956 files: **~17 min → a few seconds** (parallel, server-side).
- With Bug 1 fixed, the duplicate `sam-2..sam-5` stop being staged at all, cutting
  the file count too.

---

## Also worth a look (not tool bugs)

- **Source data has duplicates:** `sam-2..sam-5` are the same series four times in
  the *measurement dataset* itself — worth whoever populates it checking.
- **Run namespacing:** `target_prefix` is `{dag_id}/run_{run_index}/inputs` with
  `dag_id`/`run_index` currently constant per DAG, so concurrent runs would clobber
  each other's staged inputs. Consider keying on the Airflow `run_id`.
