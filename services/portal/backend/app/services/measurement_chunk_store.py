"""Chunk store for measurement chunked uploads (Approach A).

Backs the chunked-upload pipeline: a measurement row is pre-created
(``status=pending_upload``) and its source bytes stream in as parts that land
under ``tmp/upload_<measurement_id>/``. At finalize the parts are assembled and
handed to the existing SPARC validation + extraction path — validation logic
itself is untouched.

Layout under the per-upload root::

    tmp/upload_<measurement_id>/
      .meta.json                      # manifest + per-rel received part indices
      parts/<rel_path>/<000000..>     # one file per received part, zero-padded
      data/<rel_path>                 # assembled output (folder mode)
      source.zip                      # assembled output (zip mode)

The ``upload_`` prefix is intentional: ``main._cleanup_orphan_staging`` already
scans ``tmp/upload_*`` for stale dirs, so chunk-store leftovers are swept by the
same mechanism (extended in Task 1.4 to respect ``pending_upload`` rows).

Concurrency: part PUTs for one upload run in parallel (the frontend fans out a
handful at a time). Part *bytes* go to distinct files so they never contend;
only the read-modify-write of ``.meta.json`` is serialised, under a
per-measurement lock.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

from app.builder.logger import configure_logging, get_logger
from app.utils.utils import force_rmtree

configure_logging()
logger = get_logger(__name__)

# Intra-file chunk size the frontend splits on. Surfaced to the client in the
# /upload/init response so a single source of truth drives both sides. Default
# 8 MiB (Task 0.1 decision); operators can override via env without a rebuild.
PART_SIZE = int(os.getenv("MEASUREMENT_PART_SIZE_BYTES", str(8 * 1024 * 1024)))

# Folder-mode manifest file-count ceiling — guards against a pathological drop
# (e.g. a 500k-file directory) exhausting fds / bloating .meta.json.
MANIFEST_MAX_FILES = int(os.getenv("MEASUREMENT_MANIFEST_MAX_FILES", "100000"))

_META_NAME = ".meta.json"

# Per-measurement locks for serialising .meta.json updates. Guarded by a global
# lock so the dict itself is safe to grow under concurrent first-touch.
_locks_guard = threading.Lock()
_meta_locks: Dict[str, threading.Lock] = {}


def _lock_for(measurement_id: str) -> threading.Lock:
    with _locks_guard:
        lock = _meta_locks.get(measurement_id)
        if lock is None:
            lock = threading.Lock()
            _meta_locks[measurement_id] = lock
        return lock


def _safe_rel(rel_path: str) -> PurePosixPath:
    """Normalise a manifest rel_path and reject traversal / absolute paths.

    Manifest paths are POSIX-style (forward slashes) regardless of host OS.
    """
    p = PurePosixPath(rel_path)
    if p.is_absolute() or any(part in ("..", "") for part in p.parts) or not p.parts:
        raise ValueError(f"Unsafe rel_path: {rel_path!r}")
    return p


class ChunkStoreError(ValueError):
    """Raised for client-correctable chunk-store faults (bad part, size mismatch,
    unknown rel_path). The router maps these to 400."""


class MeasurementChunkStore:
    """Filesystem-backed chunk store rooted at ``tmp_root``.

    One instance per process is fine (it is stateless beyond ``tmp_root``); the
    router constructs it with the builder's ``tmp_dir``. The MinIO-multipart
    variant (v2) can implement this same surface without touching callers.
    """

    def __init__(self, tmp_root: Path):
        self.tmp_root = Path(tmp_root)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    # -- paths --------------------------------------------------------------
    def upload_dir(self, measurement_id: str) -> Path:
        return self.tmp_root / f"upload_{measurement_id}"

    def _meta_path(self, measurement_id: str) -> Path:
        return self.upload_dir(measurement_id) / _META_NAME

    def _parts_dir(self, measurement_id: str, rel: PurePosixPath) -> Path:
        return self.upload_dir(measurement_id) / "parts" / Path(*rel.parts)

    # -- meta read/write (caller holds the lock) ----------------------------
    def _read_meta(self, measurement_id: str) -> Dict[str, Any]:
        meta_path = self._meta_path(measurement_id)
        if not meta_path.exists():
            raise ChunkStoreError(f"No active upload for measurement {measurement_id}")
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_meta(self, measurement_id: str, meta: Dict[str, Any]) -> None:
        meta_path = self._meta_path(measurement_id)
        tmp = meta_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.replace(tmp, meta_path)  # atomic swap so a crash can't leave half-meta

    # -- public API ---------------------------------------------------------
    def init(
        self,
        measurement_id: str,
        source_kind: str,
        manifest: List[Dict[str, Any]],
        owner: Optional[str] = None,
    ) -> None:
        """Create the upload root + ``.meta.json`` for a new chunked upload.

        ``manifest`` is a list of ``{rel_path, size, parts}``. For zip mode it
        holds a single ``source.zip`` entry; for folder mode one entry per file.
        Raises ChunkStoreError on bad input (mirrors the 400 surface).
        """
        if source_kind not in ("folder", "zip"):
            raise ChunkStoreError(f"Unknown source_kind: {source_kind!r}")
        if not manifest:
            raise ChunkStoreError("Manifest is empty.")
        if len(manifest) > MANIFEST_MAX_FILES:
            raise ChunkStoreError(
                f"Manifest has {len(manifest)} files; exceeds the "
                f"{MANIFEST_MAX_FILES} limit."
            )

        norm: List[Dict[str, Any]] = []
        for entry in manifest:
            rel = _safe_rel(str(entry["rel_path"]))
            size = int(entry["size"])
            parts = int(entry["parts"])
            if size < 0 or parts < 1:
                raise ChunkStoreError(f"Bad manifest entry for {rel}: size={size} parts={parts}")
            norm.append({"rel_path": str(rel), "size": size, "parts": parts})

        updir = self.upload_dir(measurement_id)
        if updir.exists():
            raise ChunkStoreError(f"Upload dir already exists for measurement {measurement_id}")
        updir.mkdir(parents=True)

        meta = {
            "source_kind": source_kind,
            "owner": owner,
            "manifest": norm,
            "received": {e["rel_path"]: [] for e in norm},
        }
        with _lock_for(measurement_id):
            self._write_meta(measurement_id, meta)
        logger.info(
            f"Chunk upload init: measurement={measurement_id} kind={source_kind} "
            f"files={len(norm)}"
        )

    def source_kind(self, measurement_id: str) -> str:
        with _lock_for(measurement_id):
            return self._read_meta(measurement_id)["source_kind"]

    def owner(self, measurement_id: str) -> Optional[str]:
        with _lock_for(measurement_id):
            return self._read_meta(measurement_id).get("owner")

    def write_part(
        self,
        measurement_id: str,
        rel_path: str,
        part_no: int,
        of: int,
        data: bytes,
    ) -> int:
        """Persist one part and record it. Returns bytes received for this rel so far.

        Idempotent: re-writing an already-received part (concurrent / retried
        PUT) overwrites the bytes and leaves the received set unchanged. Parts
        may arrive out of order. The byte is written to a ``.tmp`` sibling and
        atomically renamed so a half-written part is never counted.
        """
        rel = _safe_rel(rel_path)
        with _lock_for(measurement_id):
            meta = self._read_meta(measurement_id)
            entry = next((e for e in meta["manifest"] if e["rel_path"] == str(rel)), None)
            if entry is None:
                raise ChunkStoreError(f"rel_path not in manifest: {rel}")
            if of != entry["parts"]:
                raise ChunkStoreError(
                    f"Part count mismatch for {rel}: client says {of}, manifest says {entry['parts']}"
                )
            if not (0 <= part_no < of):
                raise ChunkStoreError(f"part_no {part_no} out of range [0,{of}) for {rel}")

            parts_dir = self._parts_dir(measurement_id, rel)
            parts_dir.mkdir(parents=True, exist_ok=True)
            part_path = parts_dir / f"{part_no:06d}"
            tmp = part_path.with_name(part_path.name + ".tmp")
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, part_path)

            received: List[int] = meta["received"].setdefault(str(rel), [])
            if part_no not in received:
                received.append(part_no)
                received.sort()
            self._write_meta(measurement_id, meta)

            return sum(p.stat().st_size for p in parts_dir.iterdir() if p.is_file())

    def status(self, measurement_id: str) -> Dict[str, Any]:
        """Manifest + per-rel received parts/bytes + overall completeness.

        Drives resume: the client diffs its localStorage ``sentParts`` against
        ``received`` and re-sends only the gaps.
        """
        with _lock_for(measurement_id):
            meta = self._read_meta(measurement_id)
            files = []
            complete_all = True
            for e in meta["manifest"]:
                rel = e["rel_path"]
                got = sorted(meta["received"].get(rel, []))
                parts_dir = self._parts_dir(measurement_id, _safe_rel(rel))
                bytes_got = (
                    sum(p.stat().st_size for p in parts_dir.iterdir() if p.is_file())
                    if parts_dir.exists()
                    else 0
                )
                done = len(got) == e["parts"]
                complete_all = complete_all and done
                files.append(
                    {
                        "rel_path": rel,
                        "size": e["size"],
                        "parts": e["parts"],
                        "received_parts": got,
                        "bytes": bytes_got,
                        "complete": done,
                    }
                )
            return {
                "source_kind": meta["source_kind"],
                "files": files,
                "complete": complete_all,
            }

    def is_complete(self, measurement_id: str) -> bool:
        with _lock_for(measurement_id):
            meta = self._read_meta(measurement_id)
            for e in meta["manifest"]:
                if len(meta["received"].get(e["rel_path"], [])) != e["parts"]:
                    return False
            return True

    def assemble(self, measurement_id: str) -> Path:
        """Concatenate every rel's parts in order, verifying declared sizes.

        Returns the assembled artefact:
          - folder mode → the ``data/`` dir (a SPARC staging tree)
          - zip mode    → the ``source.zip`` file

        Raises ChunkStoreError if any rel is incomplete or its assembled size
        does not match the manifest (corrupt / dropped part).
        """
        with _lock_for(measurement_id):
            meta = self._read_meta(measurement_id)
            kind = meta["source_kind"]
            updir = self.upload_dir(measurement_id)

            if kind == "zip":
                entry = meta["manifest"][0]
                out_path = updir / "source.zip"
                self._concat_rel(measurement_id, entry, out_path)
                return out_path

            data_dir = updir / "data"
            for entry in meta["manifest"]:
                rel = _safe_rel(entry["rel_path"])
                out_path = data_dir / Path(*rel.parts)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                self._concat_rel(measurement_id, entry, out_path)
            return data_dir

    def _concat_rel(self, measurement_id: str, entry: Dict[str, Any], out_path: Path) -> None:
        rel = _safe_rel(entry["rel_path"])
        parts_dir = self._parts_dir(measurement_id, rel)
        written = 0
        with open(out_path, "wb") as out:
            for n in range(entry["parts"]):
                part_path = parts_dir / f"{n:06d}"
                if not part_path.exists():
                    raise ChunkStoreError(f"Missing part {n} for {rel}; upload incomplete.")
                with open(part_path, "rb") as p:
                    while True:
                        buf = p.read(1024 * 1024)
                        if not buf:
                            break
                        out.write(buf)
                        written += len(buf)
        if written != entry["size"]:
            raise ChunkStoreError(
                f"Assembled size mismatch for {rel}: got {written}, expected {entry['size']}."
            )

    def cleanup(self, measurement_id: str) -> None:
        updir = self.upload_dir(measurement_id)
        if updir.exists():
            force_rmtree(updir)
        with _locks_guard:
            _meta_locks.pop(measurement_id, None)
