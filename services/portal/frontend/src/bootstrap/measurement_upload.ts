/**
 * Chunked-upload orchestrator for measurement datasets.
 *
 * Drives the Approach-A pipeline from the browser: init (pre-create row) ->
 * fan out part PUTs with bounded concurrency -> finalize. Supports pause/resume
 * and cancel, and persists a small index to localStorage so an unfinished
 * upload is discoverable after a reload (the user re-selects the same source to
 * resume; already-received parts are skipped via the server's status).
 *
 * Part PUTs go through the interceptor-bearing global axios instance directly
 * (raw octet-stream body) so a mid-upload 401 still triggers the keycloak
 * refresh+retry in ./http. The Blob body bypasses the snake_case converter.
 */
import axios from 'axios';
// Side-effect import: configures axios.defaults.baseURL + interceptors.
import './http';
import {
  useUploadCancel,
  useUploadFinalize,
  useUploadInit,
  useUploadStatus,
  type UploadManifestEntry,
} from './measurement_api';
import type { LocalSource } from './upload_source';
import type { MeasurementResponse } from '@/models/types';

/**
 * Client-side part size. MUST match the backend's MEASUREMENT_PART_SIZE_BYTES
 * (default 8 MiB) and stay <= the nginx MAX_PART_SIZE_MB cap, exactly like the
 * existing MAX_UPLOAD_MB sync between layers. Manifest `parts` counts are
 * derived from this, so it has to agree with the server.
 */
export const PART_SIZE = 8 * 1024 * 1024;
const CONCURRENCY = 4;
const LS_PREFIX = 'measurement.upload.';

// ---- localStorage index ---------------------------------------------------

export interface PendingUpload {
  measurementId: string;
  name: string;
  sourceKind: 'folder' | 'zip';
  manifest: UploadManifestEntry[];
}

function lsKey(id: string): string {
  return `${LS_PREFIX}${id}`;
}

function savePending(p: PendingUpload): void {
  try {
    localStorage.setItem(lsKey(p.measurementId), JSON.stringify(p));
  } catch {
    // Quota / private-mode — non-fatal; resume just won't be offered.
  }
}

export function clearPending(id: string): void {
  localStorage.removeItem(lsKey(id));
}

/**
 * If a re-selected source exactly matches a recorded pending upload (same kind
 * + identical manifest), return its measurementId so the caller can resume.
 * Exact-manifest match guarantees it's the same dataset, so skipping already-
 * received parts can never splice bytes into the wrong upload.
 */
export function findResumableUpload(source: LocalSource): string | null {
  const { manifest } = buildManifest(source);
  const key = manifestKey(manifest);
  for (const p of loadPendingUploads()) {
    if (p.sourceKind === source.kind && manifestKey(p.manifest) === key) {
      return p.measurementId;
    }
  }
  return null;
}

function manifestKey(m: UploadManifestEntry[]): string {
  return m
    .map((e) => `${e.relPath}:${e.size}:${e.parts}`)
    .sort()
    .join('|');
}

/** All unfinished uploads recorded in this browser (for the resume prompt). */
export function loadPendingUploads(): PendingUpload[] {
  const out: PendingUpload[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(LS_PREFIX)) continue;
    try {
      const v = JSON.parse(localStorage.getItem(key) ?? '');
      if (v && typeof v.measurementId === 'string') out.push(v as PendingUpload);
    } catch {
      // Corrupt entry — skip.
    }
  }
  return out;
}

// ---- manifest + slicing ---------------------------------------------------

function partCount(size: number): number {
  return Math.max(1, Math.ceil(size / PART_SIZE));
}

function partSizeFor(entry: UploadManifestEntry, partNo: number): number {
  return Math.min(PART_SIZE, entry.size - partNo * PART_SIZE);
}

function sliceBlob(blob: Blob, partNo: number): Blob {
  const start = partNo * PART_SIZE;
  return blob.slice(start, Math.min(start + PART_SIZE, blob.size));
}

/**
 * Build the manifest + a `blobFor(relPath)` resolver. Folder paths use
 * `webkitRelativePath` (includes the dropped root folder) so the backend's
 * resolve_project_root peels the wrapper exactly like the sync path.
 */
function buildManifest(source: LocalSource): {
  manifest: UploadManifestEntry[];
  blobFor: (rel: string) => Blob;
} {
  if (source.kind === 'zip') {
    const manifest: UploadManifestEntry[] = [
      { relPath: 'source.zip', size: source.blob.size, parts: partCount(source.blob.size) },
    ];
    return { manifest, blobFor: () => source.blob };
  }
  const byRel = new Map<string, File>();
  const manifest: UploadManifestEntry[] = [];
  for (const f of source.files) {
    const rel = f.webkitRelativePath || f.name;
    byRel.set(rel, f);
    manifest.push({ relPath: rel, size: f.size, parts: partCount(f.size) });
  }
  return {
    manifest,
    blobFor: (rel) => {
      const f = byRel.get(rel);
      if (!f) throw new Error(`No file for rel_path ${rel}; re-select the source to resume.`);
      return f;
    },
  };
}

function makeCanceledError(): Error {
  const e = new Error('Upload canceled') as Error & { code?: string };
  e.name = 'CanceledError';
  e.code = 'ERR_CANCELED';
  return e;
}

async function putPart(
  measurementId: string,
  rel: string,
  partNo: number,
  of: number,
  blob: Blob,
  signal: AbortSignal,
): Promise<void> {
  // Preserve slashes (backend route is {rel_path:path}); encode each segment.
  const encRel = rel.split('/').map(encodeURIComponent).join('/');
  await axios.put(`/measurement/upload/${measurementId}/parts/${encRel}`, blob, {
    params: { n: partNo, of },
    headers: { 'Content-Type': 'application/octet-stream' },
    signal,
  });
}

// ---- uploader -------------------------------------------------------------

export interface UploadProgressInfo {
  sentBytes: number;
  totalBytes: number;
  percent: number;
  sentParts: number;
  totalParts: number;
}

export type UploaderPhase =
  | 'idle'
  | 'initializing'
  | 'uploading'
  | 'paused'
  | 'finalizing'
  | 'done'
  | 'error'
  | 'canceled';

export interface ChunkedUploaderOptions {
  onProgress?: (p: UploadProgressInfo) => void;
  onPhase?: (phase: UploaderPhase) => void;
}

export class ChunkedUploader {
  private abort = new AbortController();
  private paused = false;
  private resumeWaiters: Array<() => void> = [];
  private phase: UploaderPhase = 'idle';
  measurementId: string | null = null;

  constructor(
    private source: LocalSource,
    private meta: { name: string; description?: string },
    private opts: ChunkedUploaderOptions = {},
    private resumeId?: string,
  ) {}

  private setPhase(p: UploaderPhase): void {
    this.phase = p;
    this.opts.onPhase?.(p);
  }

  pause(): void {
    if (this.phase === 'uploading') {
      this.paused = true;
      this.setPhase('paused');
    }
  }

  resume(): void {
    if (this.paused) {
      this.paused = false;
      this.setPhase('uploading');
      const waiters = this.resumeWaiters.splice(0);
      waiters.forEach((w) => w());
    }
  }

  private waitIfPaused(): Promise<void> {
    if (!this.paused) return Promise.resolve();
    return new Promise<void>((resolve) => this.resumeWaiters.push(resolve));
  }

  /** Abort in-flight parts, ask the server to drop the row + tmp, clear index. */
  async cancel(): Promise<void> {
    this.abort.abort();
    this.paused = false;
    this.resumeWaiters.splice(0).forEach((w) => w());
    this.setPhase('canceled');
    if (this.measurementId) {
      try {
        await useUploadCancel(this.measurementId);
      } catch {
        // Best effort — orphan cleanup will reap an abandoned upload anyway.
      }
      clearPending(this.measurementId);
    }
  }

  async start(): Promise<MeasurementResponse> {
    const { manifest, blobFor } = buildManifest(this.source);
    const totalParts = manifest.reduce((s, e) => s + e.parts, 0);
    const totalBytes = manifest.reduce((s, e) => s + e.size, 0);

    // relPath -> set of part indices already on the server (resume).
    const received = new Map<string, Set<number>>();

    this.setPhase('initializing');
    if (this.resumeId) {
      this.measurementId = this.resumeId;
      const status = await useUploadStatus(this.resumeId);
      for (const f of status.files) received.set(f.relPath, new Set(f.receivedParts));
    } else {
      const res = await useUploadInit({
        name: this.meta.name,
        description: this.meta.description,
        sourceKind: this.source.kind,
        manifest,
      });
      this.measurementId = res.measurementId;
      savePending({
        measurementId: res.measurementId,
        name: this.meta.name,
        sourceKind: this.source.kind,
        manifest,
      });
    }

    // Build the work queue, counting already-received parts toward progress.
    const tasks: { relPath: string; partNo: number; of: number }[] = [];
    let sentParts = 0;
    let sentBytes = 0;
    for (const e of manifest) {
      const got = received.get(e.relPath) ?? new Set<number>();
      for (let n = 0; n < e.parts; n++) {
        if (got.has(n)) {
          sentParts += 1;
          sentBytes += partSizeFor(e, n);
        } else {
          tasks.push({ relPath: e.relPath, partNo: n, of: e.parts });
        }
      }
    }

    const emit = (): void => {
      this.opts.onProgress?.({
        sentBytes,
        totalBytes,
        percent: totalBytes > 0 ? Math.round((sentBytes / totalBytes) * 100) : 100,
        sentParts,
        totalParts,
      });
    };
    emit();

    this.setPhase('uploading');
    let idx = 0;
    const worker = async (): Promise<void> => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        if (this.abort.signal.aborted) throw makeCanceledError();
        await this.waitIfPaused();
        if (this.abort.signal.aborted) throw makeCanceledError();
        const i = idx;
        idx += 1;
        if (i >= tasks.length) return;
        const t = tasks[i];
        const blob = sliceBlob(blobFor(t.relPath), t.partNo);
        await putPart(this.measurementId!, t.relPath, t.partNo, t.of, blob, this.abort.signal);
        sentParts += 1;
        sentBytes += blob.size;
        emit();
      }
    };

    const workerCount = Math.min(CONCURRENCY, Math.max(1, tasks.length));
    await Promise.all(Array.from({ length: workerCount }, () => worker()));

    this.setPhase('finalizing');
    const measurement = await useUploadFinalize(this.measurementId!);
    clearPending(this.measurementId!);
    this.setPhase('done');
    return measurement;
  }
}
