import http from "./http";
import { IDashboardCategory, IDashboardWorkflow, IAssayDetails } from "@/models/apiTypes";

export async function useDashboardProgrammes() {
    const programmes = http.get<IDashboardCategory[]>("/dashboard/programmes");
    return programmes;
}

export async function useDashboardCategoryChildren(uuid: string, category: string) {
    const details = http.get<IDashboardCategory[]>("/dashboard/category-children", { uuid, category });
    return details;
}

export async function useDashboardWorkflows() {
    const workflows = http.get<IDashboardWorkflow[]>("/dashboard/workflows");
    return workflows;
}

export async function useDashboardWorkflowDetail(uuid: string) {
    const details = http.get<IDashboardWorkflow>("/dashboard/workflow-detail", { uuid });
    return details;
}

export async function useSaveAssayDetails(body: IAssayDetails) {
    const success = http.post<boolean>("/dashboard/assay-details", body);
    return success;
  }

export async function useDashboardGetAssayDetails(uuid: string) {
    const details = http.get<IAssayDetails>("/dashboard/assay-details", { uuid });
    return details;
}