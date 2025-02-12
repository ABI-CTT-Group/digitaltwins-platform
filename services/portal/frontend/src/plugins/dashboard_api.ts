import http from "./http";
import { IDashboardCategory } from "@/models/apiTypes";

export async function useDashboardProgrammes() {
    const programmes = http.get<IDashboardCategory[]>("/dashboard/programmes");
    return programmes;
}

export async function useDashboardCategoryChildren(uuid: string, category: string) {
    const details = http.get<IDashboardCategory[]>("/dashboard/category-children", { uuid, category });
    return details;
}