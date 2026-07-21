import { ref } from "vue";
import { useRouter } from "vue-router";
import { useToast } from "vue-toastification";
import { storeToRefs } from "pinia";
import { useDashboardCacheStore } from "@/store/dashboard_cache_store";
import {
  useDashboardGetAssayConfigDetails,
  useDashboardGetAssayLaunch,
  useDashboardWorkflowDetail,
  useSaveAssayDetails,
} from "@/bootstrap/dashboard_api";
import { DashboardCategory } from "@/models/types";
import { JUPYTER_BASE_URL } from "@/config/platform-links";
import { getApiErrorMessage } from "@/utils/common";

// Sheet UI state is shared across every component that drives the assay
// actions (each AssayCard + the host DashboardView that renders the sheets),
// so it lives at module scope as a single source of truth.
const downloadDialog = ref(false);
const submitDialog = ref(false);
const submitState = ref<"waiting" | "true" | "false" | "unavailable">("waiting");
const downloadZipProgressValue = ref(0);

/**
 * All assay-level actions (launch / monitor / verify / download / submit /
 * edit / save / expand) plus the loader that fills the per-assay cache when
 * the Assays level opens. State is held in `dashboard_cache_store`; this
 * composable is the behaviour layer over it.
 */
export function useAssayActions() {
  const router = useRouter();
  const toast = useToast();
  const store = useDashboardCacheStore();
  const { assayDetails, assayExecute, currentAssayDetails } = storeToRefs(store);

  /**
   * Populate per-assay config + launch state for the assays at the current
   * level: prefer the saved config; fall back to a workflow-only stub when no
   * config exists yet.
   *
   * Cache-aware — assays already loaded in the store are skipped, so returning
   * to an Assays level (e.g. back from the assay report) does NOT re-fetch.
   * State is keyed by seekId, so leaving stale assays from other studies in the
   * store is harmless (and keeps a launched assay's Monitor state alive across
   * navigations).
   */
  const loadAssayList = async (items: DashboardCategory[]) => {
    for (const item of items) {
      store.setAssayName(item.seekId, item.name); // cache name for the report title
      if (assayDetails.value[item.seekId]) continue; // already cached
      store.setAssayExecute(item.seekId, "Launch", "");
      const details = await useDashboardGetAssayConfigDetails(item.seekId);
      if (details) {
        store.setAssayDetails(item.seekId, details);
      } else {
        const workflowDetail = await useDashboardWorkflowDetail(item.workflowSeekId!);
        workflowDetail.type = item.tag ?? "unknown workflow type";
        store.setAssayDetails(item.seekId, {
          uuid: "",
          seekId: item.seekId,
          workflow: workflowDetail,
          numberOfParticipants: [],
          isAssayReadyToLaunch: false,
        });
      }
    }
  };

  const openEdit = (seekId: string) => {
    store.setCurrentAssayDetails(assayDetails.value[seekId]);
  };

  const save = async () => {
    try {
      const success = await useSaveAssayDetails(currentAssayDetails.value!);
      if (success) {
        currentAssayDetails.value!.isAssayReadyToLaunch = true;
        store.setAssayDetails(currentAssayDetails.value!.seekId, currentAssayDetails.value!);
        toast.success("Assay configuration saved successfully.");
      } else {
        toast.error("Save failed. Please try again.");
      }
    } catch (e: any) {
      toast.error(getApiErrorMessage(e, "Save"));
    }
  };

  const launch = async (seekId: string) => {
    store.setCurrentAssayDetails(assayDetails.value[seekId]);
    store.setAssayLaunching(seekId, true);
    try {
      const res = await useDashboardGetAssayLaunch(seekId);
      if (!res) {
        toast.warning("Launch is not available for this assay. Please check the configuration.");
        return;
      }
      if (res.message) {
        toast.info(res.message, { timeout: 6000 });
      } else if (res.type === "airflow") {
        store.setAssayExecute(seekId, "Monitor", res.data);
        toast.success("Workflow launched successfully. Click Monitor to track progress.");
      } else if (res.type === "notebook") {
        // Notebook assays open straight into JupyterHub. Open the tab now and
        // stash the URL under Monitor so re-opening it uses the same path.
        store.setAssayExecute(seekId, "Monitor", res.data);
        window.open(res.data, "_blank");
      } else if (res.type === "EP3 workflow launch") {
        window.open(res.data, "_blank");
      }
    } catch (e: any) {
      toast.error(getApiErrorMessage(e, "Launch"));
    } finally {
      store.setAssayLaunching(seekId, false);
    }
  };

  const monitor = (seekId: string) => {
    const url = assayExecute.value[seekId]?.url;
    if (url) window.open(url, "_blank");
  };

  const verify = (seekId: string) => {
    const workflowUUID = assayDetails.value[seekId]?.workflow.uuid;
    window.open(
      `${JUPYTER_BASE_URL}/lab/tree/workflow_outputs/${workflowUUID}/verify.ipynb`,
      "_blank",
    );
  };

  const download = (_seekId: string) => {
    downloadDialog.value = true;
    downloadZipProgressValue.value = 0;
    toast.info("Download feature is being migrated to the portal backend; not available right now.");
  };

  const submit = (_seekId: string) => {
    submitDialog.value = true;
    submitState.value = "waiting";
    toast.info("Submit feature is being migrated to the portal backend; not available right now.");
    submitState.value = "unavailable";
  };

  const expand = (seekId: string) => {
    router.push({ name: "LaunchedAssayOverview", query: { assayId: seekId } });
  };

  return {
    // state
    assayDetails,
    assayExecute,
    currentAssayDetails,
    downloadDialog,
    submitDialog,
    submitState,
    downloadZipProgressValue,
    // actions
    loadAssayList,
    openEdit,
    save,
    launch,
    monitor,
    verify,
    download,
    submit,
    expand,
  };
}
