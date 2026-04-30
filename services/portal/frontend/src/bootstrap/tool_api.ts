import http from "./http";
import {
  IToolInformationStep,
  IAnnotation,
  CheckNameResponse,
  ToolResponse,
  BuildResponse,
  ToolDeployResponse,
  ToolMinIOMetadata,
  ExcuteBuildResponse,
  IAnnotationResponse,
} from "@/models/types";
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";

/** @deprecated Use useCheckName('tool', name) from api_helpers instead */
export const useCheckToolName = (name: string): Promise<CheckNameResponse> =>
  useCheckName('tool', name);

export async function useCreateTool(plugin:IToolInformationStep) {
    const createToolResponse = http.post<ToolResponse>("/tools/create", plugin)
    return createToolResponse
}

export async function useCreateToolAnnotation(id:string, annotation:IAnnotation) {
    const createToolResponse = http.post<IAnnotationResponse>(`/tools/plugin/${id}/annotation`, annotation)
    return createToolResponse
}

export async function useWorkflowTools(): Promise<ToolResponse[]> {
  return fetchWithLatestBuild<ToolResponse>(
    '/tools/',
    (id) => `/tools/plugin/${id}/builds`,
    // Enrich with deploy status for GUI tools whose latest build completed
    async (tool, latestBuild) => {
      if (!tool.has_backend || latestBuild.status !== 'completed') return {};
      try {
        const deploys = await http.get<ToolDeployResponse[]>(
          `/tools/plugin/build/${latestBuild.build_id}/deploys`,
        );
        if (deploys.length > 0) {
          const latestDeploy = deploys.sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
          )[0];
          return {
            deploy_status: latestDeploy.status,
            latest_deploy_id: latestDeploy.deploy_id,
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

export async function useDockerCompose(deploy_id:string, command:"up"|"down") {
  const res = http.get(`/tools/plugin/deploy/${deploy_id}/execute`, {command})
  return res;
}

export async function useGetDockerComposeStatus(deploy_id:string) {
  const res = http.get<boolean>(`/tools/check/deploy/${deploy_id}/`)
  return res;
}

export async function useGetWorkflowToolAnnotation(id:string){
  const res = http.get<IAnnotationResponse>(`/tools/plugin/${id}/annotation`)
  return res;
}