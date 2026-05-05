import { ref } from 'vue';
import type { CheckNameResponse } from '@/models/types';

export interface LocalFolderInfo {
  /** root folder name (taken from webkitRelativePath first segment) */
  name: string;
  /** package.json author (string or .name), empty when missing */
  author: string;
  /** package.json version (empty string if not found) */
  version: string;
  /** top-level directories inside the chosen root */
  foldersInRoot: string[];
  /** whether at least one .cwl file exists in the root */
  cwlExists: boolean;
  /** CWL validation result, populated after refresh in checkCwl mode */
  cwlRepoErr: CheckNameResponse | undefined;
}

const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);

function isBlacklisted(relPath: string): boolean {
  const segments = relPath.split('/');
  return segments.some((seg) => FOLDER_BLACKLIST.has(seg));
}

/**
 * Composable for parsing metadata from a locally selected folder.
 *
 * Mirrors the shape of {@link useGithubRepoInfo} so {@link BaseInformationStep}
 * can swap between the two without branching consumers.
 *
 * Usage:
 *   const { info, refresh } = useLocalFolderInfo();
 *   await refresh(files, isCwlCheck);
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

  /**
   * Parse a list of files (typically the FileList from `<input webkitdirectory>`).
   *
   * @param files     Files retained after the dropzone's blacklist filter.
   * @param checkCwl  When true, treat absence of a root `.cwl` as an error.
   */
  async function refresh(files: File[], checkCwl = false): Promise<void> {
    info.value.name = '';
    info.value.author = '';
    info.value.version = '';
    info.value.foldersInRoot = [];
    info.value.cwlExists = false;
    info.value.cwlRepoErr = undefined;

    if (!files || files.length === 0) {
      if (checkCwl) {
        info.value.cwlRepoErr = {
          available: false,
          message: 'No CWL files found in the root of the selected folder.',
        };
      }
      return;
    }

    // Determine root folder: first segment of every webkitRelativePath should match.
    const firstPath = files[0].webkitRelativePath || files[0].name;
    const rootName = firstPath.split('/')[0] ?? '';
    info.value.name = rootName;

    // Walk files: detect root-level folders and root-level .cwl / package.json
    const rootFolders = new Set<string>();
    let rootPackageJson: File | undefined;
    let rootHasCwl = false;

    for (const file of files) {
      const relPath = file.webkitRelativePath || file.name;
      if (isBlacklisted(relPath)) continue;

      const parts = relPath.split('/');
      // Expect [rootName, child, ...]
      if (parts.length < 2) continue;
      const child = parts[1];

      if (parts.length === 2) {
        // Direct file under root
        if (child === 'package.json') {
          rootPackageJson = file;
        } else if (child.endsWith('.cwl')) {
          rootHasCwl = true;
        }
      } else {
        // Anything deeper means `child` is a directory under root
        if (!FOLDER_BLACKLIST.has(child)) {
          rootFolders.add(child);
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

    // Read root package.json (best-effort)
    if (rootPackageJson) {
      try {
        const text = await rootPackageJson.text();
        const pkg = JSON.parse(text);
        if (typeof pkg.version === 'string') info.value.version = pkg.version;
        if (typeof pkg.author === 'string') {
          info.value.author = pkg.author;
        } else if (pkg.author && typeof pkg.author === 'object' && typeof pkg.author.name === 'string') {
          info.value.author = pkg.author.name;
        }
      } catch (err) {
        console.warn('Failed to parse root package.json:', err);
      }
    }
  }

  return { info, refresh };
}
