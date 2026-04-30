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
} from "@/models/types";
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";

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

export async function useWorkflowToolBuild(id:string) {
  const res = http.get<ExcuteBuildResponse>(`/tools/plugin/${id}/build`)
  return res
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