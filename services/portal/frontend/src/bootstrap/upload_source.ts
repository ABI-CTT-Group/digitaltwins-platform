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

async function buildZipFromFiles(
  files: File[],
  onProgress?: (p: UploadProgress) => void,
): Promise<Blob> {
  const zip = new JSZip();
  for (const file of files) {
    const relPath = file.webkitRelativePath || file.name;
    if (isBlacklisted(relPath)) continue;
    zip.file(relPath, file);
  }
  return zip.generateAsync(
    { type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } },
    (meta) =>
      onProgress?.({
        phase: 'zip',
        percent: meta.percent,
        currentFile: meta.currentFile ?? undefined,
      }),
  );
}

async function buildBlobForSource(
  source: LocalSource,
  onProgress?: (p: UploadProgress) => void,
): Promise<Blob> {
  // For zip kind we deliberately skip the zip-phase progress; the dropzone UI
  // will jump straight from `scanned` to `uploading` when the first
  // onUploadProgress event fires.
  if (source.kind === 'zip') return source.blob;
  return buildZipFromFiles(source.files, onProgress);
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
  const blob = await buildBlobForSource(source, opts.onProgress);
  return postZip('/tools/upload-source', blob, opts);
}

export async function useUploadWorkflowSource(
  source: LocalSource,
  opts: UploadSourceOptions = {},
): Promise<UploadSourceResponse> {
  const blob = await buildBlobForSource(source, opts.onProgress);
  return postZip('/workflow/upload-source', blob, opts);
}
