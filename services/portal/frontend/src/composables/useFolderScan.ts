/**
 * Shared folder/zip scanning primitives for the upload dropzones.
 *
 * These are the source-agnostic pieces that both `LocalFolderDropzone` (the
 * sync tool/workflow/measurement-legacy dropzone) and `MeasurementChunkedDropzone`
 * (the chunked measurement dropzone) need: drag-drop tree traversal, the
 * blacklist, zip detection, byte formatting, and the single-wrapper root
 * detection that mirrors the backend's `resolve_project_root`.
 *
 * Intentionally framework-free (no reactive state) so each component keeps its
 * own UI state machine and only borrows the mechanics. Lifted verbatim from
 * the original LocalFolderDropzone implementation to preserve behavior.
 */

export const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);

export function isBlacklisted(relPath: string): boolean {
  return relPath.split('/').some((seg) => FOLDER_BLACKLIST.has(seg));
}

export function isZipFile(f: File): boolean {
  return (
    f.name.toLowerCase().endsWith('.zip')
    || f.type === 'application/zip'
    || f.type === 'application/x-zip-compressed'
  );
}

export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0 B';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

/**
 * Recursive single-wrapper detection. Mirrors the backend's
 * `resolve_project_root`: peels nested `outer/inner/project/...` chains until
 * we hit a level that contains either multiple top-level dirs OR any
 * top-level files. Returns the prefix to strip (with trailing slash) or `""`.
 */
export function findRootPrefix(entries: { path: string; isDir: boolean }[]): string {
  let prefix = '';
  for (let depth = 0; depth < 20; depth++) {
    const topDirs = new Set<string>();
    const topFiles = new Set<string>();
    for (const e of entries) {
      if (e.path === '__MACOSX' || e.path.startsWith('__MACOSX/')) continue;
      if (prefix && !e.path.startsWith(prefix)) continue;
      const rel = prefix ? e.path.slice(prefix.length) : e.path;
      if (!rel) continue;
      const trimmed = rel.replace(/\/$/, '');
      if (!trimmed) continue;
      const segments = trimmed.split('/');
      if (!segments[0]) continue;
      if (segments.length === 1) {
        if (e.isDir) topDirs.add(segments[0]);
        else topFiles.add(segments[0]);
      } else {
        topDirs.add(segments[0]);
      }
    }
    if (topDirs.size === 1 && topFiles.size === 0) {
      prefix += `${Array.from(topDirs)[0]}/`;
    } else {
      break;
    }
  }
  return prefix;
}

/**
 * Walk a `FileSystemEntry` tree (from `webkitGetAsEntry`) collecting `File`
 * objects with their `webkitRelativePath` set. `onTick(count)` fires every 25
 * files so the caller can repaint a live counter.
 */
export async function traverseEntry(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  entry: any,
  out: File[],
  pathPrefix: string,
  onTick?: (count: number) => void,
): Promise<void> {
  if (entry.isFile) {
    await new Promise<void>((resolve) => {
      entry.file((file: File) => {
        const relPath = pathPrefix ? `${pathPrefix}/${entry.name}` : entry.name;
        try {
          Object.defineProperty(file, 'webkitRelativePath', {
            value: relPath,
            configurable: true,
          });
        } catch {
          // Some browsers won't let us redefine; ignore.
        }
        out.push(file);
        resolve();
      });
    });
    if (out.length % 25 === 0) {
      onTick?.(out.length);
      await new Promise((r) => setTimeout(r, 0));
    }
    return;
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const children: any[] = await new Promise((resolve) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const all: any[] = [];
      const readBatch = () =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        reader.readEntries((batch: any[]) => {
          if (batch.length === 0) resolve(all);
          else {
            all.push(...batch);
            readBatch();
          }
        });
      readBatch();
    });
    const nextPrefix = pathPrefix ? `${pathPrefix}/${entry.name}` : entry.name;
    for (const child of children) {
      await traverseEntry(child, out, nextPrefix, onTick);
    }
  }
}

/**
 * Snapshot a DataTransfer SYNCHRONOUSLY before any await. Once a drop handler
 * yields, `dataTransfer.items` is cleared by the browser and
 * `webkitGetAsEntry()` returns null. FileSystemEntry refs + File objects
 * survive across awaits; the act of *obtaining* them is what must be sync.
 */
export function captureDataTransfer(dt: DataTransfer): {
  flatFiles: File[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  captured: { entry?: any; file?: File }[];
} {
  const flatFiles = Array.from(dt.files);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const captured: { entry?: any; file?: File }[] = [];
  for (let i = 0; i < dt.items.length; i++) {
    const item = dt.items[i];
    if (item.kind !== 'file') continue;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const entry: any = (item as any).webkitGetAsEntry?.();
    if (entry) {
      captured.push({ entry });
    } else {
      const f = item.getAsFile();
      if (f) captured.push({ file: f });
    }
  }
  return { flatFiles, captured };
}

export interface FolderScanResult {
  kept: File[];
  keptSize: number;
  skippedCount: number;
  skippedSize: number;
  rootName: string;
}

/**
 * Apply the blacklist filter to a flat File list and derive the display root.
 * Pure: returns the partition + root, no UI side effects.
 */
export function filterFolderFiles(files: File[]): FolderScanResult {
  const kept: File[] = [];
  let keptSize = 0;
  let skippedCount = 0;
  let skippedSize = 0;

  for (const f of files) {
    const relPath = f.webkitRelativePath || f.name;
    if (isBlacklisted(relPath)) {
      skippedCount += 1;
      skippedSize += f.size;
      continue;
    }
    kept.push(f);
    keptSize += f.size;
  }

  const firstRelPath = kept.length ? kept[0].webkitRelativePath || kept[0].name : '';
  const rootName = firstRelPath.includes('/') ? firstRelPath.split('/')[0] : '';

  return { kept, keptSize, skippedCount, skippedSize, rootName };
}
