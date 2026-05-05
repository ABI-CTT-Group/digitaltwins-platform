import http from "./http";
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
