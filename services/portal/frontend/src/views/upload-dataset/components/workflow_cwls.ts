import yaml from 'js-yaml';
import type { GitContent, SourceType, TransientAuth, WorkflowResponse } from '@/models/types';
import { useGetWorkflowLocalCwl, useProbeWorkflowSource } from '@/bootstrap/workflow_api';
import { SDS_MARKER, getRepoContents, sdsWorkflowCwls } from '@/views/upload-dataset/components/utils';

export interface ParsedCwl { cwlFile: string; content: any }

/** A workflow's CWL for the Annotation step. `isSds` comes from the source itself; the build records the same. */
export interface WorkflowCwls { isSds: boolean; content: any; tools: ParsedCwl[] }

export function parseCwlText(raw: string): any {
  try { return yaml.load(raw); }
  catch { return JSON.parse(raw); }
}

/** Public GitHub without a token is read from the browser; private GitHub and other hosts go through /probe-source. */
export function canUsePublicGithubPath(sourceType: SourceType | undefined, auth?: TransientAuth | null): boolean {
  return sourceType === 'github' && !auth?.token;
}

const parseAll = (tools: { cwlFile: string; content: string }[] = []): ParsedCwl[] =>
  tools.map((t) => ({ cwlFile: t.cwlFile, content: parseCwlText(t.content) }));

async function readGithubFile(repositoryUrl: string, path: string): Promise<string> {
  const res = await getRepoContents(repositoryUrl, path);
  return atob((res.data.content as string).replace(/\n/g, ''));
}

/** SDS when the root has dataset_description.xlsx, as the backend's detect_workflow_layout decides. */
async function loadPublicGithub(repositoryUrl: string): Promise<WorkflowCwls> {
  const files = ((await getRepoContents(repositoryUrl)).data as GitContent[]).filter((item) => item.type === 'file');
  if (!files.some((item) => item.name === SDS_MARKER)) {
    const cwlFile = files.filter((item) => item.name.endsWith('.cwl')).pop()?.name;
    if (!cwlFile) throw new Error('No CWL file found at repo root.');
    return { isSds: false, content: parseCwlText(await readGithubFile(repositoryUrl, cwlFile)), tools: [] };
  }
  const primary = ((await getRepoContents(repositoryUrl, 'primary')).data as GitContent[])
    .filter((item) => item.type === 'file' && item.name.endsWith('.cwl'));
  const [wfName] = sdsWorkflowCwls(primary.map((item) => item.name));
  if (!wfName) throw new Error('No primary/workflow_*.cwl in the repository.');
  const tools = await Promise.all(primary.filter((item) => item.name.startsWith('tool_'))
    .map(async (item) => ({ cwlFile: item.name, content: parseCwlText(await readGithubFile(repositoryUrl, `primary/${item.name}`)) })));
  return { isSds: true, content: parseCwlText(await readGithubFile(repositoryUrl, `primary/${wfName}`)), tools };
}

export async function loadWorkflowCwls(workflow: WorkflowResponse, auth?: TransientAuth | null): Promise<WorkflowCwls> {
  if (workflow.sourceType === 'local') {
    const res = await useGetWorkflowLocalCwl(workflow.id);
    return { isSds: res.isSds, content: parseCwlText(res.content), tools: parseAll(res.toolCwls) };
  }
  if (canUsePublicGithubPath(workflow.sourceType, auth)) return loadPublicGithub(workflow.repositoryUrl);
  const res = await useProbeWorkflowSource({
    sourceType: workflow.sourceType as Exclude<SourceType, 'local'>, url: workflow.repositoryUrl,
    token: auth?.token, authUsername: auth?.authUsername, verifySsl: auth?.verifySsl ?? true,
  });
  if (!res.ok) throw new Error(`Failed to fetch CWL: ${res.message}`);
  if (!res.data.cwlContent) throw new Error('No CWL file found at the root of the repository.');
  return { isSds: !!res.data.isSds, content: parseCwlText(res.data.cwlContent), tools: parseAll(res.data.toolCwls) };
}
