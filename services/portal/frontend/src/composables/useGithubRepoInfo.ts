import { ref } from 'vue';
import type { CheckNameResponse, SourceType, TransientAuth } from '@/models/types';
import {
  getRepoNameFromUrl,
  getRepoAuthorFromUrl,
  getRepoContents,
  inferProviderFromUrl,
} from '@/views/upload-dataset/components/utils';
import type { GitContent, ProbeSourceResponse, ProbeFailureReason } from '@/models/types';
import { useProbeToolSource } from '@/bootstrap/tool_api';
import { useProbeWorkflowSource } from '@/bootstrap/workflow_api';

export interface GitRepoInfo {
  /** repo name extracted from URL */
  name: string;
  /** repo author / owner extracted from URL */
  author: string;
  /** package.json version (empty string if not found) */
  version: string;
  /** top-level directories in the repo root */
  foldersInRoot: string[];
  /** whether at least one .cwl file exists in the repo root */
  cwlExists: boolean;
  /** CWL validation result (populated after refresh) */
  cwlRepoErr: CheckNameResponse | undefined;
  /** Provider inferred from URL — set on every refresh, drives parent's
   *  `formData.sourceType` so the registration POST carries the right type. */
  provider: Exclude<SourceType, "local">;
  /** Structured probe failure (only set when backend returned ok:false).
   *  Frontend uses `reason` to decide which UI fields to expand:
   *    - auth_required / not_found → expand token (+ username if generic)
   *    - tls_error → expand "Trust self-signed cert" toggle
   *    - network / unknown → show error, no field expansion */
  probeFailure?: { reason: ProbeFailureReason; message: string };
}

/**
 * Multi-provider git repo metadata fetcher.
 *
 * Dispatch policy (per phase 0.3 decision Y):
 * - **Public GitHub** without token → keep the existing browser-side anonymous
 *   GitHub Contents/Trees API path. No backend roundtrip; no token handling.
 * - **Everything else** (private GitHub, GitLab, Bitbucket, generic git) →
 *   POST `/probe-source` to the backend, which shallow-clones via askpass and
 *   returns the same metadata shape as `inspect_uploaded_source`. Token never
 *   leaves the request body and is never persisted.
 *
 * The composable holds two separate paths because forcing public GitHub
 * through the backend would (a) lose anonymous rate-limit benefits and
 * (b) regress an existing well-tested path.
 *
 * Usage:
 *   const { info, refresh } = useGitRepoInfo();
 *   await refresh(repositoryUrl, isCwlCheck, { type: 'tool', auth: { token } });
 */
export function useGitRepoInfo() {
  const info = ref<GitRepoInfo>({
    name: '',
    author: '',
    version: '',
    foldersInRoot: [],
    cwlExists: false,
    cwlRepoErr: undefined,
    provider: 'github',
    probeFailure: undefined,
  });

  /** Normalize a git URL by ensuring it ends with `.git`. */
  const normalizeUrl = (url: string): string => {
    if (!url) return '';
    const cleaned = url.replace(/\.git$/, '');
    return cleaned + '.git';
  };

  /** Find all `package.json` paths recursively via GitHub Trees API.
   *  Used only on the public-GitHub anonymous path. */
  async function findPackageJsonPaths(repoUrl: string): Promise<string[]> {
    const branch = 'main';
    // Build /repos/{owner}/{repo} URL — same logic as convertToApiUrl in utils.
    const stripped = repoUrl.replace(/\.git$/, '').replace(/\/$/, '');
    const parts = stripped.split('/');
    const owner = parts[parts.length - 2];
    const repo = parts[parts.length - 1];
    const treeUrl = `https://api.github.com/repos/${owner}/${repo}/git/trees/${branch}?recursive=1`;

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

  /** Refresh public-GitHub metadata via anonymous Contents API. Preserves
   *  the original `useGithubRepoInfo` behavior — same network calls, same
   *  failure modes — so this code path is a behavioral no-op for already
   *  working public flows. */
  async function refreshPublicGithub(
    normalizedUrl: string,
    checkCwl: boolean,
  ): Promise<void> {
    info.value.foldersInRoot = [];
    info.value.cwlExists = false;
    info.value.cwlRepoErr = undefined;

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
      // Map the GitHub API status to a structured reason code so
      // CommonInfoForm's v-if expansion picks the right field
      // (private repos return 404, not 401 — GitHub deliberately hides
      // unauthorized access this way to avoid leaking repo existence).
      const msg = err instanceof Error ? err.message : String(err);
      const m = msg.match(/GitHub API error:\s*(\d+)/i);
      let reason: ProbeFailureReason = 'network';
      let friendly = msg;
      if (m) {
        const status = parseInt(m[1], 10);
        if (status === 404) {
          reason = 'not_found';
          friendly = 'Repository not found. If this is a private repository, provide a Personal Access Token below.';
        } else if (status === 401) {
          reason = 'auth_required';
          friendly = 'Authentication required. Provide a Personal Access Token below.';
        } else if (status === 403) {
          // 403 from GitHub anon API is almost always rate-limit related
          // (60 req/hr cap). Authenticated requests get 5000/hr.
          reason = 'rate_limit';
          friendly = 'GitHub API rate limit reached. Provide a Personal Access Token to authenticate.';
        }
      }
      console.error('Error fetching repo contents (public GitHub):', err);
      info.value.probeFailure = { reason, message: friendly };
      return;
    }

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
      console.error('Error reading package.json (public GitHub):', err);
    }
  }

  /** Refresh metadata via backend `/probe-source` — used for private GitHub,
   *  all GitLab/Bitbucket, and generic git. Token (if any) is in the POST
   *  body, never persisted. */
  async function refreshViaBackend(
    normalizedUrl: string,
    provider: Exclude<SourceType, "local">,
    auth: TransientAuth | undefined,
    backendKind: 'tool' | 'workflow',
    checkCwl: boolean,
  ): Promise<void> {
    info.value.foldersInRoot = [];
    info.value.cwlExists = false;
    info.value.cwlRepoErr = undefined;

    const probe = backendKind === 'tool' ? useProbeToolSource : useProbeWorkflowSource;
    let res: ProbeSourceResponse;
    try {
      // Body is in camelCase — http.ts axios interceptor deep-snake_cases
      // outgoing JSON before sending, and deep-camelCases incoming responses.
      res = await probe({
        sourceType: provider,
        url: normalizedUrl,
        token: auth?.token,
        authUsername: auth?.authUsername,
        verifySsl: auth?.verifySsl ?? true,
      });
    } catch (err) {
      console.error('Probe-source request failed:', err);
      info.value.probeFailure = {
        reason: 'network',
        message: err instanceof Error ? err.message : 'Failed to reach backend probe-source',
      };
      return;
    }

    if (!res.ok) {
      info.value.probeFailure = { reason: res.reason, message: res.message };
      return;
    }

    // Response data is camelCase post-interceptor (backend ships snake_case
    // `folders_in_root` / `package_version` / `has_cwl` / `cwl_required`).
    info.value.foldersInRoot = res.data.foldersInRoot;
    if (res.data.packageVersion) info.value.version = res.data.packageVersion;
    if (res.data.packageAuthor) info.value.author = res.data.packageAuthor;
    if (checkCwl) {
      info.value.cwlExists = res.data.hasCwl;
      info.value.cwlRepoErr = res.data.hasCwl
        ? { available: true, message: '' }
        : { available: false, message: 'No CWL files found in the root of the repository.' };
    }
  }

  /**
   * Refresh repo metadata for any git provider.
   *
   * @param repositoryUrl   The git URL (with or without `.git` suffix)
   * @param checkCwl        When true, populate `cwlExists` / `cwlRepoErr`
   * @param opts.kind       'tool' or 'workflow' — picks the backend probe endpoint
   * @param opts.auth       Optional token / auth_username / verify_ssl —
   *                        triggers backend dispatch even for github
   *
   * Returns the normalized URL; the parent component should also read
   * `info.value.provider` to update its `sourceType` field.
   */
  async function refresh(
    repositoryUrl: string,
    checkCwl = false,
    opts: { kind: 'tool' | 'workflow'; auth?: TransientAuth } = { kind: 'tool' },
  ): Promise<string> {
    if (!repositoryUrl) return repositoryUrl;

    const normalizedUrl = normalizeUrl(repositoryUrl);
    const provider = inferProviderFromUrl(normalizedUrl);

    info.value.name = getRepoNameFromUrl(normalizedUrl);
    info.value.author = getRepoAuthorFromUrl(normalizedUrl);
    info.value.provider = provider;
    info.value.probeFailure = undefined;

    // Public GitHub without token → anonymous Contents API (preserved).
    // Anything else (private GitHub, GitLab, Bitbucket, generic) → backend.
    const usePublicGithubPath =
      provider === 'github' && !opts.auth?.token;

    if (usePublicGithubPath) {
      await refreshPublicGithub(normalizedUrl, checkCwl);
    } else {
      await refreshViaBackend(normalizedUrl, provider, opts.auth, opts.kind, checkCwl);
    }

    return normalizedUrl;
  }

  return { info, refresh, normalizeUrl };
}

/** @deprecated Use `useGitRepoInfo` — same API, multi-provider aware. */
export const useGithubRepoInfo = useGitRepoInfo;

/** @deprecated Use `GitRepoInfo`. */
export type GithubRepoInfo = GitRepoInfo;
