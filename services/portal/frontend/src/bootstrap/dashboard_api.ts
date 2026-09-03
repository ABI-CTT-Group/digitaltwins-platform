import http from "./http";
import axios from "axios";
import { DashboardCategory, DashboardWorkflow, AssayDetails, AssayLaunch, AssayDataset, SeekAssayDetails } from "@/models/types";

export async function useDashboardProgrammes() {
    const programmes = http.get<DashboardCategory[]>("/dashboard/programmes");
    return programmes;
}

export async function useDashboardCategoryChildren(seekId: string, category: string) {
    const details = http.get<DashboardCategory[]>("/dashboard/category-children", { seekId, category });
    return details;
}

export async function useDashboardWorkflows() {
    const workflows = http.get<DashboardWorkflow[]>("/dashboard/workflows");
    return workflows;
}

export async function useDashboardWorkflowDetail(seekId: string) {
    const details = http.get<DashboardWorkflow>("/dashboard/workflow-detail", { seekId });
    return details;
}

export async function useDashboardSeekAssay(seekId: string) {
    const details = http.get<SeekAssayDetails>(`/dashboard/assays/${seekId}`);
    return details;
}

export async function useSaveAssayDetails(body: AssayDetails) {
    const success = http.post<boolean>("/dashboard/assay-details", body);
    return success;
  }

export async function useDashboardGetAssayConfigDetails(seekId: string) {
    const details = http.get<AssayDetails>("/dashboard/assay-details", { seekId });
    return details;
}
export async function useDashboardGetAssayLaunch(seekId: string) {
    const details = http.get<AssayLaunch>("/dashboard/assay-launch", { seekId });
    return details;
}
export async function useDashboardGetDatasets(category: string) {
    const details = http.get<AssayDataset[]>("/dashboard/datasets", { category });
    return details;
}
export async function useDashboardSelectedDatasetSampleTypes(uuid: string) {
    const sampleTypes = http.get<string[]>("/dashboard/dataset-detail", { uuid });
    return sampleTypes;
}

export async function useDashboardSubmitAssayResults(seekId: string) {
    const success = http.post<any>(`/dashboard/assay-results-submit?seek_id=${seekId}`);
    return success;
}

export async function useDashboardDownloadAssayWorkspace(seekId: string) {
    const res = await axios.get("/dashboard/assay-download", { 
        params: { seek_id: seekId }, 
        responseType: 'blob' 
    });
    
    let filename = `assay_${seekId}_results.zip`;
    const cd = res.headers["content-disposition"];
    if (cd) {
        const match = cd.match(/filename="?([^"]+)"?/);
        if (match && match[1]) {
            filename = match[1];
        }
    }
    
    return { data: res.data, filename };
}
