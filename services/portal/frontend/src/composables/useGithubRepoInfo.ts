import { ref } from 'vue';
import type { CheckNameResponse } from '@/models/types';
import {
  getRepoNameFromUrl,
  getRepoAuthorFromUrl,
  getRepoContents,
  convertToApiUrl,
} from '@/views/upload-dataset/components/utils';
import type { GitContent } from '@/models/types';

export interface GithubRepoInfo {
  /** repo name extracted from URL */
  name: string;
  /** repo author extracted from URL */
  author: string;
  /** package.json version (empty string if not found) */
  version: string;
  /** top-level directories in the repo root */
  foldersInRoot: string[];
  /** whether at least one .cwl file exists in the repo root */
  cwlExists: boolean;
  /** CWL validation result (populated after refresh) */
  cwlRepoErr: CheckNameResponse | undefined;
}

/**
 * Composable for fetching GitHub repo metadata.
 *
 * Usage:
 *   const { info, refresh } = useGithubRepoInfo();
 *   await refresh(repositoryUrl, isTool);
 */
export function useGithubRepoInfo() {
  const info = ref<GithubRepoInfo>({
    name: '',
    author: '',
    version: '',
    foldersInRoot: [],
    cwlExists: false,
    cwlRepoErr: undefined,
  });

  /**
   * Normalize a GitHub URL by ensuring it ends with `.git`.
   */
  const normalizeUrl = (url: string): string => {
    if (!url) return '';
    const cleaned = url.replace(/\.git$/, '');
    return cleaned + '.git';
  };

  /**
   * Find all `package.json` files (recursively) in the repo and return their paths.
   */
  async function findPackageJsonPaths(repoUrl: string): Promise<string[]> {
    const branch = 'main';
    const apiBase = convertToApiUrl(repoUrl);
    const treeUrl = `${apiBase}/git/trees/${branch}?recursive=1`;

    const res = await fetch(treeUrl, {
      headers: { Accept: 'application/vnd.github+json' },
    });
    if (!res.ok) throw new Error(`GitHub API error: ${res.status}`);

    const data = await res.json();
    const tree: { path: string }[] = data.tree ?? [];
    return tree
      .filter((item) => item.path.endsWith('package.json'))
      .map((item) => item.path);
  }

  /**
   * Refresh repo metadata from GitHub.
   *
   * @param repositoryUrl  The GitHub repository URL (with or without .git suffix)
   * @param checkCwl       When true, look for .cwl files in the root; otherwise populate foldersInRoot for GUI tool
   */
  async function refresh(repositoryUrl: string, checkCwl = false): Promise<string> {
    if (!repositoryUrl) return repositoryUrl;

    const normalizedUrl = normalizeUrl(repositoryUrl);

    info.value.name = getRepoNameFromUrl(normalizedUrl);
    info.value.author = getRepoAuthorFromUrl(normalizedUrl);
    info.value.foldersInRoot = [];
    info.value.cwlExists = false;
    info.value.cwlRepoErr = undefined;

    // Fetch root contents (folders + optional CWL detection)
    try {
      const res = await getRepoContents(normalizedUrl);
      const items = res!.data as GitContent[];
      const cwlFiles: string[] = [];

      items.forEach((item: GitContent) => {
        if (item.type === 'dir') {
          info.value.foldersInRoot.push(item.name);
        } else if (item.type === 'file' && item.name.endsWith('.cwl')) {
          cwlFiles.push(item.name);
        }
      });

      if (checkCwl) {
        info.value.cwlExists = cwlFiles.length > 0;
        info.value.cwlRepoErr = cwlFiles.length > 0
          ? { available: true, message: '' }
          : { available: false, message: 'No CWL files found in the root of the repository.' };
      }
    } catch (err) {
      console.error('Error fetching repo contents:', err);
    }

    // Read package.json version
    try {
      const pkgPaths = await findPackageJsonPaths(normalizedUrl);
      if (pkgPaths.length > 0) {
        const pkgRes = await getRepoContents(normalizedUrl, pkgPaths[0]);
        const decoded = atob((pkgRes.data.content as string).replace(/\n/g, ''));
        const pkgJson = JSON.parse(decoded);
        if (pkgJson.version) {
          info.value.version = pkgJson.version;
        }
      }
    } catch (err) {
      console.error('Error reading package.json:', err);
    }

    return normalizedUrl;
  }

  return { info, refresh, normalizeUrl };
}
