import axios from 'axios';
import JSZip from 'jszip';
import { getAccessToken } from './keycloak';
// Side-effect import: ensures axios.defaults.baseURL is configured.
import './http';

export type UploadProgress =
  | { phase: 'zip'; percent: number; currentFile?: string }
  | { phase: 'upload'; loaded: number; total: number; percent: number }
  | { phase: 'server' };

export interface UploadSourceResponse {
  uploadId: string;
  foldersInRoot: string[];
  packageVersion?: string;
  packageAuthor?: string;
  hasCwl: boolean;
}

/**
 * What the dropzone produces and what the upload helpers consume.
 *
 * - `folder`: enumerated `File[]` from `<input webkitdirectory>` or a recursive
 *   `webkitGetAsEntry` walk. Needs client-side zipping before upload.
 * - `zip`: a single .zip blob the user dropped/picked directly. Skips the
 *   client-side zip phase and uploads as-is.
 */
export type LocalSource =
  | {
      kind: 'folder';
      files: File[];
      rootName: string;
      fileCount: number;
      totalSize: number;
    }
  | {
      kind: 'zip';
      blob: Blob;
      rootName: string;
      fileCount: number;
      totalSize: number;
    };

export interface UploadSourceOptions {
  onProgress?: (p: UploadProgress) => void;
  signal?: AbortSignal;
}

const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);

function isBlacklisted(relPath: string): boolean {
  return relPath.split('/').some((seg) => FOLDER_BLACKLIST.has(seg));
}

/** Axios-compatible cancel error so the existing `ERR_CANCELED` / `CanceledError`
 *  catch branches in the callers treat a zip-phase cancel exactly like an
 *  aborted network request (reset the dropzone, no error toast). */
function makeCanceledError(): Error {
  const e = new Error('Upload canceled') as Error & { code?: string };
  e.name = 'CanceledError';
  e.code = 'ERR_CANCELED';
  return e;
}

async function buildZipFromFiles(
  files: File[],
  onProgress?: (p: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<Blob> {
  const throwIfAborted = () => {
    if (signal?.aborted) throw makeCanceledError();
  };

  const zip = new JSZip();
  for (const file of files) {
    throwIfAborted();
    const relPath = file.webkitRelativePath || file.name;
    if (isBlacklisted(relPath)) continue;
    zip.file(relPath, file);
  }

  const genPromise = zip.generateAsync(
    { type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } },
    (meta) => {
      // Throwing here asks JSZip to stop generating; the race below guarantees
      // the awaiter unblocks immediately even if JSZip keeps churning in the
      // background (it can't be hard-killed, but its result is discarded).
      throwIfAborted();
      onProgress?.({
        phase: 'zip',
        percent: meta.percent,
        currentFile: meta.currentFile ?? undefined,
      });
    },
  );

  if (!signal) return genPromise;
  return new Promise<Blob>((resolve, reject) => {
    if (signal.aborted) {
      reject(makeCanceledError());
      return;
    }
    const onAbort = () => reject(makeCanceledError());
    signal.addEventListener('abort', onAbort, { once: true });
    genPromise.then(
      (blob) => {
        signal.removeEventListener('abort', onAbort);
        resolve(blob);
      },
      (err) => {
        signal.removeEventListener('abort', onAbort);
        reject(err);
      },
    );
  });
}

async function buildBlobForSource(
  source: LocalSource,
  onProgress?: (p: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<Blob> {
  // For zip kind we deliberately skip the zip-phase progress; the dropzone UI
  // will jump straight from `scanned` to `uploading` when the first
  // onUploadProgress event fires.
  if (source.kind === 'zip') return source.blob;
  return buildZipFromFiles(source.files, onProgress, signal);
}

async function postZip(
  endpoint: string,
  blob: Blob,
  opts: UploadSourceOptions,
): Promise<UploadSourceResponse> {
  const formData = new FormData();
  // Field name must match the backend signature: `file: UploadFile = File(...)`
  // in both workflow_tool_plugin.py and workflow_router.py upload-source endpoints.
  formData.append('file', blob, 'source.zip');

  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const total = blob.size;
  const res = await axios.post(endpoint, formData, {
    headers,
    signal: opts.signal,
    onUploadProgress: (e) => {
      const loaded = e.loaded;
      const t = e.total ?? total;
      // Once the body is fully flushed to the socket the transfer is done and
      // the server is extracting/validating. Flip the UI out of the cancelable
      // "upload" state immediately so the user isn't shown "Uploading… 100%"
      // with a Cancel button that can no longer stop the (already-sent) bytes.
      if (t > 0 && loaded >= t) {
        opts.onProgress?.({ phase: 'server' });
        return;
      }
      opts.onProgress?.({
        phase: 'upload',
        loaded,
        total: t,
        percent: t > 0 ? Math.round((loaded / t) * 100) : 0,
      });
    },
  });

  opts.onProgress?.({ phase: 'server' });
  // The global axios response interceptor (see ./http) deep-camelizes res.data,
  // so the snake_case backend payload arrives as UploadSourceResponse already.
  return res.data as UploadSourceResponse;
}

export async function useUploadToolSource(
  source: LocalSource,
  opts: UploadSourceOptions = {},
): Promise<UploadSourceResponse> {
  const blob = await buildBlobForSource(source, opts.onProgress, opts.signal);
  return postZip('/tools/upload-source', blob, opts);
}

export async function useUploadWorkflowSource(
  source: LocalSource,
  opts: UploadSourceOptions = {},
): Promise<UploadSourceResponse> {
  const blob = await buildBlobForSource(source, opts.onProgress, opts.signal);
  return postZip('/workflow/upload-source', blob, opts);
}

// The measurement sync upload (useUploadMeasurementSource) was removed when the
// measurement source path moved to chunked upload — see measurement_upload.ts.
// tool / workflow keep the sync upload helpers above.
