import http from "./http";
import {
    IAnnotation,
    CheckNameResponse,
    WorkflowInformationStep,
    WorkflowResponse,
    AnnotationResponse,
    BuildResponse,
    ExcuteBuildResponse,
    TransientAuth,
    ProbeSourceRequest,
    ProbeSourceResponse,
} from "@/models/types";
import { useCheckName, fetchWithLatestBuild } from "./api_helpers";
import { usePlatformWorkflows } from "./platform_api";

const _toBuildBody = (auth?: TransientAuth): Record<string, unknown> => {
    if (!auth) return {};
    const body: Record<string, unknown> = {};
    if (auth.token) body.token = auth.token;
    if (auth.authUsername) body.authUsername = auth.authUsername;
    if (auth.verifySsl === false) body.verifySsl = false;
    return body;
};

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

export async function useWorkflowBuild(workflowId: string, auth?: TransientAuth) {
    const buildRes = http.post<ExcuteBuildResponse>(
        `/workflow/${workflowId}/build`,
        _toBuildBody(auth),
    );
    return buildRes;
}

/** POST /api/workflow/probe-source — see `useProbeToolSource`. */
export async function useProbeWorkflowSource(
    req: ProbeSourceRequest,
): Promise<ProbeSourceResponse> {
    return http.post<ProbeSourceResponse>(`/workflow/probe-source`, req);
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

/** The Workflow Hub: portal workflows plus platform-only ones (the platform being down hides only the latter). */
export async function useWorkflowHub(): Promise<WorkflowResponse[]> {
  const workflows = await useWorkflow();
  const known = new Set(workflows.map((w) => w.uuid).filter((u): u is string => !!u));
  const platform = await usePlatformWorkflows(known).catch((err) => {
    console.warn("Failed to list platform workflows:", err);
    return [] as WorkflowResponse[];
  });
  return [...workflows, ...platform];
}

export async function useWorkflowApproval(workflowId:string) {
  const res = http.get(`/workflow/${workflowId}/approval`)
  return res;
}

export async function useGetWorkflowLocalCwl(id: string): Promise<{ cwlFile: string; content: string }> {
  return http.get<{ cwlFile: string; content: string }>(`/workflow/${id}/cwl`);
}