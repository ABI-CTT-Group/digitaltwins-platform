import http from "./http";
import { AxiosError } from "axios";
import { IToolInformationStep, CheckNameResponse, PluginResponse} from "@/models/uiTypes";


   

export async function useCheckPluginName(name: string): Promise<CheckNameResponse> {
  try {
    const status = await http.get<CheckNameResponse>("/workflow-tool/check-name", { name });
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
    const createPluginResponse = http.post<PluginResponse>("/workflow-tool/plugins", plugin)
    return createPluginResponse
}

