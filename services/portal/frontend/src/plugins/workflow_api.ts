import http from "./http";
import { AxiosError } from "axios";
import { 
    IAnnotation,
    CheckNameResponse, 
    IWorkflowInformationStep,
    IWrokflowResponse,
    IAnnotationResponse
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
    const createPluginResponse = http.post<IWrokflowResponse>("/workflow/create", workflow)
    return createPluginResponse
}

export async function useCreateWorkflowAnnotation(id:string, annotation:IAnnotation) {
    const createPluginResponse = http.post<IAnnotationResponse>(`/workflow/${id}/annotation`, annotation)
    return createPluginResponse
}

export async function useWorkflow() {
  const workflowTools = http.get<Array<IWrokflowResponse>>("/workflow")
  return workflowTools
}