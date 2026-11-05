import { CheckNameResponse, GitContent, SourceType } from '@/models/types';

/**
 * Infer git provider from URL host. Used at URL-blur time to decide which
 * acquirer the backend should dispatch and which form fields to show.
 *
 * Returns ``"git_generic"`` for self-hosted / unrecognized hosts —
 * generic acquirer requires a per-request `auth_username` (no canonical
 * convention), so the UI must surface that field for this case.
 */
export const inferProviderFromUrl = (url: string): Exclude<SourceType, "local"> => {
  if (!url) return "git_generic";
  let host = "";
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    // Try git@host:owner/repo SSH-style — pull host out manually.
    const m = url.match(/^git@([^:]+):/);
    host = m ? m[1].toLowerCase() : "";
  }
  if (host === "github.com" || host.endsWith(".github.com")) return "github";
  if (host === "gitlab.com" || host.endsWith(".gitlab.com")) return "gitlab";
  if (host === "bitbucket.org" || host.endsWith(".bitbucket.org")) return "bitbucket";
  return "git_generic";
};

/** Loose URL shape check — accepts `https://...` or `git@host:owner/repo`. */
export const looksLikeGitUrl = (url: string): boolean => {
  if (!url) return false;
  if (/^https?:\/\/\S+\/\S+/.test(url)) return true;
  if (/^git@\S+:\S+\/\S+/.test(url)) return true;
  return false;
};

export const getRepoNameFromUrl = (url: string) => {
  url = url.replace(/\/+$/, "");
  let name = url.split("/").pop();
  name = name!.replace(/\.git$/, "");
  return name;
}

export const getRepoAuthorFromUrl = (url: string) => {
  url = url.replace(/\.git$/, "").replace(/\/+$/, "");
  const parts = url.split("/");
  return parts[parts.length - 2];
}

export const convertToApiUrl = (repoUrl: string) => {
  repoUrl = repoUrl.replace(/\.git$/, "").replace(/\/$/, "");

  const parts = repoUrl.split("/");
  const owner = parts[parts.length - 2];
  const repo = parts[parts.length - 1];

  return `https://api.github.com/repos/${owner}/${repo}`;
}

export const getRepoContents = async (url: string, path: string = "") => {
  const rootContentUrl = convertToApiUrl(url) + `/contents/${path}`;
  const res = await fetch(rootContentUrl, {
    headers: {
      Accept: 'application/vnd.github+json',
    },
  });
  if (!res.ok) throw new Error(`GitHub API error: ${res.status}`);
  const data = await res.json();
  return { data };
}

// A tool is either source code (one .cwl at the root) or an SDS package whose
// CWL is primary/tool_*.cwl. Mirrors services/builder/app/engine/tool_layout.py.
export const SDS_MARKER = "dataset_description.xlsx";
const SDS_TOOL_CWL = /^tool_.*\.cwl$/;

export const sdsToolCwls = (primaryFiles: string[]) => primaryFiles.filter((name) => SDS_TOOL_CWL.test(name));

export const sdsCwlResult = (hasToolCwl: boolean): CheckNameResponse => hasToolCwl
  ? { available: true, message: "Detected an SDS package: its metadata is kept as-is." }
  : { available: false, message: "An SDS package must have exactly one primary/tool_*.cwl." };

export const noToolCwlMessage = (where: string) =>
  `No CWL found in the ${where}. Expected one .cwl at the root (source code), ` +
  `or one primary/tool_*.cwl in an SDS package (${SDS_MARKER} at the root).`;

const SDS_WORKFLOW_CWL = /^workflow_.*\.cwl$/;

export const sdsWorkflowCwls = (primaryFiles: string[]) => primaryFiles.filter((name) => SDS_WORKFLOW_CWL.test(name));

export const sdsWorkflowCwlResult = (ok: boolean): CheckNameResponse => ok
  ? { available: true, message: "Detected an SDS workflow package: approving it registers the workflow and its tools." }
  : { available: false, message: "An SDS workflow package must have exactly one primary/workflow_*.cwl." };

export const noWorkflowCwlMessage = (where: string) =>
  `No CWL found in the ${where}. Expected a .cwl at the root (source code), ` +
  `or one primary/workflow_*.cwl in an SDS package (${SDS_MARKER} at the root).`;

/** The tool's CWL file name and raw text from a public GitHub repo; rejects if it can't be fetched. */
export const getRepoRootCWLContent = async (repositoryUrl: string): Promise<{ cwlFile: string, content: string }> => {
  const folders = (await getRepoContents(repositoryUrl)).data as GitContent[];
  let cwlFile = "";
  let cwlPath = "";
  if (folders.some((item) => item.type == 'file' && item.name === SDS_MARKER)) {
    const primary = (await getRepoContents(repositoryUrl, "primary")).data as GitContent[];
    cwlFile = sdsToolCwls(primary.filter((item) => item.type == 'file').map((item) => item.name))[0] ?? "";
    cwlPath = `primary/${cwlFile}`;
  } else {
    cwlFile = folders.filter((item) => item.type == 'file' && item.name.endsWith(".cwl")).pop()?.name ?? "";
    cwlPath = cwlFile;
  }
  const res = await getRepoContents(repositoryUrl, cwlPath);
  return { cwlFile, content: atob(res.data.content) }; // base64 → plain text
}