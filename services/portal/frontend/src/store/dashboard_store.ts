import { defineStore } from "pinia";
import { ref } from "vue";
import {
    useDashboardProgrammes,
    useDashboardCategoryChildren,
    useDashboardWorkflows,
    useSaveAssayDetails,
 } from "@/plugins/dashboard_api";
import { IDashboardCategory, IDashboardWorkflow, IAssayDetails } from "@/models/apiTypes";

export const useDashboardProgrammesStore = defineStore("DashboardProgrammes", () => {
    const dashboardProgrammes = ref<IDashboardCategory[]>();
    const getDashboardProgrammes = async () => {
        dashboardProgrammes.value = await useDashboardProgrammes();
    };
    return {
        dashboardProgrammes,
        getDashboardProgrammes,
    };
});

export const useDashboardCategoryChildrenStore = defineStore("DashboardCategoryChildren", () => {
    const dashboardCategoryChildren = ref<IDashboardCategory[]>();
    const getDashboardCategoryChildren = async (seek_id: string, category: string) => {
        dashboardCategoryChildren.value = await useDashboardCategoryChildren(seek_id, category);
    };
    return {
        dashboardCategoryChildren,
        getDashboardCategoryChildren,
    };
});

export const useDashboardWorkflowsStore = defineStore("DashboardWorkflows", () => {
    const dashboardWorkflows = ref<IDashboardWorkflow[]>();
    const getDashboardWorkflows = async () => {
        dashboardWorkflows.value = await useDashboardWorkflows();
    };
    return {
        dashboardWorkflows,
        getDashboardWorkflows,
    };
});

export const useDashboardSaveAssayDetailsStore = defineStore("DashboardSaveAssayDetails", () => {
    const saveAssayDetailsStatus = ref<boolean>();
    const saveAssayDetails = async (body: IAssayDetails): Promise<boolean> => {
        saveAssayDetailsStatus.value = await useSaveAssayDetails(body);
        return !!saveAssayDetailsStatus.value;
    };
    return {
        saveAssayDetailsStatus,
        saveAssayDetails,
    };
});

