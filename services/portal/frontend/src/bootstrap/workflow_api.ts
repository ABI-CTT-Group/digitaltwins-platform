import http from "./http";
import {
    IAnnotation,
    CheckNameResponse,
    IWorkflowInformationStep,
    IWorkflowResponse,
    IAnnotationResponse,
    BuildResponse,
    ExcuteBuildResponse
} from "@/models/types";
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";

/** @deprecated Use useCheckName('workflow', name) from api_helpers instead */
export const useCheckToolName = (name: string): Promise<CheckNameResponse> =>
  useCheckName('workflow', name);

export async function useCreateWorkflow(workflow:IWorkflowInformationStep) {
    const createWorkflowResponse = http.post<IWorkflowResponse>("/workflow/create", workflow)
    return createWorkflowResponse
}

export async function useCreateWorkflowAnnotation(id:string, annotation:IAnnotation) {
    const createAnnotationResponse = http.post<IAnnotationResponse>(`/workflow/${id}/annotation`, annotation)
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

export async function useWorkflow(): Promise<IWorkflowResponse[]> {
  return fetchWithLatestBuild<IWorkflowResponse>(
    '/workflow/',
    (id) => `/workflow/${id}/builds`,
  ) as Promise<IWorkflowResponse[]>;
}

export async function useWorkflowApproval(workflowId:string) {
  const res = http.get(`/workflow/${workflowId}/approval`)
  return res;
}