import http from "./http";
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
} from "@/models/types";
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";

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
      if (!tool.hasBackend || latestBuild.status !== 'completed') return {};
      try {
        const deploys = await http.get<ToolDeployResponse[]>(
          `/tools/plugin/build/${latestBuild.buildId}/deploys`,
        );
        if (deploys.length > 0) {
          const latestDeploy = deploys.sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
          )[0];
          return {
            deployStatus: latestDeploy.status,
            latestDeployId: latestDeploy.deployId,
          } as Partial<ToolResponse>;
        }
      } catch (err) {
        console.warn(`Failed to fetch deploys for tool ${tool.id}:`, err);
      }
      return {};
    },
  ) as Promise<ToolResponse[]>;
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

export async function useToolApproval(id:string) {
  const res = http.get(`/tools/plugin/${id}/approval`)
  return res;
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