import { defineStore } from "pinia";
import { ref } from "vue";
import { AssayDetails } from "@/models/types";

/**
 * Transient caches for the dashboard, keyed by assay seekId. The drill-down
 * navigation state lives entirely in the URL (route query), NOT here — so this
 * store holds only per-assay config/launch state and is never persisted.
 */
export const useDashboardCacheStore = defineStore("dashboardCache", () => {
  const assayDetails = ref<Record<string, AssayDetails>>({});
  const assayExecute = ref<Record<string, { text: string; url: string; isLaunching?: boolean }>>({});
  const currentAssayDetails = ref<AssayDetails | undefined>();
  // Display names captured from the assays list, so the report page can show the
  // title without a redundant seek-assay fetch when arriving from the dashboard.
  const assayNames = ref<Record<string, string>>({});

  const setAssayDetails = (seekId: string, details: AssayDetails) => {
    assayDetails.value[seekId] = details;
  };
  const setAssayName = (seekId: string, name: string) => {
    assayNames.value[seekId] = name;
  };
  const setAssayExecute = (seekId: string, text: string, url: string) => {
    assayExecute.value[seekId] = { text, url };
  };
  const setAssayLaunching = (seekId: string, isLaunching: boolean) => {
    if (assayExecute.value[seekId]) assayExecute.value[seekId].isLaunching = isLaunching;
  };
  const setCurrentAssayDetails = (details: AssayDetails) => {
    currentAssayDetails.value = details;
  };

  return {
    assayDetails,
    assayExecute,
    currentAssayDetails,
    assayNames,
    setAssayDetails,
    setAssayName,
    setAssayExecute,
    setAssayLaunching,
    setCurrentAssayDetails,
  };
});
