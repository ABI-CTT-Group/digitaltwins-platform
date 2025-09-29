import http from "./http";
import { AxiosError } from "axios";
import { 
  IToolInformationStep, 
  CheckNameResponse, 
  PluginResponse, 
  PluginBuildResponse, 
  PluginMinIOMetadata,
  PluginExcuteBuildResponse} from "@/models/uiTypes";


   

export async function useCheckPluginName(name: string): Promise<CheckNameResponse> {
  try {
    const status = await http.get<CheckNameResponse>("/workflow-tools/check-name", { name });
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

export async function useCreateToolPlugin(plugin:IToolInformationStep) {
    const createPluginResponse = http.post<PluginResponse>("/workflow-tools/create", plugin)
    return createPluginResponse
}

export async function useWorkflowTools() {
  const workflowTools = http.get<Array<PluginResponse>>("/workflow-tools").then(async (tools)=>{
    const formattedWorkflowTools = await Promise.all(tools.map(async (tool)=>{
      let buildStatus = 'pending'
      try {
        const buildsResponse = await http.get<Array<PluginBuildResponse>>(`/workflow-tools/plugin/${tool.id}/builds`)
        if(buildsResponse.length > 0){
          // get the most recent build
          const lastestBuild = buildsResponse.sort((a:PluginBuildResponse, b:PluginBuildResponse)=> 
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
          buildStatus = lastestBuild.status
        }
        
      }catch(buildError){
        console.warn(`Failed to fetch builds for workflow tool ${tool.id}:`, buildError)
      }
      return {
        ...tool,
        description: tool.description == "" ? "No description available" : tool.description,
        status: buildStatus
      }
    }))
    return formattedWorkflowTools
  })
  return workflowTools
}

export async function useMinIoWorkflowToolMetadata() {
  const metadata = http.get<PluginMinIOMetadata>("/workflow-tools/metadata")
  return metadata
}

export async function useWorkflowToolBuild(id:string) {
  const res = http.get<PluginExcuteBuildResponse>(`/workflow-tools/plugin/${id}/build`)
  return res
}

export async function useDeleteTool(id:string) {
  const res = http.delete(`/workflow-tools/plugin/${id}`)
  return res;
}

export async function useToolApproval(id:string) {
  const res = http.get(`/workflow-tools/plugin/${id}/approval`)
  return res;
}

export async function useDeployTool(id:string) {
  const res = http.get(`/workflow-tools/plugin/${id}/deploy`)
  return res;
}