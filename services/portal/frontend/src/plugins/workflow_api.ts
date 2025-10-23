import http from "./http";
import { AxiosError } from "axios";
import { 
    IAnnotation,
    CheckNameResponse, 
    IWorkflowInformationStep,
    IWrokflowResponse,
    IAnnotationResponse,
    BuildResponse,
    ExcuteBuildResponse
} from "@/models/uiTypes";

export async function useCheckPluginName(name: string): Promise<CheckNameResponse> {
  try {
    const status = await http.get<CheckNameResponse>("/workflow/check-name", { name });
    return status;
  } catch (err) {
    const axiosErr = err as AxiosError<{ detail: string }>;
    if (axiosErr.response?.status === 400) {
      return {
        available: false,
        message: axiosErr.response.data.detail
      };
    } else {
      return {
        available: false,
        message: "Name cannot be used."
      };
    }
  }
}

export async function useCreateWorkflow(workflow:IWorkflowInformationStep) {
    const createWorkflowResponse = http.post<IWrokflowResponse>("/workflow/create", workflow)
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

export async function useWorkflow() {
  const workflows = http.get<Array<IWrokflowResponse>>("/workflow").then(async (items)=>{
      const formattedWorkflows = await Promise.all(items.map(async (workflow)=>{
        let buildStatus = 'pending'
        let lastestBuildId = undefined
        try {
          const buildsResponse = await http.get<Array<BuildResponse>>(`/workflow/${workflow.id}/builds`)
          if(buildsResponse.length > 0){
            // get the most recent build
            const lastestBuild = buildsResponse.sort((a:BuildResponse, b:BuildResponse)=> 
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
            buildStatus = lastestBuild.status
            lastestBuildId = lastestBuild.build_id
          }
          
        }catch(buildError){
          console.warn(`Failed to fetch builds for workflow tool ${workflow.id}:`, buildError)
        }
        return {
          ...workflow,
          description: workflow.description == "" ? "No description available" : workflow.description,
          status: buildStatus,
          latest_build_id: lastestBuildId,
        }
      }))
      return formattedWorkflows
    })
    return workflows
}

export async function useWorkflowApproval(workflowId:string) {
  const res = http.get(`/workflow/${workflowId}/approval`)
  return res;
}