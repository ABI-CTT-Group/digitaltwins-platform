import http, { dtApi } from "./http";
import {
  ToolInformationStep,
  IAnnotation,
  CheckNameResponse,
  ToolResponse,
  BuildResponse,
  ToolDeployResponse,
  ToolMinIOMetadata,
  ExcuteBuildResponse,
  AnnotationResponse,
  TransientAuth,
  ProbeSourceRequest,
  ProbeSourceResponse,
  ToolApprovalStatus,
  SeekProject,
} from "@/models/types";

/** A ``tools`` row of GET /digitaltwins-api/datasets (keys camelCased by the interceptor). */
interface PlatformToolDataset {
  datasetUuid: string;
  datasetName?: string;
  toolType?: string;
  seekId?: string;
  fhirStatus?: string;
  fhirFailureMessage?: string;
  createdAt?: string;
}
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";
import { getAccessToken, getKeycloak } from './keycloak';

/** Proactively refresh the Keycloak token before making raw fetch calls that
 *  bypass axios. Falls through to the current token on any error. */
async function freshToken(): Promise<string> {
  try {
    const kc = getKeycloak();
    if (kc) await kc.updateToken(5);
  } catch {
    /* fall through to current token */
  }
  return getAccessToken() as string;
}

/** Build the optional POST body for a build trigger. Sent in camelCase —
 *  http.ts axios interceptor deep-snake_cases outgoing JSON. Empty / missing
 *  values are dropped so a public build's POST body is just `{}` (matches
 *  the backend's BuildTriggerRequest dataclass defaults). */
const _toBuildBody = (auth?: TransientAuth): Record<string, unknown> => {
  if (!auth) return {};
  const body: Record<string, unknown> = {};
  if (auth.token) body.token = auth.token;
  if (auth.authUsername) body.authUsername = auth.authUsername;
  if (auth.verifySsl === false) body.verifySsl = false;
  return body;
};

/** @deprecated Use useCheckName('tool', name) from api_helpers instead */
export const useCheckToolName = (name: string): Promise<CheckNameResponse> =>
  useCheckName('tool', name);

export async function useCreateTool(plugin:ToolInformationStep) {
    const createToolResponse = http.post<ToolResponse>("/tools/create", plugin)
    return createToolResponse
}

export async function useCreateToolAnnotation(id:string, annotation:IAnnotation) {
    const createToolResponse = http.post<AnnotationResponse>(`/tools/plugin/${id}/annotation`, annotation)
    return createToolResponse
}

export async function useWorkflowTools(): Promise<ToolResponse[]> {
  return fetchWithLatestBuild<ToolResponse>(
    '/tools/',
    (id) => `/tools/plugin/${id}/builds`,
    // Enrich with deploy status for GUI tools whose latest build completed
    async (tool, latestBuild) => {
      const handoff = { handoffStatus: latestBuild.handoffStatus ?? null };
      if (!tool.hasBackend || latestBuild.status !== 'completed') return handoff;
      try {
        const deploys = await http.get<ToolDeployResponse[]>(
          `/tools/plugin/build/${latestBuild.buildId}/deploys`,
        );
        if (deploys.length > 0) {
          const latestDeploy = deploys.sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
          )[0];
          return {
            ...handoff,
            deployStatus: latestDeploy.status,
            latestDeployId: latestDeploy.deployId,
            // start/end so the log console can show deploy DURATION on reopen
            latestDeployCreatedAt: latestDeploy.createdAt,
            latestDeployUpdatedAt: latestDeploy.updatedAt,
          } as Partial<ToolResponse>;
        }
      } catch (err) {
        console.warn(`Failed to fetch deploys for tool ${tool.id}:`, err);
      }
      return handoff;
    },
  ) as Promise<ToolResponse[]>;
}

const PLATFORM_LABELS: Record<string, string> = { gui: "GUI", script: "Script", notebook: "Notebook" };

/** Tools in the platform that no portal plugin produced (uploaded through the REST API). */
export async function usePlatformTools(known: Set<string>): Promise<ToolResponse[]> {
  const res = await dtApi.get<{ datasets: PlatformToolDataset[] }>("/datasets", { categories: "tools" });
  return (res.datasets ?? [])
    .filter((d) => !known.has(d.datasetUuid) && PLATFORM_LABELS[d.toolType ?? ""])
    .map((d) => ({
      id: d.datasetUuid, uuid: d.datasetUuid, name: d.datasetName || d.datasetUuid, version: "",
      label: PLATFORM_LABELS[d.toolType!], description: "Uploaded to the platform directly.",
      status: "completed", platformOnly: true, hasBackend: false, toolMetadata: {}, repositoryUrl: "",
      frontendFolder: "", frontendBuildCommand: "", backendDeployCommand: "",
      createdAt: d.createdAt ?? "", updatedAt: d.createdAt ?? "",
    }));
}

/** gui SDS workflows' tools as Tool Hub rows; their workflow builds them (GET /api/workflow/gui-tools). */
export async function useWorkflowGuiTools(): Promise<ToolResponse[]> {
  return http.get<ToolResponse[]>("/workflow/gui-tools");
}

/** The Tool Hub: portal tools, gui workflows' tools, then platform-only tools (each source can fail on its own). */
export async function useToolHub(): Promise<ToolResponse[]> {
  const [tools, workflowTools] = await Promise.all([
    useWorkflowTools(),
    useWorkflowGuiTools().catch((err) => {
      console.warn("Failed to list gui workflow tools:", err);
      return [] as ToolResponse[];
    }),
  ]);
  const known = new Set([...tools, ...workflowTools].map((t) => t.uuid).filter((u): u is string => !!u));
  const platform = await usePlatformTools(known).catch((err) => {
    console.warn("Failed to list platform tools:", err);
    return [] as ToolResponse[];
  });
  return [...tools, ...workflowTools, ...platform];
}

export async function useDeployWorkflowTool(workflowId: string) {
  return http.get(`/workflow/${workflowId}/deploy`);
}

export async function useToolMetadata() {
  const metadata = http.get<ToolMinIOMetadata>("/tools/metadata")
  return metadata
}

export async function useWorkflowToolBuild(id: string, auth?: TransientAuth) {
  const res = http.post<ExcuteBuildResponse>(
    `/tools/plugin/${id}/build`,
    _toBuildBody(auth),
  );
  return res;
}

/** POST /api/tools/probe-source — used by `useGitRepoInfo` for non-public-GitHub
 *  paths. Token (if supplied) stays server-side; the response carries either
 *  `{ok:true, data}` (autofill the form) or `{ok:false, reason, message}`
 *  (frontend uses `reason` to decide which UI fields to expand). */
export async function useProbeToolSource(
  req: ProbeSourceRequest,
): Promise<ProbeSourceResponse> {
  return http.post<ProbeSourceResponse>(`/tools/probe-source`, req);
}

export async function useDeleteTool(id:string) {
  const res = http.delete(`/tools/plugin/${id}`)
  return res;
}

/** Hand the latest build to the platform (SEEK + Postgres + MinIO, optional FHIR), as the signed-in user. */
export async function useToolApproval(id: string, body: { seekProjectId?: number; fhir?: boolean }) {
  return http.post<ToolApprovalStatus>(`/tools/plugin/${id}/approval`, body);
}

/** Handoff progress. Polling it also hands the backend a fresh token, which resumes a paused handoff. */
export async function useToolApprovalStatus(id: string) {
  return http.get<ToolApprovalStatus>(`/tools/plugin/${id}/approval/status`);
}

/** SEEK projects the signed-in user can see (digitaltwins-api). */
export async function useSeekProjects(): Promise<SeekProject[]> {
  const res = await dtApi.get<{ projects: Array<{ id: string | number; title?: string; attributes?: { title?: string } }> }>(
    "/projects",
  );
  return (res.projects ?? []).map((p) => ({
    id: Number(p.id), title: p.attributes?.title ?? p.title ?? `Project ${p.id}`,
  }));
}

/** The platform dataset (fhirStatus etc.) of an approved tool. */
export async function usePlatformDataset(uuid: string) {
  return (await dtApi.get<{ dataset: PlatformToolDataset }>(`/datasets/${uuid}`)).dataset;
}

export async function useRetryToolFhir(uuid: string) {
  return dtApi.post(`/datasets/${uuid}/fhir/push`, {});
}

export async function useDeployTool(id:string) {
  const res = http.get(`/tools/plugin/${id}/deploy`)
  return res;
}

export async function useDockerCompose(deployId:string, command:"up"|"down") {
  const res = http.get(`/tools/plugin/deploy/${deployId}/execute`, {command})
  return res;
}

export async function useGetDockerComposeStatus(deployId:string) {
  const res = http.get<boolean>(`/tools/check/deploy/${deployId}/`)
  return res;
}

export async function useGetWorkflowToolAnnotation(id:string){
  const res = http.get<AnnotationResponse>(`/tools/plugin/${id}/annotation`)
  return res;
}

export async function useGetToolLocalCwl(id: string): Promise<{ cwlFile: string; content: string }> {
  return http.get<{ cwlFile: string; content: string }>(`/tools/plugin/${id}/cwl`);
}

// ---------------------------------------------------------------------------
// SSE log streaming (Phase 4)
// ---------------------------------------------------------------------------

const _logPath = (kind: 'build' | 'deploy', id: string) =>
  kind === 'build' ? `/api/tools/builds/${id}/logs` : `/api/tools/deploy/${id}/logs`;

export function streamLogs(
  kind: 'build' | 'deploy',
  jobId: string,
  onLine: (l: string) => void,
  onEnd: (status: string) => void,
  onError: (e: unknown) => void,
): AbortController {
  const ctrl = new AbortController();
  (async () => {
    try {
      const token = await freshToken();
      const res = await fetch(`${_logPath(kind, jobId)}/stream`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: ctrl.signal,
      });
      if (!res.body) throw new Error('no stream body');
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        // SSE events are separated by blank lines
        let idx;
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const evt = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const isEnd = evt.startsWith('event: end');
          const data = evt.split('\n')
            .filter((l) => l.startsWith('data:'))
            .map((l) => l.slice(5).replace(/^ /, '')).join('\n');
          if (isEnd) { onEnd(data || 'completed'); return; }
          if (data) onLine(data);
        }
      }
    } catch (e) {
      if (!ctrl.signal.aborted) onError(e);
    }
  })();
  return ctrl;
}

export async function getLogs(kind: 'build' | 'deploy', jobId: string): Promise<string> {
  const token = await freshToken();
  const res = await fetch(_logPath(kind, jobId), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`logs ${res.status}`);
  return res.text();
}
