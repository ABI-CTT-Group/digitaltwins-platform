import { GitContent, SourceType } from '@/models/types';
import yaml from "js-yaml";

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

export const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 1) return '1 day ago'
  if (diffDays < 30) return `${diffDays} days ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
  return `${Math.floor(diffDays / 365)} years ago`
}

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

export const getRepoRootCWLContent = (repositoryUrl: string) => {
  return new Promise<{ cwlFile: string, content: any }>((resolve, reject) => {
    getRepoContents(repositoryUrl).then((res) => {
      const folders = res!.data as GitContent[];
      let cwlFile = "";
      folders.forEach((item: GitContent) => {
        if (item.type == 'file' && item.name.endsWith(".cwl")) {
          cwlFile = item.name;
          return;
        }
      })
      getRepoContents(repositoryUrl, cwlFile).then((res) => {
        const contentBase64 = res.data.content;
        const content = atob(contentBase64); // base64 → plain text
        try {
          // try to parse YAML format first
          resolve({
            cwlFile,
            content: yaml.load(content)
          });
        } catch (err) {
          console.warn("YAML parse failed, trying JSON...");
          resolve({
            cwlFile,
            content: JSON.parse(content)
          }); // if it is JSON format
        }
      })
    })
  })

}