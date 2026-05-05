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

export interface UploadSourceOptions {
  onProgress?: (p: UploadProgress) => void;
  signal?: AbortSignal;
}

const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);

function isBlacklisted(relPath: string): boolean {
  return relPath.split('/').some((seg) => FOLDER_BLACKLIST.has(seg));
}

async function buildZip(
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
        currentFile: meta.currentFile,
      }),
  );
}

async function postZip(
  endpoint: string,
  blob: Blob,
  opts: UploadSourceOptions,
): Promise<UploadSourceResponse> {
  const formData = new FormData();
  formData.append('archive', blob, 'source.zip');

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
  files: File[],
  opts: UploadSourceOptions = {},
): Promise<UploadSourceResponse> {
  const blob = await buildZip(files, opts.onProgress);
  return postZip('/tools/upload-source', blob, opts);
}

export async function useUploadWorkflowSource(
  files: File[],
  opts: UploadSourceOptions = {},
): Promise<UploadSourceResponse> {
  const blob = await buildZip(files, opts.onProgress);
  return postZip('/workflow/upload-source', blob, opts);
}
