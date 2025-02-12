import { defineStore } from "pinia";
import { ref } from "vue";
import { useDashboardProgrammes, useDashboardCategoryChildren } from "@/plugins/dashboard_api";
import { IDashboardCategory } from "@/models/apiTypes";

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
    const getDashboardCategoryChildren = async (uuid: string, category: string) => {
        dashboardCategoryChildren.value = await useDashboardCategoryChildren(uuid, category);
    };
    return {
        dashboardCategoryChildren,
        getDashboardCategoryChildren,
    };
});