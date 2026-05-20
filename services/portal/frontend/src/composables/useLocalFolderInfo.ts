import { ref } from 'vue';
import JSZip from 'jszip';
import type { CheckNameResponse } from '@/models/types';
import type { LocalSource } from '@/bootstrap/upload_source';

export interface LocalFolderInfo {
  /** Display root name (zip filename minus .zip, or webkitRelativePath top segment) */
  name: string;
  /** package.json author (string or .name), empty when missing */
  author: string;
  /** package.json version (empty string if not found) */
  version: string;
  /** top-level directories inside the resolved project root */
  foldersInRoot: string[];
  /** whether at least one .cwl file exists in the resolved project root */
  cwlExists: boolean;
  /** CWL validation result, populated after refresh in checkCwl mode */
  cwlRepoErr: CheckNameResponse | undefined;
}

const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);
const MAX_WRAPPER_DEPTH = 20;

function isBlacklisted(relPath: string): boolean {
  return relPath.split('/').some((seg) => FOLDER_BLACKLIST.has(seg));
}

function applyPackageJson(info: LocalFolderInfo, raw: string) {
  try {
    const pkg = JSON.parse(raw);
    if (typeof pkg.version === 'string') info.version = pkg.version;
    if (typeof pkg.author === 'string') {
      info.author = pkg.author;
    } else if (pkg.author && typeof pkg.author === 'object' && typeof pkg.author.name === 'string') {
      info.author = pkg.author.name;
    }
  } catch (err) {
    console.warn('Failed to parse package.json:', err);
  }
}

/**
 * Generic representation of a path inside the source. We use this to build
 * one wrapper-resolution algorithm that works for both folder (File[]) and
 * zip (JSZip entries) inputs.
 */
interface PathEntry {
  path: string;
  isDir: boolean;
}

/**
 * Walk down through single-wrapper directories until we hit a level that has
 * either multiple top-level dirs OR any top-level files. Mirrors the backend's
 * (now recursive) `resolve_project_root`. Returns the prefix (with trailing
 * slash) to strip from each entry, e.g. `"outer/inner/"` or `""`.
 */
function resolveRootPrefix(entries: PathEntry[]): string {
  let prefix = '';
  for (let depth = 0; depth < MAX_WRAPPER_DEPTH; depth++) {
    const topDirs = new Set<string>();
    const topFiles = new Set<string>();

    for (const e of entries) {
      // __MACOSX is the Finder zip-extra-attributes folder; ignore at every level.
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
        // Implies a directory at segments[0] regardless of whether the dir
        // entry itself is in the archive — many zippers omit dir entries.
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
 * Composable for parsing metadata from a locally selected source.
 *
 * Mirrors {@link useGithubRepoInfo} so {@link BaseInformationStep} can swap
 * between the two without branching consumers.
 */
export function useLocalFolderInfo() {
  const info = ref<LocalFolderInfo>({
    name: '',
    author: '',
    version: '',
    foldersInRoot: [],
    cwlExists: false,
    cwlRepoErr: undefined,
  });

  function reset() {
    info.value.name = '';
    info.value.author = '';
    info.value.version = '';
    info.value.foldersInRoot = [];
    info.value.cwlExists = false;
    info.value.cwlRepoErr = undefined;
  }

  function setNoCwlError() {
    info.value.cwlRepoErr = {
      available: false,
      message: 'No CWL files found in the root of the selected source.',
    };
  }

  /**
   * Refresh metadata from a {@link LocalSource}. `null` clears state.
   *
   * @param source    Folder (File[]) or zip (Blob) wrapper from the dropzone.
   * @param checkCwl  When true, treat absence of a root `.cwl` as an error.
   */
  async function refresh(source: LocalSource | null, checkCwl = false): Promise<void> {
    reset();

    if (!source) {
      if (checkCwl) setNoCwlError();
      return;
    }

    // Always trust the dropzone's rootName — it has the correct .zip stripping
    // and folder-root logic.
    info.value.name = source.rootName;

    if (source.kind === 'folder') {
      await refreshFromFiles(source.files, checkCwl);
    } else {
      await refreshFromZip(source.blob, checkCwl);
    }
  }

  async function refreshFromFiles(files: File[], checkCwl: boolean) {
    // FileList from <input webkitdirectory> always prefixes with the root
    // folder name; treat each file path as-is and let resolveRootPrefix peel
    // off the top segment(s) for us.
    const entries: PathEntry[] = [];
    for (const f of files) {
      const path = f.webkitRelativePath || f.name;
      if (isBlacklisted(path)) continue;
      entries.push({ path, isDir: false });
    }

    const rootPrefix = resolveRootPrefix(entries);

    const rootFolders = new Set<string>();
    let rootHasCwl = false;
    const pkgCandidates: { file: File; depth: number }[] = [];

    for (const f of files) {
      const fullPath = f.webkitRelativePath || f.name;
      if (isBlacklisted(fullPath)) continue;
      if (rootPrefix && !fullPath.startsWith(rootPrefix)) continue;

      const rel = rootPrefix ? fullPath.slice(rootPrefix.length) : fullPath;
      if (!rel) continue;
      const parts = rel.split('/');
      const first = parts[0];
      if (!first) continue;

      if (parts.length === 1) {
        if (first === 'package.json') pkgCandidates.push({ file: f, depth: 1 });
        else if (first.endsWith('.cwl')) rootHasCwl = true;
      } else {
        if (!FOLDER_BLACKLIST.has(first)) rootFolders.add(first);
        // Recursive package.json search — every nested package.json is a candidate.
        if (parts[parts.length - 1] === 'package.json') {
          pkgCandidates.push({ file: f, depth: parts.length });
        }
      }
    }

    info.value.foldersInRoot = Array.from(rootFolders).sort();
    info.value.cwlExists = rootHasCwl;

    if (checkCwl) {
      info.value.cwlRepoErr = rootHasCwl
        ? { available: true, message: '' }
        : {
            available: false,
            message: 'No CWL files found in the root of the selected folder.',
          };
    }

    // Pick the shallowest package.json — same heuristic as GitHub mode's
    // `findPackageJsonPaths()[0]`, just made explicit.
    pkgCandidates.sort((a, b) => a.depth - b.depth);
    const pkg = pkgCandidates[0];
    if (pkg) {
      try {
        applyPackageJson(info.value, await pkg.file.text());
      } catch (err) {
        console.warn('Failed to read package.json from folder:', err);
      }
    }
  }

  async function refreshFromZip(blob: Blob, checkCwl: boolean) {
    let zip: JSZip;
    try {
      zip = await JSZip.loadAsync(blob);
    } catch (err) {
      console.warn('Failed to read zip archive:', err);
      if (checkCwl) setNoCwlError();
      return;
    }

    const allPaths = Object.keys(zip.files);
    const entries: PathEntry[] = allPaths
      .filter((p) => !p.startsWith('__MACOSX/'))
      .filter((p) => !isBlacklisted(p))
      .map((p) => ({ path: p, isDir: zip.files[p].dir }));

    const rootPrefix = resolveRootPrefix(entries);

    const rootFolders = new Set<string>();
    let rootHasCwl = false;
    const pkgCandidates: { entry: JSZip.JSZipObject; depth: number }[] = [];

    for (const path of allPaths) {
      if (path.startsWith('__MACOSX/')) continue;
      if (rootPrefix && !path.startsWith(rootPrefix)) continue;
      if (isBlacklisted(path)) continue;

      const rel = rootPrefix ? path.slice(rootPrefix.length) : path;
      if (!rel) continue;

      const trimmed = rel.replace(/\/$/, '');
      if (!trimmed) continue;
      const parts = trimmed.split('/');
      const first = parts[0];

      if (parts.length === 1) {
        if (zip.files[path].dir) {
          if (!FOLDER_BLACKLIST.has(first)) rootFolders.add(first);
        } else if (first === 'package.json') {
          pkgCandidates.push({ entry: zip.files[path], depth: 1 });
        } else if (first.endsWith('.cwl')) {
          rootHasCwl = true;
        }
      } else {
        if (!FOLDER_BLACKLIST.has(first)) rootFolders.add(first);
        const last = parts[parts.length - 1];
        if (last === 'package.json' && !zip.files[path].dir) {
          pkgCandidates.push({ entry: zip.files[path], depth: parts.length });
        }
      }
    }

    info.value.foldersInRoot = Array.from(rootFolders).sort();
    info.value.cwlExists = rootHasCwl;

    if (checkCwl) {
      info.value.cwlRepoErr = rootHasCwl
        ? { available: true, message: '' }
        : {
            available: false,
            message: 'No CWL files found in the root of the selected zip.',
          };
    }

    pkgCandidates.sort((a, b) => a.depth - b.depth);
    const pkg = pkgCandidates[0];
    if (pkg) {
      try {
        applyPackageJson(info.value, await pkg.entry.async('string'));
      } catch (err) {
        console.warn('Failed to read package.json from zip:', err);
      }
    }
  }

  return { info, refresh };
}
