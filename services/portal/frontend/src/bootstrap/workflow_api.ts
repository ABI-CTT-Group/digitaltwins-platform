import http from "./http";
import {
    IAnnotation,
    CheckNameResponse,
    WorkflowInformationStep,
    WorkflowResponse,
    AnnotationResponse,
    BuildResponse,
    ExcuteBuildResponse
} from "@/models/types";
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";

/** @deprecated Use useCheckName('workflow', name) from api_helpers instead */
export const useCheckToolName = (name: string): Promise<CheckNameResponse> =>
  useCheckName('workflow', name);

export async function useCreateWorkflow(workflow:WorkflowInformationStep) {
    const createWorkflowResponse = http.post<WorkflowResponse>("/workflow/create", workflow)
    return createWorkflowResponse
}

export async function useCreateWorkflowAnnotation(id:string, annotation:IAnnotation) {
    const createAnnotationResponse = http.post<AnnotationResponse>(`/workflow/${id}/annotation`, annotation)
    return createAnnotationResponse
}

export async function useWorkflowBuild(workflowId: string) {
    const buildRes = http.get<ExcuteBuildResponse>(`/workflow/${workflowId}/build`)
    return buildRes
}

export async function useDeleteWorkflow(workflowId: string) {
    const deleteRes = http.delete(`/workflow/${workflowId}`)
    return deleteRes
}

export async function useWorkflow(): Promise<WorkflowResponse[]> {
  return fetchWithLatestBuild<WorkflowResponse>(
    '/workflow/',
    (id) => `/workflow/${id}/builds`,
  ) as Promise<WorkflowResponse[]>;
}

export async function useWorkflowApproval(workflowId:string) {
  const res = http.get(`/workflow/${workflowId}/approval`)
  return res;
}

export async function useGetWorkflowLocalCwl(id: string): Promise<{ cwlFile: string; content: string }> {
  return http.get<{ cwlFile: string; content: string }>(`/workflow/${id}/cwl`);
}