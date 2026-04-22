import http from "./http";
import { AxiosError } from "axios";
import { 
  IToolInformationStep, 
  IAnnotation,
  CheckNameResponse, 
  PluginResponse, 
  BuildResponse, 
  PluginDeployResponse,
  PluginMinIOMetadata,
  ExcuteBuildResponse,
  IAnnotationResponse} from "@/models/uiTypes";


   

export async function useCheckPluginName(name: string): Promise<CheckNameResponse> {
  try {
    const status = await http.get<CheckNameResponse>("/tools/check-name", { name });
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
    const createPluginResponse = http.post<PluginResponse>("/tools/create", plugin)
    return createPluginResponse
}

export async function useCreateToolPluginAnnotation(id:string, annotation:IAnnotation) {
    const createPluginResponse = http.post<IAnnotationResponse>(`/tools/plugin/${id}/annotation`, annotation)
    return createPluginResponse
}

export async function useWorkflowTools() {
  const workflowTools = http.get<Array<PluginResponse>>("/tools/").then(async (tools)=>{
    const formattedWorkflowTools = await Promise.all(tools.map(async (tool)=>{
      let buildStatus = 'pending'
      let deployStatus = undefined
      let lastestBuildId = undefined
      let latestDeployId = undefined
      try {
        const buildsResponse = await http.get<Array<BuildResponse>>(`/tools/plugin/${tool.id}/builds`)
        if(buildsResponse.length > 0){
          // get the most recent build
          const lastestBuild = buildsResponse.sort((a:BuildResponse, b:BuildResponse)=> 
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
          buildStatus = lastestBuild.status
          lastestBuildId = lastestBuild.build_id
          if(tool.has_backend && buildStatus === 'completed'){
    
            const deployResponses = await http.get<Array<PluginDeployResponse>>(`/tools/plugin/build/${lastestBuild.build_id}/deploys`)
            if(deployResponses.length > 0){
              const latestDeploy = deployResponses.sort((a:PluginDeployResponse, b:PluginDeployResponse)=>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
              deployStatus = latestDeploy.status
              latestDeployId = latestDeploy.deploy_id
            }
          }
        }
        
      }catch(buildError){
        console.warn(`Failed to fetch builds for workflow tool ${tool.id}:`, buildError)
      }
      return {
        ...tool,
        description: tool.description == "" ? "No description available" : tool.description,
        status: buildStatus,
        deploy_status: deployStatus,
        latest_build_id: lastestBuildId,
        latest_deploy_id: latestDeployId
      }
    }))
    return formattedWorkflowTools
  })
  return workflowTools
}

export async function useToolMetadata() {
  const metadata = http.get<PluginMinIOMetadata>("/tools/metadata")
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